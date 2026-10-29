"""Administrator replacement must prove ownership before revoking old access."""

from datetime import timedelta

import pytest
from conftest import sign_in
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import func, select

from app import account_email
from app.account_security import action_rows, create_email_action
from app.config import get_settings
from app.database import SessionLocal
from app.models import AccountEvent, EmailActionToken, User, utc_now
from app.retire_admin import main, retire_admin

PASSWORD = "ValidPassword123!"
OWNER_EMAIL = "owner@example.com"


@pytest.fixture
def replacement(accounts):
    with SessionLocal() as db:
        old = db.get(User, accounts["admin"])
        owner = User(
            email=OWNER_EMAIL, full_name="Project Owner", role="admin",
            email_verified_at=utc_now(), password_hash=old.password_hash,
        )
        db.add(owner)
        db.commit()
        return owner.id


def test_retirement_revokes_old_access_and_tokens_but_preserves_history(
    client, accounts, replacement
):
    sign_in(client, "admin")
    old_id = accounts["admin"]
    with SessionLocal() as db:
        db.add(AccountEvent(actor_id=old_id, subject_id=old_id, action="EXISTING_ACTIVITY"))
        db.commit()
        token = create_email_action(db, db.get(User, old_id), "RESET_PASSWORD")
        # Also retain an already-consumed token's original audit timestamp.
        consumed_at = utc_now() - timedelta(minutes=1)
        db.add(EmailActionToken(
            digest="a" * 64, user_id=old_id, purpose="VERIFY_EMAIL", session_version=0,
            expires_at=utc_now() + timedelta(hours=1), used_at=consumed_at,
        ))
        db.commit()
    assert retire_admin("ADMIN@example.com", "OWNER@example.com", PASSWORD) is True
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={
        "email": "admin@example.com", "password": PASSWORD, "role": "admin",
    }).status_code == 401
    assert client.post("/api/auth/login", json={
        "email": OWNER_EMAIL, "password": PASSWORD, "role": "admin",
    }).status_code == 200
    with SessionLocal() as db:
        old = db.get(User, old_id)
        owner = db.get(User, replacement)
        assert old is not None and old.active is False and old.session_version == 1
        assert owner.active and owner.session_version == 0 and owner.email_verified_at is not None
        events = db.scalars(select(AccountEvent).where(AccountEvent.subject_id == old_id)).all()
        assert {event.action for event in events} == {
            "SIGNED_IN", "EXISTING_ACTIVITY", "ADMIN_RETIRED_VIA_LOCAL_TOOL",
        }
        event = next(e for e in events if e.action == "ADMIN_RETIRED_VIA_LOCAL_TOOL")
        assert event.actor_id == replacement
        assert all(row.used_at is not None for row in db.scalars(
            select(EmailActionToken).where(EmailActionToken.user_id == old_id)
        ))
        with pytest.raises(HTTPException) as error:
            action_rows(db, token, "RESET_PASSWORD")
        assert error.value.status_code == 400
        assert db.get(EmailActionToken, "a" * 64).used_at.replace(tzinfo=None) == (
            consumed_at.replace(tzinfo=None)
        )
    assert retire_admin("admin@example.com", OWNER_EMAIL, PASSWORD) is False
    with SessionLocal() as db:
        assert db.get(User, old_id).session_version == 1
        assert db.scalar(select(func.count()).select_from(AccountEvent).where(
            AccountEvent.action == "ADMIN_RETIRED_VIA_LOCAL_TOOL"
        )) == 1


@pytest.mark.parametrize("case", [
    "same", "missing", "unverified", "disabled", "patient", "wrong-password", "old-patient",
    "invalid-email",
])
def test_retirement_refuses_unusable_replacements_without_changes(accounts, replacement, case):
    old_email, new_email, password = "admin@example.com", OWNER_EMAIL, PASSWORD
    with SessionLocal() as db:
        owner = db.get(User, replacement)
        if case == "same":
            new_email = old_email
        elif case == "missing":
            new_email = "missing@example.com"
        elif case == "unverified":
            owner.email_verified_at = None
        elif case == "disabled":
            owner.active = False
        elif case == "patient":
            new_email = "patient1@example.com"
        elif case == "wrong-password":
            password = "IncorrectPassword123!"
        elif case == "old-patient":
            old_email = "patient1@example.com"
        else:
            new_email = "invalid-email"
        db.commit()
    with pytest.raises(ValueError):
        retire_admin(old_email, new_email, password)
    with SessionLocal() as db:
        assert db.get(User, accounts["admin"]).active is True
        assert db.get(User, accounts["admin"]).session_version == 0
        assert db.get(User, accounts["patient1"]).active is True
        assert db.scalar(select(func.count()).select_from(AccountEvent)) == 0


def test_command_password_is_hidden_and_errors_do_not_echo_it(
    accounts, replacement, monkeypatch, capsys
):
    import app.retire_admin as command

    secret = "PrivateWrongPassword123!"
    monkeypatch.setattr("sys.argv", [
        "retire-admin", "--old-email", "admin@example.com", "--replacement-email", OWNER_EMAIL,
    ])
    monkeypatch.setattr(command, "getpass", lambda _prompt: secret)
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    output = capsys.readouterr()
    assert secret not in output.out + output.err
    monkeypatch.setattr(command, "getpass", lambda _prompt: PASSWORD)
    main()
    assert "Old administrator disabled" in capsys.readouterr().out


@pytest.mark.parametrize("account", ["patient1", "doctor1", "admin"])
def test_each_role_receives_recovery_at_its_registered_address(
    client, accounts, monkeypatch, account
):
    settings = get_settings()
    monkeypatch.setattr(settings, "email_provider", "brevo")
    monkeypatch.setattr(settings, "email_from", "sender@example.com")
    monkeypatch.setattr(settings, "brevo_api_key", SecretStr("synthetic-test-api-key"))
    messages = []
    monkeypatch.setattr(account_email, "send", lambda *args: messages.append(args))
    email = f"{account}@example.com"
    response = client.post("/api/auth/forgot-password", json={"email": email})
    assert response.status_code == 202 and len(messages) == 1
    recipient, purpose, token = messages[0]
    assert recipient == email and purpose == "RESET_PASSWORD"
    password = "NewChosenPassword123!"
    assert token not in response.text
    assert client.post("/api/auth/reset-password", json={
        "token": token, "password": password,
    }).status_code == 200
    role = "patient" if account == "patient1" else "doctor" if account == "doctor1" else "admin"
    assert client.post("/api/auth/login", json={
        "email": email, "password": password, "role": role,
    }).status_code == 200
    with SessionLocal() as db:
        user = db.get(User, accounts[account])
        assert user.role == role and user.email_verified_at is not None
