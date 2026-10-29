from conftest import sign_in
from sqlalchemy import select

from app.database import SessionLocal
from app.models import AccountEvent, DoctorProfile

DOCTOR = {
    "email": "newdoctor@example.com",
    "password": "ValidPassword123!",
    "full_name": "New Doctor",
    "registration_number": "WEB-001",
    "specialty": "Obstetrics",
}


def test_doctor_signup_pending_and_approval(client, accounts):
    result = client.post("/api/auth/register-doctor", json=DOCTOR)
    assert result.status_code == 201
    doctor_id = result.json()["id"]
    with SessionLocal() as db:
        assert db.get(DoctorProfile, doctor_id).approved is False
    assert (
        client.post(
            "/api/auth/login",
            json={**{k: DOCTOR[k] for k in ("email", "password")}, "role": "doctor"},
        ).status_code
        == 200
    )
    assert client.get("/api/doctors/me/profile").json()["approved"] is False
    assert client.get("/api/doctors/me/appointments").status_code == 403
    assert doctor_id not in [d["id"] for d in client.get("/api/doctors").json()]
    assert client.get("/api/admin/accounts").status_code == 403
    sign_in(client, "admin")
    assert (
        client.patch(
            f"/api/admin/doctors/{doctor_id}/approval", json={"approved": True}
        ).status_code
        == 200
    )
    assert doctor_id in [d["id"] for d in client.get("/api/doctors").json()]
    assert any(a["action"] == "DOCTOR_APPROVED" for a in client.get("/api/admin/activity").json())


def test_no_public_admin_or_self_approval(client):
    assert (
        client.post(
            "/api/auth/register",
            json={**{k: DOCTOR[k] for k in ("email", "password", "full_name")}, "role": "admin"},
        ).status_code
        == 422
    )
    assert (
        client.post("/api/auth/register-doctor", json={**DOCTOR, "approved": True}).status_code
        == 422
    )
    assert client.get("/api/admin/accounts").status_code == 401


def test_duplicate_doctor_registration_atomic(client):
    assert client.post("/api/auth/register-doctor", json=DOCTOR).status_code == 201
    assert (
        client.post(
            "/api/auth/register-doctor", json={**DOCTOR, "email": "second@example.com"}
        ).status_code
        == 409
    )
    with SessionLocal() as db:
        assert len(db.scalars(select(AccountEvent)).all()) == 1


def test_disable_rejects_existing_cookie_and_no_secret_data(client, accounts):
    sign_in(client)
    cookie = client.cookies.get("bloomcare_session")
    sign_in(client, "admin")
    rows = client.get("/api/admin/accounts").json()
    assert "password_hash" not in str(rows)
    assert (
        client.patch(
            f"/api/admin/accounts/{accounts['patient1']}/status", json={"active": False}
        ).status_code
        == 200
    )
    client.cookies.set("bloomcare_session", cookie)
    assert client.get("/api/auth/me").status_code == 401


def test_admin_protected_and_strict_boolean(client, accounts):
    sign_in(client, "admin")
    assert (
        client.patch(
            f"/api/admin/accounts/{accounts['admin']}/status", json={"active": False}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/admin/doctors/{accounts['doctor1']}/approval", json={"approved": "true"}
        ).status_code
        == 422
    )
    assert client.get("/api/admin/activity?offset=-1").status_code == 422
    assert client.get("/api/admin/appointments").status_code == 200


def test_wrong_login_role(client, accounts):
    assert (
        client.post(
            "/api/auth/login",
            json={
                "email": "patient1@example.com",
                "password": "ValidPassword123!",
                "role": "doctor",
            },
        ).status_code
        == 401
    )
