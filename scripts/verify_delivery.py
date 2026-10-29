"""Inspect installed delivery prerequisites without displaying keys or personal records."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

from sqlalchemy import inspect, text  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import engine  # noqa: E402
from app.integration_status import service_configuration  # noqa: E402
from app.pe_explanation import explainer  # noqa: E402
from app.pe_model import get_pe_model  # noqa: E402
from app.whatsapp_service import configured  # noqa: E402


def main():
    required = {
        "assessment_care_plans",
        "clinical_reviews",
        "clinical_review_events",
        "follow_up_proposals",
        "whatsapp_alerts",
        "email_action_tokens",
        "auth_rate_buckets",
    }
    with engine.connect() as db:
        revision = db.scalar(text("SELECT version_num FROM alembic_version"))
    if revision != "0013_account_security" or not required.issubset(
        inspect(engine).get_table_names()
    ):
        raise SystemExit("The delivery database upgrade has not completed. Run update-final.cmd.")
    columns = {column["name"] for column in inspect(engine).get_columns("assessments")}
    if not {"removed_at", "removal_reason"}.issubset(columns):
        raise SystemExit("The assessment removal upgrade is incomplete. Run update-final.cmd.")
    health_columns = {column["name"] for column in inspect(engine).get_columns("health_records")}
    if not {"removed_at", "removal_reason"}.issubset(health_columns):
        raise SystemExit("Health-record removal upgrade is incomplete. Run update-final.cmd.")
    frontend_version = json.loads((ROOT / "frontend/package.json").read_text())["version"]
    if frontend_version != "1.3.0":
        raise SystemExit("Mixed application files detected. Extract the combined v1.3.0 ZIP again.")
    get_pe_model()
    explainer()
    for name in [
        "jspdf.umd.min.js",
        "BloomSans.ttf",
        "jspdf.LICENSE",
        "BloomSans.LICENSE",
        "NotoNaskhArabic-Regular.ttf",
        "NotoNaskhArabic.LICENSE",
    ]:
        if not (ROOT / "frontend/public/vendor" / name).is_file():
            raise SystemExit("Missing PDF asset: " + name)
    comparisons = json.loads((ROOT / "ml/training_reports/v1.0.0/comparison.json").read_text())
    pe_report = json.loads(
        (ROOT / "ml/training_reports/pe-v1.0.0/pe-retraining-report.json").read_text()
    )
    if (
        len(comparisons["comparisons"]) != 3
        or comparisons["active_model_changed"]
        or comparisons["split"]["overlapping_groups"] != 0
        or pe_report["overlap_feature_groups"] != 0
    ):
        raise SystemExit("The installed training evidence does not match this release.")
    for name in [
        "workspaces.jsx",
        "experience.css",
        "training-evidence.jsx",
        "assessment-removal.jsx",
        "privacy-content.js",
        "release-check.jsx",
        "service-configuration.jsx",
        "video-readiness.jsx",
    ]:
        if not (ROOT / "frontend/src" / name).is_file():
            raise SystemExit("Missing workspace asset: " + name)
    settings = get_settings()
    result = {
        "version": "1.3.0",
        "database_revision": revision,
        "frontend_version": frontend_version,
        "pe_forest_and_shap_verified": True,
        "training_evidence_present": True,
        "role_workspaces_installed": True,
        "care_plan_provider_configured": bool(settings.groq_api_key),
        "whatsapp_provider_configured": configured(settings),
        "secure_cookie_enabled": settings.cookie_secure,
        "video_connection_mode": service_configuration(settings)["video"]["status"],
    }
    print(json.dumps(result, indent=2))
    print(
        "Local prerequisites verified. "
        "Provider delivery, cameras, HTTPS and recovery need live checks."
    )


if __name__ == "__main__":
    main()
