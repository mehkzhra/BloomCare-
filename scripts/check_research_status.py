"""Read the configured local model status without changing settings or the database."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import get_settings  # noqa: E402
from app.maternal_model import (  # noqa: E402
    MODEL_DIR,
    TRUST_PATH,
    ModelUnavailable,
    get_maternal_model,
)


def configured_status():
    settings = get_settings()
    result = {
        "scope": "local configuration; restart a running backend after activation",
        "research_enabled": settings.bloomcare_research_assessments,
        "session_minutes": settings.jwt_minutes,
        "model_files_present": all(
            (MODEL_DIR / name).is_file() for name in ("manifest.json", "pipeline.joblib")
        ),
        "registration_present": TRUST_PATH.is_file(),
        "pregnancy_model_ready": False,
        "pe_model_ready": False,
        "model_version": None,
    }
    try:
        model = get_maternal_model()
    except ModelUnavailable:
        if not settings.bloomcare_research_assessments:
            result["reason"] = "Research assessment is disabled in the backend configuration."
        elif not result["model_files_present"] or not result["registration_present"]:
            result["reason"] = "The locally trained model or its verified registration is missing."
        else:
            result["reason"] = "Model verification failed. Check the assessment update checkpoint."
    else:
        result["pregnancy_model_ready"] = True
        result["model_version"] = model.manifest["version"]
        result["reason"] = "Verified local research model is available; PE remains unavailable."
    return result


def main():
    os.chdir(BACKEND)
    try:
        result = configured_status()
    except Exception as error:
        print(
            f"Local status check failed ({type(error).__name__}). "
            "Check the backend configuration and dependencies; no settings were changed.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result["pregnancy_model_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
