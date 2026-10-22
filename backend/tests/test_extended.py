from datetime import timedelta
from uuid import uuid4

from app.config import get_settings
from app.database import SessionLocal
from app.models import FamilyGrant, Notification, utc_now
from app.reminders import process_reminders
from conftest import sign_in
from pydantic import SecretStr
from sqlalchemy import select
from test_appointments import book, decide
from test_care import MEDICINE, SYMPTOM


def test_family_scope_email_and_revoke(client, accounts):
    sign_in(client)
    client.post("/api/patients/me/symptoms", json=SYMPTOM)
    result = client.post(
        "/api/family/invitations",
        json={"recipient_email": "patient2@example.com", "scopes": ["symptoms"], "consent": True},
    )
    assert result.status_code == 201
    grant = result.json()
    assert "token_hash" not in result.text
    sign_in(client, "doctor1")
    assert (
        client.post("/api/family/accept", json={"code": grant["invitation_code"]}).status_code
        == 403
    )
    sign_in(client, "patient2")
    assert (
        client.post("/api/family/accept", json={"code": grant["invitation_code"]}).status_code
        == 200
    )
    view = client.get("/api/family/grants/" + grant["id"] + "/records")
    assert view.status_code == 200
    assert view.json()["symptoms"][0]["description"] == SYMPTOM["description"]
    assert "observations" not in view.json() and "profile" not in view.json()
    assert (
        client.get("/api/family/grants/" + grant["id"] + "/reports/fake/download").status_code
        == 403
    )
    assert client.delete("/api/family/grants/" + grant["id"]).status_code == 404
    sign_in(client)
    assert client.delete("/api/family/grants/" + grant["id"]).status_code == 204
    sign_in(client, "patient2")
    assert client.get("/api/family/grants/" + grant["id"] + "/records").status_code == 403


def test_family_invitation_expiry_and_wrong_email(client, accounts):
    sign_in(client)
    grant = client.post(
        "/api/family/invitations",
        json={"recipient_email": "wrong@example.com", "scopes": ["profile"], "consent": True},
    ).json()
    sign_in(client, "patient2")
    assert (
        client.post("/api/family/accept", json={"code": grant["invitation_code"]}).status_code
        == 404
    )
    sign_in(client)
    grant = client.post(
        "/api/family/invitations",
        json={"recipient_email": "patient2@example.com", "scopes": ["profile"], "consent": True},
    ).json()
    with SessionLocal() as db:
        db.get(FamilyGrant, grant["id"]).invite_expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    sign_in(client, "patient2")
    assert (
        client.post("/api/family/accept", json={"code": grant["invitation_code"]}).status_code
        == 403
    )


def test_reminder_worker_deduplicates_and_owner_only(client, accounts):
    sign_in(client)
    med = client.post("/api/patients/me/medications", json=MEDICINE).json()
    due = utc_now() + timedelta(minutes=1)
    r = client.post(
        "/api/patients/me/reminders", json={"medication_id": med["id"], "due_at": due.isoformat()}
    )
    assert r.status_code == 201
    process_reminders(due + timedelta(seconds=1))
    process_reminders(due + timedelta(seconds=2))
    alerts = client.get("/api/notifications").json()["items"]
    assert len([a for a in alerts if a["kind"] == "MEDICATION_REMINDER"]) == 1
    sign_in(client, "patient2")
    assert client.delete("/api/patients/me/reminders/" + r.json()["id"]).status_code == 404
    assert client.get("/api/patients/me/reminders").json() == []


def test_recurring_reminder_advances_and_cancel_stops(client, accounts):
    sign_in(client)
    med = client.post("/api/patients/me/medications", json=MEDICINE).json()
    due = utc_now() + timedelta(minutes=1)
    r = client.post(
        "/api/patients/me/reminders",
        json={"medication_id": med["id"], "due_at": due.isoformat(), "period_hours": 24},
    ).json()
    process_reminders(due + timedelta(seconds=1))
    assert client.get("/api/patients/me/reminders").json()[0]["cancelled"] is False
    assert client.delete("/api/patients/me/reminders/" + r["id"]).status_code == 204
    process_reminders(due + timedelta(days=2))
    with SessionLocal() as db:
        assert (
            len(
                db.scalars(
                    select(Notification).where(Notification.kind == "MEDICATION_REMINDER")
                ).all()
            )
            == 1
        )


def test_groq_not_configured_and_consent_required(client, accounts, monkeypatch):
    sign_in(client)
    monkeypatch.setattr(get_settings(), "groq_api_key", None)
    data = {"question": "Explain my records", "consent": True, "request_id": str(uuid4())}
    assert client.post("/api/patients/me/assistant", json=data).status_code == 503
    assert (
        client.post("/api/patients/me/assistant", json={**data, "consent": False}).status_code
        == 422
    )
    assert "groq_api_key" not in client.get("/api/patients/me/assistant/status").text


def test_groq_only_selected_own_context_and_retry(client, accounts, monkeypatch):
    import app.groq_service as module

    payloads = []

    class Provider:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            payloads.append(kwargs["json"])

            class Reply:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"choices": [{"message": {"content": "Example explanation"}}]}

            return Reply()

    monkeypatch.setattr(module.httpx, "Client", Provider)
    monkeypatch.setattr(get_settings(), "groq_api_key", SecretStr("fake-key-for-test-only"))
    sign_in(client)
    client.post("/api/patients/me/symptoms", json=SYMPTOM)
    data = {
        "question": "Explain the symptom record",
        "context": ["symptoms"],
        "consent": True,
        "request_id": str(uuid4()),
    }
    assert client.post("/api/patients/me/assistant", json=data).status_code == 201
    assert client.post("/api/patients/me/assistant", json=data).status_code == 201
    assert len(payloads) == 1
    assert SYMPTOM["description"] in str(payloads)
    assert "patient1@example.com" not in str(payloads)
    assert "fake-key" not in str(payloads)
    sign_in(client, "patient2")
    assert client.get("/api/patients/me/assistant/history").json() == []


def test_consultation_participants_signals_and_end(client, accounts):
    sign_in(client)
    a = book(client, accounts)
    path = "/api/appointments/" + a["id"] + "/consultation"
    assert client.get(path).status_code == 403
    sign_in(client, "doctor1")
    decide(client, a)
    call = client.post(path).json()
    assert call["id"]
    signal_url = "/api/consultations/" + call["id"] + "/signals"
    assert (
        client.post(
            signal_url, json={"kind": "offer", "payload": {"type": "offer", "sdp": "demo"}}
        ).status_code
        == 201
    )
    assert client.get(signal_url).json() == []
    sign_in(client, "patient2")
    assert client.get(signal_url).status_code == 404
    sign_in(client)
    assert client.get(signal_url).json()[0]["kind"] == "offer"
    assert client.post("/api/consultations/" + call["id"] + "/end").status_code == 200
    assert client.get(signal_url).status_code == 409


def test_audit_records_templates_not_secrets_and_admin_only(client, accounts):
    sign_in(client)
    client.get("/api/patients/me/profile?private_parameter=never-store-this")
    assert client.get("/api/admin/analytics").status_code == 403
    sign_in(client, "admin")
    data = client.get("/api/admin/audit")
    assert data.status_code == 200
    assert "/api/patients/me/profile" in data.text
    assert "never-store-this" not in data.text and "ValidPassword" not in data.text
    assert any(row["actor"] == "patient1" for row in data.json())
    stats = client.get("/api/admin/analytics").json()
    assert stats["account_roles"]["patient"] == 2
