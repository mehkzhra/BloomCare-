import importlib.util
import sys
from pathlib import Path

import pytest


def load(name):
    path = Path(__file__).resolve().parents[2] / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_configure_preserves_settings_and_hides_key(tmp_path, monkeypatch, capsys):
    module = load("configure_integrations")
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=existing\nJWT_SECRET=existing-secret\n")
    monkeypatch.setattr(module, "ENV", env)
    monkeypatch.setattr(module, "getpass", lambda prompt: "fake-key-for-test-only")
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    monkeypatch.setattr(sys, "argv", ["configure_integrations.py", "groq"])
    module.main()
    assert "DATABASE_URL=existing" in env.read_text()
    assert "JWT_SECRET=existing-secret" in env.read_text()
    assert "fake-key-for-test-only" not in capsys.readouterr().out


def test_restore_requires_explicit_confirmation(tmp_path, monkeypatch):
    module = load("database_backup")
    backup = tmp_path / "backup.dump"
    backup.write_bytes(b"DEMO")
    monkeypatch.setattr(sys, "argv", ["database_backup.py", "restore", "--file", str(backup)])
    calls = []
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(SystemExit, match="confirm-restore"):
        module.main()
    assert calls == []


def test_backup_refuses_overwriting_existing_file(tmp_path, monkeypatch):
    module = load("database_backup")
    backup = tmp_path / "backup.dump"
    backup.write_bytes(b"PRESERVE")
    monkeypatch.setattr(sys, "argv", ["database_backup.py", "backup", "--file", str(backup)])
    with pytest.raises(SystemExit, match="not overwritten"):
        module.main()
    assert backup.read_bytes() == b"PRESERVE"


@pytest.mark.parametrize(
    "choice,urls",
    [("1", None), ("2", "stun:example.invalid:3478"), ("3", "turns:example.invalid:5349")],
)
def test_video_wizard_preserves_existing_env_and_hides_turn_credentials(
    tmp_path, monkeypatch, capsys, choice, urls
):
    module = load("configure_integrations")
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=existing\nJWT_SECRET=existing-secret\n")
    monkeypatch.setattr(module, "ENV", env)
    answers = iter([choice] + ([urls] if urls else []))
    secrets = iter(["private-turn-user", "private-turn-password"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(module, "getpass", lambda prompt: next(secrets))
    monkeypatch.setattr(sys, "argv", ["configure_integrations.py", "webrtc"])
    module.main()
    content = env.read_text()
    assert "DATABASE_URL=existing" in content and "JWT_SECRET=existing-secret" in content
    assert "WEBRTC_ICE_SERVERS=" in content
    printed = capsys.readouterr().out
    assert "private-turn-user" not in printed and "private-turn-password" not in printed


def test_invalid_video_wizard_input_leaves_existing_env_untouched(tmp_path, monkeypatch):
    module = load("configure_integrations")
    env = tmp_path / ".env"
    env.write_text('WEBRTC_ICE_SERVERS="[]"\nJWT_SECRET=preserve\n')
    original = env.read_bytes()
    answers = iter(["2", "https://example.invalid"])
    monkeypatch.setattr(module, "ENV", env)
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(sys, "argv", ["configure_integrations.py", "webrtc"])
    with pytest.raises(SystemExit, match="Invalid ICE"):
        module.main()
    assert env.read_bytes() == original


def test_email_wizard_preserves_private_runtime_and_hides_smtp_values(
    tmp_path, monkeypatch, capsys
):
    module = load("configure_integrations")
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=preserved\nJWT_SECRET=preserved-secret\n")
    monkeypatch.setattr(module, "ENV", env)
    answers = iter(
        [
            "https://care.example.com",
            "smtp.example.invalid",
            "starttls",
            "587",
            "noreply@example.com",
            "y",
        ]
    )
    secrets = iter(["private-smtp-user", "private-smtp-credential"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(module, "getpass", lambda _: next(secrets))
    monkeypatch.setattr(sys, "argv", ["configure_integrations.py", "email"])
    module.main()
    content = env.read_text()
    assert "DATABASE_URL=preserved" in content and "JWT_SECRET=preserved-secret" in content
    assert 'AUTH_REQUIRE_EMAIL_VERIFICATION="true"' in content
    printed = capsys.readouterr().out
    assert "private-smtp-user" not in printed
    assert "private-smtp-credential" not in printed


def test_brevo_wizard_preserves_database_and_existing_smtp_and_hides_key(
    tmp_path, monkeypatch, capsys
):
    module = load("configure_integrations")
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=preserved\nJWT_SECRET=preserved-secret\nSMTP_HOST=preserved\n")
    monkeypatch.setattr(module, "ENV", env)
    answers = iter(["https://care.example.com", "owner@example.com", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(module, "getpass", lambda _: "private-brevo-credential")
    monkeypatch.setattr(sys, "argv", ["configure_integrations.py", "email-brevo"])
    module.main()
    content = env.read_text()
    assert "DATABASE_URL=preserved" in content and "SMTP_HOST=preserved" in content
    assert 'EMAIL_PROVIDER="brevo"' in content
    assert 'AUTH_REQUIRE_EMAIL_VERIFICATION="true"' in content
    assert "private-brevo-credential" not in capsys.readouterr().out


@pytest.mark.parametrize("fails", [False, True])
def test_restore_test_uses_only_a_generated_database_and_drops_it(tmp_path, monkeypatch, fails):
    module = load("database_backup")
    dump = tmp_path / "database.dump"
    dump.write_bytes(b"PGDMP-test-only")
    monkeypatch.setattr(sys, "argv", ["database_backup.py", "restore-test", "--file", str(dump)])
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        if fails and any("pg_restore" in part for part in command):
            raise module.subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(module.subprocess, "run", run)
    if fails:
        with pytest.raises(module.subprocess.CalledProcessError):
            module.main()
    else:
        module.main()
    commands = [" ".join(call[0]) for call in calls]
    assert "createdb" in commands[0] and "dropdb" in commands[-1]
    assert all("bloomcare_restore_test_" in cmd for cmd in commands)
    assert all("--clean" not in cmd for cmd in commands)
    assert all('"$POSTGRES_DB"' not in cmd for cmd in commands)
    if not fails:
        assert "octet_length(content)" in commands[-2]
    assert dump.read_bytes() == b"PGDMP-test-only"
