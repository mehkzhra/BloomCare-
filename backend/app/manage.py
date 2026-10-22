import argparse
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import DoctorProfile, User
from app.schemas import Register
from app.security import hasher


def main():
    parser = argparse.ArgumentParser(description="Create a trusted BloomCare staff account")
    parser.add_argument("role", choices=["admin", "doctor"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--registration-number")
    parser.add_argument("--specialty", default="Obstetrics")
    args = parser.parse_args()
    if args.role == "doctor" and not args.registration_number:
        parser.error("Doctor accounts require --registration-number")
    password = getpass("Password (12–128 characters): ")
    if password != getpass("Confirm password: "):
        parser.error("Passwords do not match")
    try:
        data = Register(email=args.email, full_name=args.name, password=password)
    except ValidationError as exc:
        parser.error("; ".join(error["msg"] for error in exc.errors()))
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == str(data.email))):
            parser.error("Email is already registered")
        user = User(
            email=str(data.email),
            full_name=data.full_name,
            password_hash=hasher.hash(password),
            role=args.role,
        )
        if args.role == "doctor":
            user.doctor_profile = DoctorProfile(
                registration_number=args.registration_number,
                specialty=args.specialty,
                approved=True,
            )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            parser.error("Account conflicts with an existing doctor registration number")
    print(f"Created {args.role} account. Sign in using the web application.")


if __name__ == "__main__":
    main()
