"""Check Groq using fixed test text, without reading or sending patient data."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(settings):
    from app.groq_service import GroqFailure, available_models, complete

    if not settings.groq_api_key:
        print("GROQ_NOT_CONFIGURED: Run scripts\\configure-integrations.cmd groq")
        return 1
    print("Testing Groq with fixed test text only. No patient records are sent.")
    try:
        models = available_models(settings)
        if settings.groq_model not in models:
            print("GROQ_MODEL_UNAVAILABLE: The configured model is not listed by Groq.")
            if "openai/gpt-oss-20b" in models:
                print("Listed alternative: openai/gpt-oss-20b")
            print("Set a model: scripts\\configure-integrations.cmd groq-model --model ID")
            return 1
        # Listing a model alone does not prove chat permission; make one test request.
        complete(settings, [{"role": "user", "content": "Reply briefly: BloomCare connection OK."}])
    except GroqFailure as error:
        status = f" (Groq HTTP {error.upstream_status})" if error.upstream_status else ""
        print(error.code + status + ": " + error.message)
        return 1
    print("Groq connection test passed. A real final answer was received.")
    print("Restart the backend after changing its settings, then test Assistant in BloomCare.")
    return 0


def main():
    os.chdir(ROOT / "backend")
    sys.path.insert(0, str(ROOT / "backend"))
    try:
        from app.config import get_settings

        settings = get_settings()
    except Exception:
        print("SETTINGS_UNAVAILABLE: Check backend/.env. Credentials were not printed.")
        return 1
    return check(settings)


if __name__ == "__main__":
    raise SystemExit(main())
