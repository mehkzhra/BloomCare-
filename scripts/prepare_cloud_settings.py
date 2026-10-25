"""Prepare private Northflank settings from the working Windows installation."""

import getpass
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from dotenv import dotenv_values
from pydantic import EmailStr, TypeAdapter, ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings  # noqa: E402

PROVIDER_KEYS = (
    "EMAIL_PROVIDER", "EMAIL_FROM", "BREVO_API_KEY", "SMTP_HOST", "SMTP_PORT",
    "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM", "SMTP_SECURITY",
    "GROQ_API_KEY", "GROQ_MODEL", "WEBRTC_ICE_SERVERS",
)


def cloud_values(source, *, origin, database_url, email, name):
    parsed = urlsplit(database_url)
    if (
        parsed.scheme not in {"postgres", "postgresql", "postgresql+psycopg"}
        or not parsed.hostname
        or not parsed.hostname.endswith(".neon.tech")
        or not parsed.username or not parsed.password
        or parsed.path in {"", "/"}
        or parse_qs(parsed.query).get("sslmode") not in [
            ["require"], ["verify-ca"], ["verify-full"],
        ]
    ):
        raise ValueError("Paste the Neon PostgreSQL URL with SSL enabled, without a psql command.")
    try:
        address = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    except ValidationError:
        raise ValueError("Enter the administrator's reachable email address.") from None
    if not 2 <= len(name.strip()) <= 120:
        raise ValueError("Use an administrator name between 2 and 120 characters.")
    values = {key: source[key] for key in PROVIDER_KEYS if source.get(key)}
    if not values.get("GROQ_API_KEY"):
        raise ValueError("Configure GROQ_API_KEY in the working backend/.env first.")
    values.update({
        "DATABASE_URL": database_url,
        "JWT_SECRET": secrets.token_urlsafe(64),
        "PUBLIC_APP_URL": origin.rstrip("/"),
        "ALLOWED_ORIGINS": origin.rstrip("/"),
        "COOKIE_SECURE": "true",
        "AUTH_REQUIRE_EMAIL_VERIFICATION": "true",
        "AUTH_PROXY_HEADER": "none",
        "BLOOMCARE_RESEARCH_ASSESSMENTS": "true",
        "BOOTSTRAP_ADMIN_EMAIL": address,
        "BOOTSTRAP_ADMIN_NAME": name.strip(),
        "PORT": "10000",
    })
    try:
        settings = Settings(_env_file=None, **{key.lower(): val for key, val in values.items()})
        json.loads(settings.webrtc_ice_servers)
    except (ValidationError, json.JSONDecodeError):
        raise ValueError(
            "Check the HTTPS origin, email provider and existing video settings."
        ) from None
    return values


def save_private(values, destination):
    text = "".join(
        f"{key}={json.dumps(value, ensure_ascii=False)}\n" for key, value in values.items()
    )
    # Exclusive creation preserves the cloud session key on accidental reruns.
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
        output.write(text)


def main():
    source = ROOT / "backend/.env"
    destination = ROOT / "backend/.env.northflank"
    if not source.is_file():
        raise SystemExit("Run this from the working installation with backend/.env configured.")
    if destination.exists():
        raise SystemExit("backend/.env.northflank already exists; reuse it to keep your cloud key.")
    origin = input("Northflank public HTTPS URL (Networking): ").strip()
    database_url = getpass.getpass("Neon PostgreSQL URL (hidden while typing): ").strip()
    email = input("Administrator's real email: ").strip()
    name = input("Administrator name [BloomCare Administrator]: ").strip()
    try:
        values = cloud_values(
            dotenv_values(source, interpolate=False), origin=origin, database_url=database_url,
            email=email, name=name or "BloomCare Administrator",
        )
        save_private(values, destination)
    except (ValueError, OSError) as error:
        message = (
            str(error) if isinstance(error, ValueError) else "Could not write private settings."
        )
        raise SystemExit(message) from None
    print("Created backend/.env.northflank; no credentials were printed.")
    print("Import it as Northflank runtime environment variables; it is ignored by Git.")
    print("Mount the three private PE files separately before starting the deployment.")


if __name__ == "__main__":
    main()
