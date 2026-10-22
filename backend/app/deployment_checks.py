"""Non-secret public-configuration preflight; no provider calls, messages or writes."""

import json

from sqlalchemy import inspect, text

from app.account_email import configured
from app.config import get_settings
from app.database import engine
from app.integration_status import video_status
from app.maternal_model import get_maternal_model
from app.pe_model import get_pe_model


def configuration_checks(settings):
    origins = [x.strip() for x in settings.allowed_origins.split(",") if x.strip()]
    return {
        "https_application_origin": settings.public_app_url.startswith("https://"),
        "secure_cookie": settings.cookie_secure,
        "exact_same_https_origin": origins == [settings.public_app_url],
        "email_verification_required": settings.auth_require_email_verification,
        "account_email_configured": configured(settings),
        "postgresql": settings.database_url.startswith("postgresql+psycopg://"),
        "assessments_enabled": settings.bloomcare_research_assessments,
        "groq_configured": bool(settings.groq_api_key),
        "turn_relay_configured": video_status(settings) == "RELAY_CONFIGURED",
    }


def main():
    checks = configuration_checks(get_settings())
    try:
        with engine.connect() as db:
            checks["database_schema_current"] = db.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "0013_account_security" and {"email_action_tokens", "auth_rate_buckets"}.issubset(
                inspect(engine).get_table_names()
            )
    except Exception:
        checks["database_schema_current"] = False
    for name, loader in [
        ("registered_maternal_model", get_maternal_model),
        ("pinned_pe_model", get_pe_model),
    ]:
        try:
            loader()
            checks[name] = True
        except Exception:
            checks[name] = False
    print(
        json.dumps(
            {
                "configuration_checks": checks,
                "passed": all(checks.values()),
                "provider_delivery_and_media_verified": False,
                "clinical_validation": "Not established by this preflight",
            },
            indent=2,
        )
    )
    if not all(checks.values()):
        raise SystemExit(
            "Complete the false configuration checks before public acceptance testing."
        )
    print("Configuration preflight passed. Complete the live acceptance checklist before handover.")


if __name__ == "__main__":
    main()
