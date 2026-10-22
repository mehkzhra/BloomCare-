"""Erroneous results leave every active care view while audit and ownership remain intact."""

from uuid import uuid4

import pytest
from app.database import SessionLocal
from app.models import AccountEvent, Assessment, DoctorNote, HealthRecord, Notification
from conftest import sign_in
from sqlalchemy import func, select
from test_delivery import episode, future_slot
from test_pe_screening import PE_VALUES, create_assessment
from test_pe_screening import available as available  # noqa: F401
from test_pe_screening import pe_examples as pe_examples  # noqa: F401
from test_pe_screening import trained as trained  # noqa: F401


def remove(client, identity, reason="Blood pressure entered incorrectly"):
    return client.request(
        "DELETE", "/api/patients/me/assessments/" + identity, json={"reason": reason}
    )


@pytest.mark.parametrize("account,expected", [("patient2", 404), ("doctor1", 403), ("admin", 403)])
def test_only_owner_can_remove_a_result(
    client, accounts, available, pe_examples, account, expected
):
    sign_in(client)
    _, result = create_assessment(client, pe_examples)
    sign_in(client, account)
    assert remove(client, result["id"]).status_code == expected
    with SessionLocal() as db:
        assert db.get(Assessment, result["id"]).removed_at is None


def test_removal_excludes_history_exports_dashboard_and_admin_totals(
    client, accounts, available, pe_examples
):
    sign_in(client)
    record, result = create_assessment(client, pe_examples)
    path = "/api/patients/me/assessments/" + result["id"]
    assert remove(client, result["id"], "  ").status_code == 422
    first = remove(client, result["id"])
    assert first.status_code == 200, first.text
    assert remove(client, result["id"]).json() == first.json()
    assert client.get("/api/patients/me/assessments").json() == []
    assert client.get(f"/api/patients/me/health-records/{record['id']}/assessments").json() == []
    workspace = client.get("/api/patients/me/workspace").json()
    assert workspace["latest_assessment"] is None and workspace["counts"]["assessments"] == 0
    assert client.get("/api/patients/me/passport").json()["assessments"] == []
    timeline = client.get("/api/patients/me/timeline").json()
    assert not any(row["type"] == "ASSESSMENT" for row in timeline)
    assert client.get(path).status_code == 410
    assert client.get(path + "/report-data").status_code == 410
    assert client.post(path + "/pe", json=PE_VALUES).status_code == 410
    assert (
        client.post(path + "/care-plan", json={"consent": True, "language": "en"}).status_code
        == 410
    )
    assert (
        client.post(
            path + "/alerts",
            json={
                "request_id": str(uuid4()),
                "recipient": "+923001234567",
                "consent": True,
            },
        ).status_code
        == 410
    )
    assert (
        client.post(
            "/api/patients/me/assessments", json={"health_record_id": record["id"]}
        ).status_code
        == 410
    )
    removed = client.get("/api/patients/me/removed-assessments").json()
    assert removed == [first.json()] and "class_scores" not in removed[0]
    with SessionLocal() as db:
        saved = db.get(Assessment, result["id"])
        assert saved.observations_snapshot == result["observations"]
        assert db.get(HealthRecord, record["id"]) is not None
        assert (
            db.scalar(
                select(func.count())
                .select_from(AccountEvent)
                .where(AccountEvent.action == "ASSESSMENT_REMOVED")
            )
            == 1
        )
    sign_in(client, "patient2")
    assert client.get("/api/patients/me/removed-assessments").json() == []
    assert client.get(path + "/report-data").status_code == 404
    sign_in(client, "admin")
    overview = client.get("/api/admin/workspace").json()
    assert overview["counts"]["assessments"] == 0
    assert overview["counts"]["removed_assessments"] == 1
    assert overview["risk_categories"] == {} and overview["review_statuses"] == {}
    assert client.get("/api/admin/stats").json()["assessments"] == 0
    assert client.get("/api/admin/analytics").json()["assessment_categories"] == {}


def test_removed_result_cannot_reenter_doctor_workflows_and_pending_followup_is_withdrawn(
    client, accounts, available, pe_examples
):
    record, result, appointment = episode(client, accounts, pe_examples)
    base = f"/api/doctors/me/appointments/{appointment['id']}"
    reviewed = client.put(
        base + f"/assessments/{result['id']}/review",
        json={
            "status": "URGENT_FOLLOW_UP",
            "reason": "Please discuss the recorded result",
            "follow_up_at": future_slot(2),
            "expected_version": 0,
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    note = client.post(
        base + "/notes",
        json={
            "assessment_id": result["id"],
            "body": "Review retained for the clinical audit",
            "patient_visible": True,
        },
    )
    assert note.status_code == 201, note.text
    proposal = client.post(
        base + "/follow-ups",
        json={
            "assessment_id": result["id"],
            "request_id": str(uuid4()),
            "scheduled_at": future_slot(5),
            "reason": "Discuss the saved result",
        },
    )
    assert proposal.status_code == 201, proposal.text
    sign_in(client)
    assert remove(client, result["id"]).status_code == 200
    assert client.get("/api/patients/me/follow-ups").json()[0]["declined"] is True
    sign_in(client, "doctor1")
    assert client.get("/api/doctors/me/cases").json() == []
    counts = client.get("/api/doctors/me/workspace").json()["counts"]
    assert counts["urgent"] == 0
    # Removing a result does not revoke the separately selected health record.
    assert counts["patients"] == 1
    assert client.get(base + "/review").json()["assessments"] == []
    assert client.get(base + f"/records/{record['id']}/assessments").json() == []
    assert client.get(base + f"/assessments/{result['id']}/report-data").status_code == 410
    assert client.get(base + "/notes").json()[0]["assessment_removed"] is True
    assert (
        client.post(
            base + "/notes",
            json={
                "assessment_id": result["id"],
                "body": "New note must not attach",
                "patient_visible": True,
            },
        ).status_code
        == 410
    )
    amended = client.post(
        base + f"/notes/{note.json()['id']}/amend",
        json={
            "assessment_id": result["id"],
            "body": "Correction: the linked result was removed",
            "patient_visible": True,
        },
    )
    assert amended.status_code == 201, amended.text
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(DoctorNote)) == 2
        assert (
            db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.recipient_id == accounts["doctor1"],
                    Notification.kind == "ASSESSMENT_REMOVED",
                )
            )
            == 1
        )


def test_family_consent_cannot_expose_a_removed_assessment(
    client, accounts, available, pe_examples
):
    sign_in(client)
    _, result = create_assessment(client, pe_examples)
    grant = client.post(
        "/api/family/invitations",
        json={
            "recipient_email": "patient2@example.com",
            "scopes": ["assessments"],
            "consent": True,
        },
    ).json()
    sign_in(client, "patient2")
    assert (
        client.post("/api/family/accept", json={"code": grant["invitation_code"]}).status_code
        == 200
    )
    path = f"/api/family/grants/{grant['id']}/records"
    assert len(client.get(path).json()["assessments"]) == 1
    sign_in(client)
    assert remove(client, result["id"]).status_code == 200
    sign_in(client, "patient2")
    assert client.get(path).json()["assessments"] == []
