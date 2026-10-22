"""One-use, hashed email actions and password-reset session invalidation."""

import hashlib
import secrets
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import EmailStr, Field, field_validator
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app import account_email
from app.auth_limits import enforce, utc
from app.database import SessionLocal, get_db
from app.models import AccountEvent, EmailActionToken, User, utc_now
from app.schemas import Input
from app.security import hasher

router = APIRouter(prefix="/api/auth")
ACCEPTED = {
    "message": (
        "If this address is eligible, an email will be sent. "
        "Check your inbox and spam folder and use the latest link."
    )
}


class EmailRequest(Input):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize(cls, value):
        return value.lower()


class TokenInput(Input):
    token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class ResetInput(TokenInput):
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password", mode="before")
    @classmethod
    def no_edge_space(cls, value):
        if isinstance(value, str) and value != value.strip():
            raise ValueError("Passwords must not start or end with whitespace")
        return value


def create_email_action(db, user, purpose):
    # Lock the user before tokens in both issue and consume paths.
    user = db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update(of=User)
        .execution_options(populate_existing=True)
    )
    now = utc_now()
    token = secrets.token_urlsafe(32)
    db.execute(
        update(EmailActionToken)
        .where(
            EmailActionToken.user_id == user.id,
            EmailActionToken.purpose == purpose,
            EmailActionToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    db.execute(
        delete(EmailActionToken).where(EmailActionToken.expires_at < now - timedelta(days=2))
    )
    db.add(
        EmailActionToken(
            digest=hashlib.sha256(token.encode()).hexdigest(),
            user_id=user.id,
            purpose=purpose,
            session_version=user.session_version,
            expires_at=now
            + (timedelta(hours=24) if purpose == "VERIFY_EMAIL" else timedelta(minutes=30)),
        )
    )
    db.commit()
    return token


def registration_delivery(db, user, background):
    if account_email.configured():
        token = create_email_action(db, user, "VERIFY_EMAIL")
        background.add_task(account_email.deliver, user.id, user.email, "VERIFY_EMAIL", token)


def process_email_request(email, purpose):
    # Account lookup, token generation and SMTP all run after the same generic
    # response. They cannot make known and unknown account responses differ.
    try:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email, User.active.is_(True)))
            if user and (purpose != "VERIFY_EMAIL" or user.email_verified_at is None):
                token = create_email_action(db, user, purpose)
                account_email.deliver(user.id, user.email, purpose, token)
    except Exception:
        account_email.logger.warning("Account email request could not complete")


def request_email(db, request, data, background, purpose):
    enforce(db, request, "recovery", str(data.email))
    if not account_email.configured():
        raise HTTPException(503, "Account email is currently unavailable. Please contact support.")
    background.add_task(process_email_request, str(data.email), purpose)
    return ACCEPTED


@router.post("/forgot-password", status_code=202)
def forgot_password(
    data: EmailRequest,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return request_email(db, request, data, background, "RESET_PASSWORD")


@router.post("/verification/request", status_code=202)
def resend_verification(
    data: EmailRequest,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return request_email(db, request, data, background, "VERIFY_EMAIL")


def action_rows(db, raw, purpose):
    digest = hashlib.sha256(raw.encode()).hexdigest()
    row = db.get(EmailActionToken, digest)
    invalid = HTTPException(400, "This link is invalid or expired. Request a new email.")
    if not row:
        raise invalid
    user = db.scalar(
        select(User)
        .where(User.id == row.user_id)
        .with_for_update(of=User)
        .execution_options(populate_existing=True)
    )
    row = db.scalar(
        select(EmailActionToken)
        .where(EmailActionToken.digest == digest)
        .with_for_update(of=EmailActionToken)
        .execution_options(populate_existing=True)
    )
    if (
        not user
        or not user.active
        or not row
        or row.purpose != purpose
        or row.used_at is not None
        or utc(row.expires_at) <= utc_now()
        or row.session_version != user.session_version
    ):
        raise invalid
    return user, row


@router.post("/verification/confirm")
def verify_email(data: TokenInput, request: Request, db: Session = Depends(get_db)):
    enforce(db, request, "confirm")
    user, row = action_rows(db, data.token, "VERIFY_EMAIL")
    now = utc_now()
    user.email_verified_at = user.email_verified_at or now
    row.used_at = now
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="EMAIL_VERIFIED"))
    db.commit()
    return {"message": "Email verified. You can now sign in."}


@router.post("/reset-password")
def reset_password(
    data: ResetInput, request: Request, response: Response, db: Session = Depends(get_db)
):
    enforce(db, request, "confirm")
    user, row = action_rows(db, data.token, "RESET_PASSWORD")
    user.password_hash = hasher.hash(data.password)
    user.session_version += 1
    # Possession of the emailed recovery link also proves email ownership.
    user.email_verified_at = user.email_verified_at or utc_now()
    db.execute(
        update(EmailActionToken)
        .where(EmailActionToken.user_id == user.id, EmailActionToken.used_at.is_(None))
        .values(used_at=utc_now())
    )
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="PASSWORD_RESET_COMPLETED"))
    db.commit()
    response.delete_cookie("bloomcare_session", path="/api", samesite="strict")
    return {"message": "Password updated. Sign in again on each device."}
