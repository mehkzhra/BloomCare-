from datetime import datetime, timedelta, timezone

import jwt
import pytest
from conftest import sign_in
from fastapi.testclient import TestClient

from app.assessment_service import pe_screening_required
from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models import User

HEALTH = {
    "age_years": 27,
    "gestational_weeks": 24.5,
    "systolic_mmhg": 120,
    "diastolic_mmhg": 80,
    "glucose_mmol_l": 5.1,
    "temperature_c": 36.8,
    "heart_rate_bpm": 78,
}


def test_registration_login_logout(client):
    payload = {
        "email": "NEW@example.com",
        "password": "ValidPassword123!",
        "full_name": "New Patient",
    }
    created = client.post("/api/auth/register", json=payload)
    assert created.status_code == 201
    assert created.json()["role"] == "patient"
    assert created.json()["email"] == "new@example.com"
    assert "password_hash" not in created.json()
    with SessionLocal() as db:
        assert db.get(User, created.json()["id"]).password_hash.startswith("$argon2id$")
    assert client.post("/api/auth/register", json=payload).status_code == 409
    login = client.post(
        "/api/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    assert login.status_code == 200
    assert "HttpOnly" in login.headers["set-cookie"]
    assert "SameSite=strict" in login.headers["set-cookie"]
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("extra", [{"role": "admin"}, {"role": "doctor"}, {"active": True}])
def test_public_registration_cannot_grant_privileges(client, extra):
    result = client.post(
        "/api/auth/register",
        json={
            "email": "attack@example.com",
            "password": "ValidPassword123!",
            "full_name": "Attack",
            **extra,
        },
    )
    assert result.status_code == 422


def test_weak_password_invalid_email_and_blank_name(client):
    payload = {"email": "valid@example.com", "password": "ValidPassword123!", "full_name": "Person"}
    for key, value in [("email", "not-email"), ("password", "short"), ("full_name", "  ")]:
        assert client.post("/api/auth/register", json={**payload, key: value}).status_code == 422


def test_wrong_credentials_are_generic(client, accounts):
    messages = []
    for email in ["patient1@example.com", "unknown@example.com"]:
        result = client.post(
            "/api/auth/login", json={"email": email, "password": "WrongPassword123!"}
        )
        assert result.status_code == 401
        messages.append(result.json()["detail"])
    assert messages[0] == messages[1]


@pytest.mark.parametrize(
    "path",
    [
        "/api/auth/me",
        "/api/patients/me/profile",
        "/api/admin/stats",
        "/api/patients/me/health-records",
        "/api/doctors/me/profile",
    ],
)
def test_anonymous_blocked(client, path):
    assert client.get(path).status_code == 401


def test_profile_persistence_and_invalid_dates(client, accounts):
    sign_in(client)
    profile = {
        "date_of_birth": "1999-05-10",
        "due_date": "2027-02-01",
        "phone": "+92 300 1234567",
        "preferred_language": "ur",
    }
    assert client.put("/api/patients/me/profile", json=profile).status_code == 200
    with TestClient(app) as second_session:
        sign_in(second_session)
        saved = second_session.get("/api/patients/me/profile").json()
        assert saved["date_of_birth"] == profile["date_of_birth"]
        assert saved["preferred_language"] == "ur"
    assert (
        client.put("/api/patients/me/profile", json={"date_of_birth": "2999-01-01"}).status_code
        == 422
    )


def test_health_history_ownership_and_persistence(client, accounts):
    sign_in(client)
    saved = client.post("/api/patients/me/health-records", json=HEALTH)
    assert saved.status_code == 201
    record_id = saved.json()["id"]
    client.post("/api/auth/logout")
    sign_in(client, "patient2")
    assert client.get("/api/patients/me/health-records").json() == []
    assert client.get(f"/api/patients/me/health-records/{record_id}").status_code == 404
    sign_in(client, "doctor1")
    assert client.get("/api/patients/me/health-records").status_code == 403
    sign_in(client)
    assert client.get("/api/patients/me/health-records").json()[0]["observations"] == HEALTH


@pytest.mark.parametrize(
    "patch",
    [
        {"systolic_mmhg": 20},
        {"diastolic_mmhg": 130},
        {"age_years": -1},
        {"glucose_mmol_l": 0},
        {"patient_id": "another-patient"},
        {"risk": "LOW"},
    ],
)
def test_invalid_health_rejected(client, accounts, patch):
    sign_in(client)
    assert (
        client.post("/api/patients/me/health-records", json={**HEALTH, **patch}).status_code == 422
    )
    assert client.get("/api/patients/me/health-records").json() == []


def test_roles_and_multiple_doctors(client, accounts):
    sign_in(client)
    doctors = client.get("/api/doctors").json()
    assert len(doctors) == 2
    assert client.get("/api/admin/stats").status_code == 403
    assert client.get("/api/doctors/me/profile").status_code == 403
    sign_in(client, "doctor1")
    assert client.get("/api/doctors/me/profile").status_code == 200
    assert client.get("/api/admin/stats").status_code == 403
    sign_in(client, "admin")
    assert client.get("/api/admin/stats").json()["doctors"] == 2
    assert client.get("/api/patients/me/profile").status_code == 403


def test_disabled_account_and_expired_token(client, accounts):
    sign_in(client)
    with SessionLocal() as db:
        db.get(User, accounts["patient1"]).active = False
        db.commit()
    assert client.get("/api/auth/me").status_code == 401
    expired = jwt.encode(
        {
            "sub": accounts["patient2"],
            "iss": "bloomcare",
            "aud": "bloomcare-web",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    client.cookies.set("bloomcare_session", expired, path="/api")
    assert client.get("/api/auth/me").status_code == 401


def test_untrusted_origin_rejected(client, accounts):
    sign_in(client)
    assert (
        client.post(
            "/api/patients/me/health-records",
            json=HEALTH,
            headers={"Origin": "https://untrusted.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/patients/me/health-records",
            json=HEALTH,
            headers={"Origin": "http://localhost:5173"},
        ).status_code
        == 201
    )


@pytest.mark.parametrize(("risk", "expected"), [("LOW", False), ("MEDIUM", True), ("HIGH", True)])
def test_locked_pe_trigger(risk, expected):
    assert pe_screening_required(risk) is expected


def test_unknown_risk_rejected():
    with pytest.raises(ValueError):
        pe_screening_required("unknown")


def test_models_fail_closed_without_saving_predictions(client, accounts):
    sign_in(client)
    assert client.get("/api/capabilities").json()["pregnancy_model_ready"] is False
    record = client.post("/api/patients/me/health-records", json=HEALTH).json()
    assert (
        client.post(
            "/api/patients/me/assessments",
            json={"health_record_id": record["id"]},
        ).status_code
        == 503
    )
    assert client.get("/api/patients/me/assessments").json() == []
    assert len(client.get("/api/patients/me/health-records").json()) == 1


def test_readiness_and_headers(client):
    result = client.get("/api/health/ready")
    assert result.status_code == 200
    assert result.headers["X-Content-Type-Options"] == "nosniff"
    assert result.headers["Cache-Control"] == "no-store"
    assert client.get("/api/health/live").json()["status"] == "ok"
