"""Private cloud export keeps secrets intact without copying local-only settings."""

import importlib.util
from pathlib import Path

import pytest
from dotenv import dotenv_values

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/prepare_cloud_settings.py"
SPEC = importlib.util.spec_from_file_location("bloomcare_cloud_settings", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def values(**overrides):
    arguments = {
        "source": {
            "EMAIL_PROVIDER": "brevo", "EMAIL_FROM": "sender@example.com",
            "BREVO_API_KEY": 'synthetic-key-with-$-and-"-characters',
            "GROQ_API_KEY": "synthetic-groq-key", "GROQ_MODEL": "existing-provider-model",
            "WEBRTC_ICE_SERVERS": '[{"urls":"stun:stun.example.com:3478"}]',
            "DATABASE_URL": "local-database-must-not-be-copied",
            "JWT_SECRET": "local-session-key-must-not-be-copied",
            "TWILIO_AUTH_TOKEN": "unrequested-provider-must-not-be-copied",
        },
        "origin": "https://bloomcare-example.code.run/",
        "database_url": "postgresql://owner:synthetic%40password@db.example.neon.tech/db?sslmode=require",
        "email": "Owner@example.com", "name": "Project Owner",
    }
    arguments.update(overrides)
    return MODULE.cloud_values(**arguments)


def test_export_round_trips_keys_video_and_ssl_without_publishing_local_configuration(tmp_path):
    settings = values()
    target = tmp_path / ".env.northflank"
    MODULE.save_private(settings, target)
    loaded = dotenv_values(target, interpolate=False)
    assert loaded == settings
    assert loaded["PUBLIC_APP_URL"] == loaded["ALLOWED_ORIGINS"]
    assert loaded["BOOTSTRAP_ADMIN_EMAIL"] == "owner@example.com"
    assert loaded["GROQ_MODEL"] == "existing-provider-model"
    assert loaded["COOKIE_SECURE"] == loaded["AUTH_REQUIRE_EMAIL_VERIFICATION"] == "true"
    assert loaded["AUTH_PROXY_HEADER"] == "none"
    assert "TWILIO_AUTH_TOKEN" not in loaded
    assert "local-" not in target.read_text()
    assert len(loaded["JWT_SECRET"]) >= 48
    with pytest.raises(FileExistsError):
        MODULE.save_private(values(), target)
    assert dotenv_values(target, interpolate=False)["JWT_SECRET"] == loaded["JWT_SECRET"]


@pytest.mark.parametrize("overrides", [
    {"origin": "http://insecure.example.com"},
    {"origin": "https://bloomcare-example.code.run/account"},
    {"database_url": "postgresql://user:synthetic@localhost/db?sslmode=require"},
    {"database_url": "postgresql://user:synthetic@host.neon.tech/db"},
    {"database_url": "psql 'postgresql://user:synthetic@host.neon.tech/db?sslmode=require'"},
    {"email": "not-an-email"},
    {"source": {"GROQ_API_KEY": "synthetic-key"}},
])
def test_invalid_cloud_settings_fail_without_echoing_credentials(overrides):
    with pytest.raises(ValueError) as error:
        values(**overrides)
    assert "synthetic" not in str(error.value)
