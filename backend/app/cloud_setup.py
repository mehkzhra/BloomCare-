"""Initialize the first administrator without a shared or printed password."""

import secrets

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import User
from app.security import hasher


def bootstrap_admin(email, name="BloomCare Administrator"):
    if not email:
        with SessionLocal() as db:
            if db.scalar(select(User.id).where(User.role == "admin", User.active.is_(True))):
                return False
        raise ValueError("Set BOOTSTRAP_ADMIN_EMAIL before the first cloud deployment")
    address = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    if not 2 <= len(name.strip()) <= 120:
        raise ValueError("Choose an administrator name between 2 and 120 characters")
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == address))
        if existing and existing.role == "admin" and existing.active:
            return False
        if db.scalar(select(func.count()).select_from(User)):
            raise ValueError(
                "Bootstrap only supports an empty database; existing accounts preserved"
            )
        db.add(User(
            email=address, full_name=name.strip(), role="admin",
            password_hash=hasher.hash(secrets.token_urlsafe(48)),
        ))
        db.commit()
    # The owner requests Forgot password from the website. No email is sent on startup.
    return True
