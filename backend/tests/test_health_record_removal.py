"""Record withdrawal covers derived results, consented readers and future provider context."""

from uuid import uuid4

import pytest
from app import assessment_lifecycle
from app.database import SessionLocal
from app.extended_api import assistant_context
from app.models import AccountEvent, Assessment, HealthRecord, Notification
from conftest import sign_in
from sqlalchemy import func, select
from test_appointments import HEALTH, request_body
from test_delivery import episode, future_slot
from test_pe_screening import available as available  # noqa: F401
from test_pe_screening import pe_examples as pe_examples  # noqa: F401
from test_pe_screening import trained as trained  # noqa: F401


def remove(client, record_id, reason="Measurements entered for the wrong date"):
    return client.request(
        "DELETE", f"/api/patients/me/health-records/{record_id}", json={"reason": reason}
    )


@pytest.mark.parametrize("account,expected", [("patient2", 404), ("doctor1", 403), ("admin", 403)])
def test_health_record_removal_is_owner_only(client, accounts, account, expected):
    sign_in(client)
    record = client.post("/api/patients/me/health-records", json=HEALTH).json()
    sign_in(client, account)
    assert remove(client, record["id"]).status_code == expected
    with SessionLocal() as db:
        assert db.get(HealthRecord, record["id"]).removed_at is None


def test_owner_removes_measurements_from_all_active_views_without_destroying_audit(
    client, accounts
):
    sign_in(client)
    body = {**HEALTH, "request_id": str(uuid4())}
    record = client.post("/api/patients/me/health-records", json=body).json()
    assert remove(client, record["id"], " ").status_code == 422
    first = remove(client, record["id"])
    assert first.status_code == 200, first.text
    assert remove(client, record["id"]).json() == first.json()
    assert client.get("/api/patients/me/health-records").json() == []
    assert client.get(f"/api/patients/me/health-records/{record['id']}").status_code == 410
    assert (
        client.get(f"/api/patients/me/health-records/{record['id']}/assessments").status_code == 410
    )
    workspace = client.get("/api/patients/me/workspace").json()
    assert workspace["records"] == [] and workspace["counts"]["records"] == 0
    assert workspace["pregnancy"]["estimated_weeks"] is None
    assert client.get("/api/patients/me/timeline").json() == []
    assert client.get("/api/patients/me/passport").json()["recent_timeline"] == []
    assert client.post("/api/patients/me/health-records", json=body).status_code == 410
    assert client.post("/api/patients/me/complete-assessment", json=body).status_code == 410
    assert (
        client.post(
            "/api/patients/me/appointments",
            json=request_body(accounts, health_record_ids=[record["id"]]),
        ).status_code
        == 404
    )
    log = client.get("/api/patients/me/removed-health-records").json()
    assert log == [first.json()] and "observations" not in log[0]
    with SessionLocal() as db:
        assert db.get(HealthRecord, record["id"]).observations == HEALTH
        assert (
            db.scalar(
                select(func.count())
                .select_from(AccountEvent)
                .where(AccountEvent.action == "HEALTH_RECORD_REMOVED")
            )
            == 1
        )
    sign_in(client, "patient2")
    assert client.get("/api/patients/me/removed-health-records").json() == []
    assert client.get(f"/api/patients/me/health-records/{record['id']}").status_code == 404
    sign_in(client, "admin")
    assert client.get("/api/admin/stats").json()["health_records"] == 0


def test_record_removal_withdraws_shared_result_and_followup_but_keeps_clinician_notes(
    client, accounts, available, pe_examples
):
    record, result, appointment = episode(client, accounts, pe_examples)
    base = f"/api/doctors/me/appointments/{appointment['id']}"
    note = client.post(
        base + "/notes",
        json={
            "assessment_id": result["id"],
            "body": "Original clinical observation",
            "patient_visible": True,
        },
    )
    assert note.status_code == 201, note.text
    proposed = client.post(
        base + "/follow-ups",
        json={
            "assessment_id": result["id"],
            "request_id": str(uuid4()),
            "scheduled_at": future_slot(6),
            "reason": "Review the selected measurements",
        },
    )
    assert proposed.status_code == 201, proposed.text
    sign_in(client)
    assert remove(client, record["id"]).status_code == 200
    assert client.get("/api/patients/me/assessments").json() == []
    assert client.get(f"/api/patients/me/assessments/{result['id']}/report-data").status_code == 410
    assert client.get("/api/patients/me/follow-ups").json()[0]["declined"] is True
    sign_in(client, "doctor1")
    review = client.get(base + "/review").json()
    assert review["records"] == [] and review["assessments"] == []
    assert review["appointment"]["health_record_ids"] == []
    assert client.get("/api/doctors/me/workspace").json()["counts"]["patients"] == 0
    assert client.get(base + f"/records/{record['id']}/assessments").status_code == 404
    assert (
        client.post(
            base + "/notes",
            json={
                "assessment_id": result["id"],
                "body": "New result-linked note must be blocked",
                "patient_visible": True,
            },
        ).status_code
        == 404
    )
    assert client.get(base + "/notes").json()[0]["assessment_removed"] is True
    amendment = client.post(
        base + f"/notes/{note.json()['id']}/amend",
        json={
            "assessment_id": result["id"],
            "body": "Correction retained after record withdrawal",
            "patient_visible": True,
        },
    )
    assert amendment.status_code == 201, amendment.text
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.kind == "HEALTH_RECORD_REMOVED",
                    Notification.recipient_id == accounts["doctor1"],
                )
            )
            == 1
        )


def test_family_and_future_assistant_context_exclude_withdrawn_observations(
    client, accounts, available, pe_examples
):
    record, _, _ = episode(client, accounts, pe_examples)
    sign_in(client)
    grant = client.post(
        "/api/family/invitations",
        json={
            "recipient_email": "patient2@example.com",
            "scopes": ["observations", "assessments"],
            "consent": True,
        },
    ).json()
    sign_in(client, "patient2")
    assert (
        client.post("/api/family/accept", json={"code": grant["invitation_code"]}).status_code
        == 200
    )
    path = f"/api/family/grants/{grant['id']}/records"
    assert len(client.get(path).json()["observations"]) == 1
    sign_in(client)
    assert remove(client, record["id"]).status_code == 200
    with SessionLocal() as db:
        assert assistant_context(db, accounts["patient1"], ["observations"])["observations"] == []
    sign_in(client, "patient2")
    shared = client.get(path).json()
    assert shared["observations"] == [] and shared["assessments"] == []


def test_record_and_linked_assessment_removal_is_one_transaction(
    client, accounts, available, pe_examples, monkeypatch
):
    record, result, _ = episode(client, accounts, pe_examples)
    sign_in(client)

    def fail(*_args):
        raise RuntimeError("simulated cascade failure")

    monkeypatch.setattr(assessment_lifecycle, "mark_assessment_removed", fail)
    with pytest.raises(RuntimeError, match="simulated cascade failure"):
        remove(client, record["id"])
    with SessionLocal() as db:
        assert db.get(HealthRecord, record["id"]).removed_at is None
        assert db.get(Assessment, result["id"]).removed_at is None


@pytest.mark.parametrize("account", ["patient1", "doctor1"])
def test_technical_admin_evaluation_endpoint_remains_role_protected(client, accounts, account):
    sign_in(client, account)
    assert client.get("/api/admin/model-evaluation").status_code == 403
