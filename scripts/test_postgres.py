"""Run migration and API tests in a separate temporary PostgreSQL database."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
os.chdir(root / "backend")
from app.config import get_settings  # noqa: E402

source_url = make_url(get_settings().database_url)
if source_url.drivername != "postgresql+psycopg":
    raise SystemExit("Configure PostgreSQL and start the database first.")
local = source_url.host in {"localhost", "127.0.0.1"} or (
    source_url.host is None and str(source_url.query.get("host", "")).startswith("/")
)
if not local:
    raise SystemExit(
        "Run this development check only against a local PostgreSQL server."
    )
database = f"bloomcare_test_{uuid4().hex[:12]}"
connection_url = source_url.set(drivername="postgresql").render_as_string(
    hide_password=False
)
test_options = dict(source_url.query)
test_options["options"] = (
    str(test_options.get("options", ""))
    + " -c lock_timeout=10000 -c statement_timeout=30000"
).strip()
test_url = source_url.set(database=database, query=test_options).render_as_string(
    hide_password=False
)
environment = {
    **os.environ,
    "DATABASE_URL": test_url,
    "BLOOMCARE_TEST_DATABASE_URL": test_url,
    "PYTHONUNBUFFERED": "1",
}
with psycopg.connect(connection_url, autocommit=True) as connection:
    connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        for command in [
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            [sys.executable, "-m", "alembic", "check"],
            [
                sys.executable,
                "-u",
                "-m",
                "pytest",
                "-vv",
                "-x",
                "-o",
                "addopts=",
                "-o",
                "faulthandler_timeout=45",
            ],
        ]:
            subprocess.run(command, env=environment, check=True, timeout=900)
    finally:
        connection.execute(
            sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database))
        )
print(
    "PostgreSQL migration and workflow tests passed. Temporary test database removed."
)
