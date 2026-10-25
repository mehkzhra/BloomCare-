"""Cloud startup: verify models, migrate, bootstrap once, and serve one HTTPS origin."""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configure_environment(environment):
    origin = environment.get("PUBLIC_APP_URL") or environment.get("RENDER_EXTERNAL_URL", "")
    if origin:
        environment.setdefault("PUBLIC_APP_URL", origin)
        environment.setdefault("ALLOWED_ORIGINS", origin)
    if environment.get("RENDER") == "true":
        environment.setdefault("AUTH_PROXY_HEADER", "render-cloudflare")
    # Render's generated 256-bit base64 seed is 44 characters. Domain-separated
    # SHA-512 derives the stable session key without relaxing the app's key policy.
    if "JWT_SECRET" not in environment:
        seed = environment.get("JWT_SECRET_SEED", "")
        if len(seed) < 32 or len(set(seed)) < 12:
            raise ValueError("A generated cloud session seed is required")
        environment["JWT_SECRET"] = hashlib.sha512(
            ("BloomCare cloud sessions v1:" + seed).encode()
        ).hexdigest()
    environment.setdefault("FRONTEND_STATIC_DIR", str(ROOT / "frontend/dist"))


def main():
    os.chdir(ROOT / "backend")
    sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]
    try:
        configure_environment(os.environ)
        from app.config import get_settings

        settings = get_settings()
        if (
            not settings.database_url.startswith("postgresql+psycopg://")
            or not settings.public_app_url.startswith("https://")
            or not settings.cookie_secure
            or not settings.auth_require_email_verification
            or settings.allowed_origins != settings.public_app_url
        ):
            raise ValueError("Complete the secure cloud environment settings")
        port = int(os.environ.get("PORT", "10000"))
        if not 1 <= port <= 65535:
            raise ValueError("Invalid port")
        from deploy.prepare_cloud_model import verify_runtime_models

        verify_runtime_models()
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
        from app.cloud_setup import bootstrap_admin

        bootstrap_admin(
            os.environ.get("BOOTSTRAP_ADMIN_EMAIL"),
            os.environ.get("BOOTSTRAP_ADMIN_NAME", "BloomCare Administrator"),
        )
    except Exception as error:
        # Never print a database URL, provider key, or a validation input.
        raise SystemExit(
            f"Cloud startup stopped ({type(error).__name__}). "
            "Check the private model mounts and deployment settings."
        ) from None
    os.execv(sys.executable, [
        sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0",
        "--port", str(port), "--workers", "1", "--no-access-log",
        "--no-proxy-headers",
    ])


if __name__ == "__main__":
    main()
