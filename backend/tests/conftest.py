import os
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

TEST_DIRECTORY = TemporaryDirectory(prefix="bloomcare-test-")
test_url = os.environ.get("BLOOMCARE_TEST_DATABASE_URL")
if test_url:
    parsed = urlsplit(test_url)
    socket = parse_qs(parsed.query).get("host", [""])[0]
    local = parsed.hostname in {"localhost", "127.0.0.1"} or (
        parsed.hostname is None and socket.startswith("/")
    )
    if not local or not parsed.path.startswith("/bloomcare_test_"):
        raise RuntimeError("PostgreSQL tests require a separate local bloomcare_test_* database")
os.environ["DATABASE_URL"] = test_url or f"sqlite:///{Path(TEST_DIRECTORY.name) / 'test.db'}"
os.environ["JWT_SECRET"] = "test-only-secret-abcdefghijklmnopqrstuvwxyz-0123456789-XYZ"
os.environ["COOKIE_SECURE"] = "false"
os.environ["BLOOMCARE_RESEARCH_ASSESSMENTS"] = "false"
os.environ["AUTH_REQUIRE_EMAIL_VERIFICATION"] = "false"
# A developer's configured mailbox must never receive mail from the test suite.
# Email tests substitute a fake sender and explicit synthetic settings.
os.environ["SMTP_HOST"] = ""
os.environ["EMAIL_PROVIDER"] = "smtp"
os.environ["BREVO_API_KEY"] = ""
os.environ["FRONTEND_STATIC_DIR"] = ""
os.environ["AUTH_PROXY_HEADER"] = "none"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import DoctorProfile, PatientProfile, User  # noqa: E402
from app.security import hasher  # noqa: E402


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(connection, _record):
    if engine.dialect.name == "sqlite":
        connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture(scope="session", autouse=True)
def release_test_resources():
    try:
        yield
    finally:
        # All per-test sessions and clients have closed before session teardown.
        # Dispose the pool before deleting the SQLite file, which Windows locks
        # while even an idle pooled connection still has it open.
        engine.dispose()
        TEST_DIRECTORY.cleanup()


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as session:
        yield session


@pytest.fixture
def accounts():
    accounts = {}
    encoded = hasher.hash("ValidPassword123!")
    with SessionLocal() as db:
        for key, role in [
            ("patient1", "patient"),
            ("patient2", "patient"),
            ("doctor1", "doctor"),
            ("doctor2", "doctor"),
            ("admin", "admin"),
        ]:
            user = User(email=f"{key}@example.com", full_name=key, password_hash=encoded, role=role)
            if role == "patient":
                user.patient_profile = PatientProfile()
            if role == "doctor":
                user.doctor_profile = DoctorProfile(registration_number=key, approved=True)
            db.add(user)
            db.flush()
            accounts[key] = user.id
        db.commit()
    return accounts


def sign_in(client, account="patient1"):
    result = client.post(
        "/api/auth/login", json={"email": f"{account}@example.com", "password": "ValidPassword123!"}
    )
    assert result.status_code == 200
    return result
