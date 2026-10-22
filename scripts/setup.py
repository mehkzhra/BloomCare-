"""Create unique local development secrets without overwriting existing configuration."""

import secrets
from pathlib import Path
from urllib.parse import quote

root = Path(__file__).resolve().parents[1]
backend_env = root / "backend" / ".env"
compose_env = root / ".env"

if backend_env.exists() or compose_env.exists():
    raise SystemExit("Setup stopped: .env already exists. Keep it or move it before running setup.")

password = secrets.token_urlsafe(24)
secret = secrets.token_urlsafe(48)
compose_env.write_text(
    f"POSTGRES_DB=bloomcare\nPOSTGRES_USER=bloomcare\nPOSTGRES_PASSWORD={password}\n",
    encoding="utf-8",
)
backend_env.write_text(
    f"DATABASE_URL=postgresql+psycopg://bloomcare:{quote(password)}@localhost:5433/bloomcare\n"
    f"JWT_SECRET={secret}\nJWT_MINUTES=30\nCOOKIE_SECURE=false\n"
    "ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:8000,http://127.0.0.1:8000\n",
    encoding="utf-8",
)
print("Created development configuration. Database port: 5433. Secrets were not printed.")
