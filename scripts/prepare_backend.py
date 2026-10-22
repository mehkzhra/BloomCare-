"""Start the existing local database if needed before launching the dev API."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[1]


def prepare_backend(database_url, probe, run=None):
    """Reuse a reachable database; only start Compose for our local dev port."""
    if probe():
        print("Database connection ready.")
        return 0

    url = make_url(database_url)
    local_compose = (
        url.drivername == "postgresql+psycopg"
        and url.host in {"localhost", "127.0.0.1", "::1"}
        and url.port == 5433
        and not any(key in url.query for key in ("host", "hostaddr", "port", "service"))
    )
    if not local_compose:
        print("Database unavailable. Start the database configured in backend/.env, then retry.")
        return 1

    print("Starting BloomCare PostgreSQL. Docker Desktop must be running.")
    command = [
        "docker", "compose", "up", "-d", "--no-recreate",
        "--wait", "--wait-timeout", "45", "db",
    ]
    try:
        (run or subprocess.run)(command, cwd=ROOT, check=True, timeout=55, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        # Driver and subprocess errors may contain credentials; never print them.
        print("PostgreSQL could not start. Open Docker Desktop and wait for its engine to run.")
        print("From the BloomCare folder, run: docker compose up -d --wait db")
        return 1
    if not probe():
        print("PostgreSQL started, but the configured database connection still failed.")
        print("Check Docker Desktop and backend/.env. Keep existing settings and database volumes.")
        return 1
    print("Database connection ready.")
    return 0


def main():
    os.chdir(ROOT / "backend")
    sys.path.insert(0, str(ROOT / "backend"))
    from app.config import get_settings
    from app.database import engine

    def probe():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False

    try:
        return prepare_backend(get_settings().database_url, probe)
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
