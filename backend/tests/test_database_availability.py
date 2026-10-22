import socket
import subprocess
from threading import Event, Thread
from time import monotonic
from unittest.mock import Mock

import pytest
from app import main
from app.database import create_database_engine, get_db
from conftest import sign_in
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from test_delivery_scripts import load


@pytest.mark.parametrize(
    "error",
    [
        OperationalError("private SQL", {}, Exception("private password")),
        PoolTimeout("private DSN"),
    ],
)
def test_outage_returns_safe_503_without_retrying_audit_or_losing_session(
    client, accounts, monkeypatch, caplog, error
):
    sign_in(client)
    audit_connection = Mock(side_effect=AssertionError("Must not retry an unavailable database"))

    def unavailable_db():
        raise error

    with monkeypatch.context() as patch:
        patch.setattr(main, "SessionLocal", audit_connection)
        main.app.dependency_overrides[get_db] = unavailable_db
        try:
            result = client.get("/api/auth/me")
            assert result.status_code == 503
            assert result.headers["Retry-After"] == "5"
            assert result.headers["Cache-Control"] == "no-store"
            assert "temporarily unavailable" in result.json()["detail"]
            assert "private" not in result.text
            assert "private" not in caplog.text
            audit_connection.assert_not_called()
            assert client.get("/api/health/live").status_code == 200
        finally:
            main.app.dependency_overrides.pop(get_db, None)
    # A temporary service outage must not clear a valid login cookie.
    assert client.get("/api/auth/me").status_code == 200


def test_anonymous_session_check_does_not_wait_for_an_audit_connection(client, monkeypatch):
    audit_connection = Mock(side_effect=AssertionError("Unexpected database connection"))
    monkeypatch.setattr(main, "SessionLocal", audit_connection)
    assert client.get("/api/auth/me").status_code == 401
    audit_connection.assert_not_called()


def test_postgres_connection_times_out_when_tcp_peer_never_completes_handshake():
    """Exercise the real driver timeout without requiring a PostgreSQL server."""
    stop = Event()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(8)

        def stalled_peer():
            with listener.accept()[0]:
                stop.wait(12)

        thread = Thread(target=stalled_peer, daemon=True)
        thread.start()
        port = listener.getsockname()[1]
        database = create_database_engine(
            f"postgresql+psycopg://demo:demo@127.0.0.1:{port}/demo?sslmode=disable"
        )
        started = monotonic()
        try:
            with pytest.raises(OperationalError):
                with database.connect():
                    pytest.fail("A silent TCP peer is not a ready database")
            assert monotonic() - started < 9
        finally:
            stop.set()
            database.dispose()
            thread.join(timeout=2)


def test_startup_reuses_ready_database_without_running_docker():
    module = load("prepare_backend")
    run = Mock()
    assert module.prepare_backend(
        "postgresql+psycopg://demo@localhost:5433/demo", lambda: True, run
    ) == 0
    run.assert_not_called()


def test_startup_starts_existing_local_database_and_checks_connection_again():
    module = load("prepare_backend")
    run = Mock()
    probe = Mock(side_effect=[False, True])
    assert module.prepare_backend("postgresql+psycopg://demo@localhost:5433/demo", probe, run) == 0
    command = run.call_args.args[0]
    assert "--no-recreate" in command
    assert "--wait" in command
    assert command[-1] == "db"
    assert run.call_args.kwargs["timeout"] <= 60
    assert probe.call_count == 2


@pytest.mark.parametrize(
    "error", [FileNotFoundError("private"), subprocess.TimeoutExpired("private", 55)]
)
def test_startup_stops_safely_when_docker_is_unavailable(error, capsys):
    module = load("prepare_backend")
    run = Mock(side_effect=error)
    assert module.prepare_backend(
        "postgresql+psycopg://demo@localhost:5433/demo", lambda: False, run
    ) == 1
    output = capsys.readouterr().out
    assert "Docker Desktop" in output
    assert "private" not in output


def test_startup_stops_if_container_health_does_not_match_actual_database_connection():
    module = load("prepare_backend")
    assert module.prepare_backend(
        "postgresql+psycopg://demo@localhost:5433/demo", lambda: False, Mock()
    ) == 1


@pytest.mark.parametrize(
    "url", ["postgresql+psycopg://demo@remote.example:5433/demo", "sqlite:///missing/test.db"]
)
def test_startup_does_not_launch_local_compose_for_a_different_database(url):
    module = load("prepare_backend")
    run = Mock()
    assert module.prepare_backend(url, lambda: False, run) == 1
    run.assert_not_called()
