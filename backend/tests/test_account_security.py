"""Exercise account recovery, mail secrecy, persistent limits and session revocation."""

import hashlib
from datetime import timedelta

import pytest
from conftest import sign_in
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select

from app import account_email
from app import api as auth_api
from app.auth_limits import consume
from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import AccountEvent, AuthRateBucket, EmailActionToken, User, utc_now


@pytest.fixture
def mailbox(monkeypatch):
    settings = get_settings()
    for key, value in {
        "smtp_host": "smtp.example.invalid",
        "smtp_username": "smtp-test-user",
        "smtp_password": SecretStr("private-smtp-test-password"),
        "smtp_from": "noreply@example.com",
        "public_app_url": "https://care.example.com",
    }.items():
        monkeypatch.setattr(settings, key, value)
    messages = []
    monkeypatch.setattr(
        account_email,
        "send",
        lambda email, purpose, token: messages.append(
            {"email": email, "purpose": purpose, "token": token}
        ),
    )
    return messages


def request_reset(client):
    response = client.post("/api/auth/forgot-password", json={"email": "patient1@example.com"})
    assert response.status_code == 202, response.text
    return response


@pytest.mark.parametrize("role", ["patient", "doctor"])
def test_registration_verification_and_doctor_approval_remain_separate(
    client, mailbox, monkeypatch, role
):
    monkeypatch.setattr(get_settings(), "auth_require_email_verification", True)
    body = {"email": "new@example.com", "password": "NewValidPassword123!", "full_name": "New User"}
    if role == "doctor":
        body.update(registration_number="REG-NEW", specialty="Obstetrics")
    path = "/api/auth/register-doctor" if role == "doctor" else "/api/auth/register"
    created = client.post(path, json=body)
    assert created.status_code == 201, created.text
    assert created.json()["email_verification_required"] is True
    assert len(mailbox) == 1 and mailbox[0]["purpose"] == "VERIFY_EMAIL"
    token = mailbox[0]["token"]
    assert token not in created.text
    credentials = {"email": body["email"], "password": body["password"], "role": role}
    assert client.post("/api/auth/login", json=credentials).json()["detail"]["code"] == (
        "EMAIL_VERIFICATION_REQUIRED"
    )
    confirmed = client.post("/api/auth/verification/confirm", json={"token": token})
    assert confirmed.status_code == 200
    assert client.post("/api/auth/verification/confirm", json={"token": token}).status_code == 400
    assert client.post("/api/auth/login", json=credentials).status_code == 200
    with SessionLocal() as db:
        user = db.get(User, created.json()["id"])
        assert user.email_verified_at is not None
        if role == "doctor":
            assert user.doctor_profile.approved is False
        saved = db.scalar(select(EmailActionToken))
        assert saved.digest == hashlib.sha256(token.encode()).hexdigest()
        assert saved.used_at is not None


def test_reset_has_uniform_requests_revokes_all_sessions_and_is_one_use(client, accounts, mailbox):
    sign_in(client)
    old_cookie = client.cookies.get("bloomcare_session")
    known = request_reset(client)
    unknown = client.post("/api/auth/forgot-password", json={"email": "unknown@example.com"})
    assert known.status_code == unknown.status_code == 202 and known.json() == unknown.json()
    assert len(mailbox) == 1
    token = mailbox[0]["token"]
    assert token not in known.text
    with SessionLocal() as db:
        row = db.scalar(select(EmailActionToken))
        assert row.digest != token and row.used_at is None
        assert (row.expires_at - row.created_at).total_seconds() == pytest.approx(1800, abs=1)
    reset = client.post(
        "/api/auth/reset-password", json={"token": token, "password": "ReplacementPassword123!"}
    )
    assert reset.status_code == 200, reset.text
    assert client.get("/api/auth/me").status_code == 401
    with TestClient(client.app) as other:
        other.cookies.set("bloomcare_session", old_cookie)
        assert other.get("/api/auth/me").status_code == 401
    assert (
        client.post(
            "/api/auth/reset-password", json={"token": token, "password": "AnotherPassword123!"}
        ).status_code
        == 400
    )
    old = {"email": "patient1@example.com", "password": "ValidPassword123!"}
    assert client.post("/api/auth/login", json=old).status_code == 401
    assert (
        client.post(
            "/api/auth/login", json={**old, "password": "ReplacementPassword123!"}
        ).status_code
        == 200
    )
    with SessionLocal() as db:
        user = db.get(User, accounts["patient1"])
        assert user.session_version == 1 and user.email_verified_at is not None
        assert "PASSWORD_RESET_COMPLETED" in [e.action for e in db.scalars(select(AccountEvent))]


@pytest.mark.parametrize("invalidity", ["expired", "superseded", "disabled", "wrong_purpose"])
def test_invalid_recovery_cannot_change_password(client, accounts, mailbox, invalidity):
    request_reset(client)
    token = mailbox[0]["token"]
    with SessionLocal() as db:
        original = db.get(User, accounts["patient1"]).password_hash
        row = db.get(EmailActionToken, hashlib.sha256(token.encode()).hexdigest())
        if invalidity == "expired":
            row.expires_at = utc_now() - timedelta(seconds=1)
        elif invalidity == "disabled":
            db.get(User, accounts["patient1"]).active = False
        elif invalidity == "wrong_purpose":
            row.purpose = "VERIFY_EMAIL"
        db.commit()
    if invalidity == "superseded":
        request_reset(client)
    response = client.post(
        "/api/auth/reset-password", json={"token": token, "password": "ReplacementPassword123!"}
    )
    assert response.status_code == 400
    with SessionLocal() as db:
        assert db.get(User, accounts["patient1"]).password_hash == original


def test_login_counter_persists_across_failed_requests_and_sessions(client, accounts):
    body = {"email": "patient1@example.com", "password": "IncorrectPassword123!"}
    for _ in range(10):
        assert client.post("/api/auth/login", json=body).status_code == 401
    limited = client.post("/api/auth/login", json={**body, "password": "ValidPassword123!"})
    assert limited.status_code == 429 and int(limited.headers["Retry-After"]) > 0
    with SessionLocal() as db:
        buckets = db.scalars(select(AuthRateBucket)).all()
        assert len(buckets) == 2
        assert all(len(b.key) == 64 and "example.com" not in b.key for b in buckets)
        assert max(b.attempts for b in buckets) == 11


def test_peer_limit_also_limits_password_spraying_and_ignores_untrusted_forwarding(
    client, monkeypatch
):
    monkeypatch.setattr(auth_api, "verify_password", lambda *_: False)
    for n in range(50):
        body = {"email": f"unknown{n}@example.com", "password": "IncorrectPassword123!"}
        assert client.post("/api/auth/login", json=body).status_code == 401
    result = client.post("/api/auth/login", json=body, headers={"X-Forwarded-For": "198.51.100.2"})
    assert result.status_code == 429


def test_email_request_limit_applies_to_unknown_accounts_too(client, mailbox):
    for _ in range(3):
        assert (
            client.post(
                "/api/auth/forgot-password", json={"email": "unknown@example.com"}
            ).status_code
            == 202
        )
    response = client.post("/api/auth/verification/request", json={"email": "unknown@example.com"})
    assert response.status_code == 429 and mailbox == []


def test_rate_window_recovers_without_changing_account_state(accounts):
    now = utc_now()
    with SessionLocal() as db:
        consume(db, "test", "synthetic-peer", 1, 60, now=now)
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as error:
            consume(db, "test", "synthetic-peer", 1, 60, now=now + timedelta(seconds=1))
        assert error.value.status_code == 429
    with SessionLocal() as db:
        consume(db, "test", "synthetic-peer", 1, 60, now=now + timedelta(seconds=61))
        assert db.scalar(select(AuthRateBucket)).attempts == 1


def test_mail_failure_does_not_reveal_account_or_log_tokens(
    client, accounts, mailbox, monkeypatch, caplog
):
    def fail(*_):
        raise RuntimeError("private-smtp-test-password must never be logged")

    monkeypatch.setattr(account_email, "send", fail)
    known = request_reset(client)
    unknown = client.post("/api/auth/forgot-password", json={"email": "unknown@example.com"})
    assert known.json() == unknown.json() and known.status_code == unknown.status_code == 202
    assert (
        "private-smtp-test-password" not in caplog.text
        and "patient1@example.com" not in caplog.text
    )
    with SessionLocal() as db:
        assert db.scalar(select(AccountEvent).where(AccountEvent.action == "ACCOUNT_EMAIL_FAILED"))


def test_unconfigured_mail_fails_uniformly_without_fake_delivery(client, accounts, monkeypatch):
    monkeypatch.setattr(get_settings(), "smtp_host", None)
    a = client.post("/api/auth/forgot-password", json={"email": "patient1@example.com"})
    b = client.post("/api/auth/forgot-password", json={"email": "unknown@example.com"})
    assert a.status_code == b.status_code == 503 and a.json() == b.json()


@pytest.mark.parametrize(
    "url",
    [
        "http://care.example.com",
        "https://user@care.example.com",
        "https://care.example.com/path",
        "https://care.example.com?redirect=evil",
    ],
)
def test_email_link_origin_rejects_untrusted_or_non_origin_urls(url):
    with pytest.raises(ValueError):
        Settings.validate_public_url(url)


@pytest.mark.parametrize("security", ["starttls", "ssl"])
def test_smtp_uses_tls_fixed_origin_and_fragment_without_printing_credentials(
    monkeypatch, capsys, security
):
    settings = get_settings()
    for key, value in {
        "smtp_host": "smtp.example.invalid",
        "smtp_username": "smtp-user",
        "smtp_password": SecretStr("private-smtp-password"),
        "smtp_from": "noreply@example.com",
        "public_app_url": "https://care.example.com",
        "smtp_security": security,
    }.items():
        monkeypatch.setattr(settings, key, value)
    events = []

    class SMTP:
        def __init__(self, *args, **kwargs):
            assert kwargs["timeout"] == 10
            if security == "ssl":
                assert kwargs["context"].check_hostname

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def ehlo(self):
            events.append("ehlo")

        def starttls(self, *, context):
            assert context.check_hostname
            events.append("tls")

        def login(self, *_):
            events.append("login")

        def send_message(self, message):
            events.append(message)

    monkeypatch.setattr(account_email.smtplib, "SMTP", SMTP)
    monkeypatch.setattr(account_email.smtplib, "SMTP_SSL", SMTP)
    token = "T" * 43
    account_email.send("person@example.com", "RESET_PASSWORD", token)
    if security == "starttls":
        assert events[:4] == ["ehlo", "tls", "ehlo", "login"]
    message = events[-1]
    assert "https://care.example.com/account/reset#token=" + token in message.get_content()
    assert "private-smtp-password" not in message.as_string()
    assert capsys.readouterr().out == ""
