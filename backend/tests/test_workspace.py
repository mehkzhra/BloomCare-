"""Verify actual dashboard totals, role scopes, clinical grants and usable coverage errors."""

import pytest
from conftest import sign_in
from test_appointments import HEALTH
from test_delivery import episode
from test_pe_screening import PE_VALUES
from test_pe_screening import available as available  # noqa: F401
from test_pe_screening import pe_examples as pe_examples  # noqa: F401
from test_pe_screening import trained as trained  # noqa: F401

from app.database import SessionLocal
from app.models import DoctorProfile

PATHS = {
    "patient1": "/api/patients/me/workspace",
    "doctor1": "/api/doctors/me/workspace",
    "admin": "/api/admin/workspace",
}


@pytest.mark.parametrize("path", PATHS.values())
def test_workspaces_require_login(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize(
    "account,path", [(a, p) for a in PATHS for role, p in PATHS.items() if role != a]
)
def test_each_workspace_is_role_protected(client, accounts, account, path):
    sign_in(client, account)
    assert client.get(path).status_code == 403


def test_patient_totals_are_not_a_page_length_and_never_include_another_patient(client, accounts):
    sign_in(client)
    for _ in range(9):
        assert client.post("/api/patients/me/health-records", json=HEALTH).status_code == 201
    first = client.get(PATHS["patient1"])
    assert first.status_code == 200, first.text
    data = first.json()
    assert data["counts"]["records"] == 9 and len(data["records"]) == 7
    assert data["latest_assessment"] is None and data["urgent_reviews"] == []
    assert all(d["id"] in {accounts["doctor1"], accounts["doctor2"]} for d in data["care_team"])
    sign_in(client, "patient2")
    second = client.get(PATHS["patient1"]).json()
    assert second["counts"]["records"] == 0 and second["records"] == []
    assert second["pregnancy"]["estimated_weeks"] is None


def test_unapproved_doctor_workspace_does_not_expose_patients(client, accounts):
    with SessionLocal() as db:
        db.get(DoctorProfile, accounts["doctor1"]).approved = False
        db.commit()
    sign_in(client, "doctor1")
    data = client.get(PATHS["doctor1"]).json()
    assert data["profile"]["approved"] is False
    assert data["appointments"] == data["priority_cases"] == []
    assert data["analytics"] is None and all(n == 0 for n in data["counts"].values())


def test_doctor_queue_respects_the_shared_episode_and_cancellation(
    client, accounts, available, pe_examples
):
    record, assessment, appointment = episode(client, accounts, pe_examples)
    before = client.get(PATHS["doctor1"])
    assert before.status_code == 200, before.text
    data = before.json()
    assert data["counts"]["patients"] == data["counts"]["awaiting_review"] == 1
    assert data["priority_cases"][0]["assessment"]["id"] == assessment["id"]
    sign_in(client, "doctor2")
    other = client.get(PATHS["doctor1"]).json()
    assert other["counts"]["patients"] == 0 and other["priority_cases"] == []
    sign_in(client)
    assert (
        client.post(f"/api/patients/me/appointments/{appointment['id']}/cancel").status_code == 200
    )
    sign_in(client, "doctor1")
    after = client.get(PATHS["doctor1"]).json()
    assert after["counts"]["patients"] == 0 and after["priority_cases"] == []


def test_admin_review_counts_include_unreviewed_assessments_and_filter_pending_doctors(
    client, accounts, available, pe_examples
):
    _, assessment, appointment = episode(client, accounts, pe_examples)
    with SessionLocal() as db:
        db.get(DoctorProfile, accounts["doctor2"]).approved = False
        db.commit()
    sign_in(client, "admin")
    data = client.get(PATHS["admin"]).json()
    assert data["counts"]["pending_doctors"] == 1
    assert data["counts"]["awaiting_review"] == 1
    assert data["review_statuses"] == {"PENDING": 1}
    assert "token" not in str(data["integrations"]).lower()
    pending = client.get("/api/admin/accounts?approval=pending&active=true").json()
    assert [r["id"] for r in pending] == [accounts["doctor2"]]
    assert client.get("/api/admin/analytics").json()["clinical_review_status"] == {"PENDING": 1}
    sign_in(client, "doctor1")
    response = client.put(
        f"/api/doctors/me/appointments/{appointment['id']}/assessments/{assessment['id']}/review",
        json={
            "status": "URGENT_FOLLOW_UP",
            "reason": "Discuss recorded observations promptly",
            "expected_version": 0,
        },
    )
    assert response.status_code == 200, response.text
    sign_in(client, "admin")
    after = client.get(PATHS["admin"]).json()
    assert after["counts"]["urgent"] == 1 and after["counts"]["awaiting_review"] == 0


def test_unsupported_pe_reports_exact_saved_field_values_without_changing_them(
    client, accounts, available, pe_examples
):
    sign_in(client)
    result = client.post(
        "/api/patients/me/complete-assessment",
        json={
            **pe_examples["MEDIUM"],
            "systolic_mmhg": 140,
            "clinical_indicators": {**PE_VALUES, "hb": 12},
        },
    )
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["pe_status"] == "OUTSIDE_COVERAGE"
    issues = {r["name"]: r for r in data["pe_input_issues"]}
    assert issues["systolic_mmhg"]["value"] == 140 and issues["systolic_mmhg"]["maximum"] == 130
    assert issues["hb"]["value"] == 12 and issues["hb"]["maximum"] == 11.2
    assert data["pe_screening"] is None
    assert data["observations"]["systolic_mmhg"] == 140
