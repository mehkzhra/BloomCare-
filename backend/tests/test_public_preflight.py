import pytest
from app.config import Settings, get_settings
from app.deployment_checks import configuration_checks
from pydantic import SecretStr, ValidationError


def test_public_preflight_requires_actual_configuration_without_sending(monkeypatch):
    settings = get_settings()
    initial = configuration_checks(settings)
    assert initial["https_application_origin"] is False
    assert initial["email_verification_required"] is False
    for key, value in {
        "public_app_url": "https://care.example.com",
        "allowed_origins": "https://care.example.com",
        "cookie_secure": True,
        "auth_require_email_verification": True,
        "smtp_host": "smtp.example.invalid",
        "smtp_username": "private-user",
        "smtp_password": SecretStr("private-mail-password"),
        "smtp_from": "noreply@example.com",
        "database_url": "postgresql+psycopg://user:password@db:5432/bloomcare",
        "bloomcare_research_assessments": True,
        "groq_api_key": SecretStr("private-groq-key"),
        "webrtc_ice_servers": (
            '[{"urls":"turn:relay.example.invalid:3478",'
            '"username":"private-turn-user","credential":"private-turn-password"}]'
        ),
    }.items():
        monkeypatch.setattr(settings, key, value)
    assert all(configuration_checks(settings).values())
    monkeypatch.setattr(
        settings, "allowed_origins", "https://care.example.com,http://localhost:5173"
    )
    assert configuration_checks(settings)["exact_same_https_origin"] is False


def test_missing_mail_cannot_enable_enforcement_or_print_config_secrets():
    with pytest.raises(ValidationError) as error:
        Settings(
            _env_file=None,
            database_url="sqlite://",
            jwt_secret="private-secret-abcdefghijklmnopqrstuvwxyz-0123456789",
            auth_require_email_verification=True,
            smtp_password="private-mail-value",
        )
    assert "private-mail-value" not in str(error.value)
