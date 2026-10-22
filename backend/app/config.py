from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: str
    jwt_secret: str = Field(min_length=48)
    jwt_minutes: int = Field(default=30, ge=5, le=120)
    cookie_secure: bool = False
    public_app_url: str = "http://127.0.0.1:5173"
    auth_require_email_verification: bool = False
    auth_proxy_header: Literal["none", "render-cloudflare"] = "none"
    email_provider: Literal["smtp", "brevo"] = "smtp"
    brevo_api_key: SecretStr | None = None
    email_from: EmailStr | None = None
    frontend_static_dir: str | None = None
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: EmailStr | None = None
    smtp_security: Literal["starttls", "ssl"] = "starttls"
    bloomcare_research_assessments: bool = False
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-20b"
    twilio_account_sid: str | None = Field(default=None, pattern=r"^AC[0-9a-fA-F]{32}$")
    twilio_auth_token: SecretStr | None = None
    twilio_whatsapp_from: str | None = None
    twilio_allowed_recipients: str = ""
    twilio_content_sid: str | None = Field(default=None, pattern=r"^HX[0-9a-fA-F]{32}$")
    webrtc_ice_servers: str = "[]"
    allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
    )

    @field_validator("public_app_url")
    @classmethod
    def validate_public_url(cls, value):
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"})
        ):
            raise ValueError("Use an HTTPS application origin, or local HTTP for development")
        return value.rstrip("/")

    @model_validator(mode="after")
    def require_verification_delivery(self):
        mail_values = [
            self.email_from,
            self.brevo_api_key.get_secret_value() if self.brevo_api_key else None,
        ] if self.email_provider == "brevo" else [
            self.smtp_host,
            self.smtp_from,
            self.smtp_username,
            self.smtp_password.get_secret_value() if self.smtp_password else None,
        ]
        if self.auth_require_email_verification and not all(
            value and str(value).strip() for value in mail_values
        ):
            raise ValueError("Configure the selected email provider before requiring verification")
        return self

    @field_validator("jwt_secret")
    @classmethod
    def require_real_secret(cls, value: str) -> str:
        if "CHANGE_ME" in value or len(set(value)) < 12:
            raise ValueError("Generate a JWT secret using scripts/setup.py")
        return value

    @field_validator("database_url")
    @classmethod
    def restrict_database(cls, value: str) -> str:
        # Hosting providers supply PostgreSQL URLs without SQLAlchemy's driver suffix.
        # Preserve the credentials, query (including sslmode), and database verbatim.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                value = "postgresql+psycopg://" + value[len(prefix):]
                break
        if not value.startswith(("postgresql+psycopg://", "sqlite://")):
            raise ValueError("Use PostgreSQL+psycopg, or SQLite for isolated tests")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
