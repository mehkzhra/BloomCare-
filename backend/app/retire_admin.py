"""Retire a test administrator from a trusted local maintenance terminal."""

import argparse
from getpass import getpass

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select, update

from app.database import SessionLocal
from app.models import AccountEvent, EmailActionToken, User, utc_now
from app.security import verify_password


def retire_admin(old_email, replacement_email, replacement_password):
    address = TypeAdapter(EmailStr)
    old_email = str(address.validate_python(old_email)).lower()
    replacement_email = str(address.validate_python(replacement_email)).lower()
    if old_email == replacement_email:
        raise ValueError("The replacement must be a different administrator")
    with SessionLocal() as db:
        # Serialize retirements in a stable order so two admins cannot retire each
        # other concurrently. Email-action consumers also lock users before tokens.
        admins = db.scalars(
            select(User).where(User.role == "admin").order_by(User.id).with_for_update(of=User)
        ).all()
        old = next((user for user in admins if user.email == old_email), None)
        replacement = next((user for user in admins if user.email == replacement_email), None)
        if old is None:
            raise ValueError("The old email must belong to an administrator")
        if (
            replacement is None
            or not replacement.active
            or replacement.email_verified_at is None
            or not verify_password(replacement.password_hash, replacement_password)
        ):
            raise ValueError(
                "Use a different active, email-verified administrator and its correct password"
            )
        if not old.active:
            return False
        old.active = False
        old.session_version += 1
        db.execute(
            update(EmailActionToken)
            .where(EmailActionToken.user_id == old.id, EmailActionToken.used_at.is_(None))
            .values(used_at=utc_now())
        )
        db.add(AccountEvent(
            actor_id=replacement.id, subject_id=old.id, action="ADMIN_RETIRED_VIA_LOCAL_TOOL"
        ))
        db.commit()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Disable a test admin after verifying its replacement"
    )
    parser.add_argument("--old-email", required=True)
    parser.add_argument("--replacement-email", required=True)
    args = parser.parse_args()
    password = getpass("New verified administrator's password (hidden): ")
    try:
        changed = retire_admin(args.old_email, args.replacement_email, password)
    except ValueError:
        # Do not echo supplied values, password, or database connection details.
        parser.error(
            "No account changed. Check both emails; the replacement must be a different "
            "active, verified administrator with the correct password."
        )
    print(
        "Old administrator disabled; its sessions and recovery links were revoked. "
        "History retained."
        if changed else "Old administrator is already disabled. No changes made."
    )


if __name__ == "__main__":
    main()
