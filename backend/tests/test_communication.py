from uuid import uuid4

from conftest import sign_in
from sqlalchemy import func, select
from test_appointments import book, decide

from app.database import SessionLocal
from app.models import CareMessage, Notification

PDF = b"%PDF-1.4\nDemo report\n%%EOF"


def upload(client):
    result = client.post(
        "/api/patients/me/reports",
        content=PDF,
        headers={"Content-Type": "application/pdf", "X-Report-Title": "CBC%20report"},
    )
    assert result.status_code == 201
    return result.json()


def accepted(client, accounts):
    sign_in(client)
    a = book(client, accounts)
    sign_in(client, "doctor1")
    assert decide(client, a).status_code == 200
    return a


def test_report_roundtrip_and_patient_isolation(client, accounts):
    sign_in(client)
    r = upload(client)
    response = client.get("/api/patients/me/reports/" + r["id"] + "/download")
    assert response.content == PDF
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert client.get("/api/patients/me/reports").json()[0]["title"] == "CBC report"
    assert any(row["type"] == "REPORT" for row in client.get("/api/patients/me/timeline").json())
    sign_in(client, "patient2")
    assert client.get("/api/patients/me/reports").json() == []
    assert client.get("/api/patients/me/reports/" + r["id"] + "/download").status_code == 404
    assert client.delete("/api/patients/me/reports/" + r["id"]).status_code == 404


def test_upload_signature_type_size_and_role(client, accounts, monkeypatch):
    import app.communication_api as module

    sign_in(client)
    assert (
        client.post(
            "/api/patients/me/reports",
            content=b"not-pdf",
            headers={"Content-Type": "application/pdf"},
        ).status_code
        == 415
    )
    assert (
        client.post(
            "/api/patients/me/reports", content=PDF, headers={"Content-Type": "text/html"}
        ).status_code
        == 415
    )
    monkeypatch.setattr(module, "MAX_REPORT", 8)
    assert (
        client.post(
            "/api/patients/me/reports", content=PDF, headers={"Content-Type": "application/pdf"}
        ).status_code
        == 413
    )
    sign_in(client, "doctor1")
    assert (
        client.post(
            "/api/patients/me/reports", content=PDF, headers={"Content-Type": "application/pdf"}
        ).status_code
        == 403
    )


def test_explicit_share_scope_revoke_and_closure(client, accounts):
    a = accepted(client, accounts)
    sign_in(client)
    r = upload(client)
    path = f"/patients/me/appointments/{a['id']}/reports"
    assert (
        client.post("/api" + path, json={"report_id": r["id"], "consent": False}).status_code == 422
    )
    assert (
        client.post("/api" + path, json={"report_id": r["id"], "consent": "true"}).status_code
        == 422
    )
    assert (
        client.post("/api" + path, json={"report_id": r["id"], "consent": True}).status_code == 201
    )
    sign_in(client, "doctor1")
    url = f"/api/doctors/me/appointments/{a['id']}/reports/{r['id']}/download"
    assert client.get(url).content == PDF
    sign_in(client, "doctor2")
    assert client.get(url).status_code == 404
    sign_in(client)
    assert client.delete("/api" + path + "/" + r["id"]).status_code == 204
    sign_in(client, "doctor1")
    assert client.get(url).status_code == 404
    sign_in(client)
    client.post("/api" + path, json={"report_id": r["id"], "consent": True})
    client.post(f"/api/patients/me/appointments/{a['id']}/cancel")
    sign_in(client, "doctor1")
    assert client.get(url).status_code == 403


def test_report_deletion_revokes_shares(client, accounts):
    a = accepted(client, accounts)
    sign_in(client)
    r = upload(client)
    client.post(
        f"/api/patients/me/appointments/{a['id']}/reports",
        json={"report_id": r["id"], "consent": True},
    )
    assert client.delete("/api/patients/me/reports/" + r["id"]).status_code == 204
    sign_in(client, "doctor1")
    assert client.get(f"/api/doctors/me/appointments/{a['id']}/reports").json() == []


def test_messages_retry_scope_and_notification(client, accounts):
    a = accepted(client, accounts)
    path = f"/api/appointments/{a['id']}/messages"
    sign_in(client)
    data = {"body": "Can we discuss the report?", "client_message_id": str(uuid4())}
    first = client.post(path, json=data)
    assert first.status_code == 201
    assert client.post(path, json=data).json()["id"] == first.json()["id"]
    assert client.post(path, json={**data, "body": "Different text"}).status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(CareMessage)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.kind == "NEW_MESSAGE")
            )
            == 1
        )
    sign_in(client, "patient2")
    assert client.get(path).status_code == 404
    sign_in(client, "admin")
    assert client.get(path).status_code == 403
    sign_in(client, "doctor1")
    assert client.get(path).json()["messages"][0]["body"] == data["body"]
    alerts = client.get("/api/notifications").json()
    alert = next(r for r in alerts["items"] if r["kind"] == "NEW_MESSAGE")
    assert client.patch("/api/notifications/" + alert["id"] + "/read").status_code == 200
    sign_in(client, "doctor2")
    assert client.patch("/api/notifications/" + alert["id"] + "/read").status_code == 404
    assert client.get("/api/notifications").json()["items"] == []


def test_closed_episode_keeps_message_history_and_blocks_new_send(client, accounts):
    a = accepted(client, accounts)
    path = f"/api/appointments/{a['id']}/messages"
    client.post(path, json={"body": "Doctor reply", "client_message_id": str(uuid4())})
    assert decide(client, a, "COMPLETE").status_code == 200
    sign_in(client)
    result = client.get(path).json()
    assert result["can_send"] is False
    assert result["messages"][0]["body"] == "Doctor reply"
    assert (
        client.post(
            path, json={"body": "Late message", "client_message_id": str(uuid4())}
        ).status_code
        == 403
    )


def test_pending_episode_and_foreign_report_cannot_share(client, accounts):
    sign_in(client, "patient2")
    foreign = upload(client)
    sign_in(client)
    a = book(client, accounts)
    url = f"/api/patients/me/appointments/{a['id']}/reports"
    assert client.post(url, json={"report_id": foreign["id"], "consent": True}).status_code == 403
    sign_in(client, "doctor1")
    decide(client, a)
    sign_in(client)
    assert client.post(url, json={"report_id": foreign["id"], "consent": True}).status_code == 404


def test_private_note_no_notification_and_transition_retry_no_duplicate(client, accounts):
    a = accepted(client, accounts)
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(Notification))
    assert decide(client, a).status_code == 200
    assert (
        client.post(
            f"/api/doctors/me/appointments/{a['id']}/notes",
            json={"body": "Private", "patient_visible": False},
        ).status_code
        == 201
    )
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Notification)) == before
