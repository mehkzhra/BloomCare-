from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash("temporary-timing-equalizer-password")


def verify_password(encoded: str, password: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def issue_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user.id,
            "iat": now,
            "exp": now + timedelta(minutes=settings.jwt_minutes),
            "iss": "bloomcare",
            "aud": "bloomcare-web",
            "sv": user.session_version,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def current_user(
    request: Request,
    bloomcare_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(401, "Please sign in to continue")
    if not bloomcare_session:
        raise unauthorized
    try:
        claims = jwt.decode(
            bloomcare_session,
            get_settings().jwt_secret,
            algorithms=["HS256"],
            audience="bloomcare-web",
            issuer="bloomcare",
            options={"require": ["sub", "iat", "exp", "iss", "aud"]},
        )
        user = db.get(User, claims["sub"])
    except (jwt.InvalidTokenError, TypeError):
        raise unauthorized from None
    if (
        not user
        or not user.active
        or claims.get("sv", 0) != user.session_version
        or (get_settings().auth_require_email_verification and user.email_verified_at is None)
    ):
        raise unauthorized
    request.state.actor_id = user.id
    return user


def require_role(role: str):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role != role:
            raise HTTPException(403, "This action is unavailable for your account role")
        return user

    return dependency
