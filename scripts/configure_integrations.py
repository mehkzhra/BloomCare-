"""Configure optional server-side integrations without printing credentials."""

import argparse
import json
from getpass import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "backend" / ".env"


def write_values(values):
    if not ENV.exists():
        raise SystemExit("Complete foundation setup first; backend/.env is missing.")
    lines = ENV.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if not any(line.startswith(key + "=") for key in values)]
    kept.extend(key + "=" + json.dumps(value) for key, value in values.items() if value is not None)
    import os
    import stat
    import tempfile

    mode = stat.S_IMODE(ENV.stat().st_mode)
    handle, temporary = tempfile.mkstemp(prefix=".integration-", dir=ENV.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write("\n".join(kept) + "\n")
        os.chmod(temporary, mode)
        os.replace(temporary, ENV)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description="Configure BloomCare integrations")
    parser.add_argument(
        "integration", choices=["groq", "groq-model", "webrtc", "email", "email-brevo"]
    )
    parser.add_argument(
        "--model", help="Groq model ID; use groq-model to keep the existing API key"
    )
    args = parser.parse_args()
    if args.integration in {"groq", "groq-model"}:
        values = {}
        if args.integration == "groq":
            values["GROQ_API_KEY"] = getpass("Groq API key (hidden; blank disables): ").strip()
        model = args.model or input("Groq model ID [openai/gpt-oss-20b]: ").strip()
        model = model or "openai/gpt-oss-20b"
        if any(c.isspace() for c in model):
            raise SystemExit("Model ID must not contain whitespace.")
        values["GROQ_MODEL"] = model
        write_values(values)
    elif args.integration == "email-brevo":
        import sys

        from pydantic import EmailStr, TypeAdapter

        sys.path.insert(0, str(ROOT / "backend"))
        from app.config import Settings

        url = input("Application origin [http://127.0.0.1:5173]: ").strip()
        sender = input("Email address verified in Brevo Senders: ").strip()
        key = getpass("Brevo API key (hidden, not SMTP key): ").strip()
        required = input("Require verified email at sign-in? [y/N]: ").strip().lower()
        try:
            url = Settings.validate_public_url(url or "http://127.0.0.1:5173")
            sender = str(TypeAdapter(EmailStr).validate_python(sender))
            if not key or required not in {"", "y", "n"}:
                raise ValueError("Invalid email configuration")
        except ValueError:
            raise SystemExit(
                "Invalid email settings. Existing configuration was preserved."
            ) from None
        write_values({
            "PUBLIC_APP_URL": url,
            "EMAIL_PROVIDER": "brevo",
            "EMAIL_FROM": sender,
            "BREVO_API_KEY": key,
            "AUTH_REQUIRE_EMAIL_VERIFICATION": "true" if required == "y" else "false",
        })
    elif args.integration == "email":
        import sys

        from pydantic import EmailStr, TypeAdapter

        sys.path.insert(0, str(ROOT / "backend"))
        from app.config import Settings

        url = input("Application origin [http://127.0.0.1:5173]: ").strip()
        url = url or "http://127.0.0.1:5173"
        host = input("SMTP host supplied by your email provider: ").strip()
        security = input("SMTP security: starttls or ssl [starttls]: ").strip() or "starttls"
        port_text = input("SMTP port [587 for STARTTLS, 465 for SSL]: ").strip()
        username = getpass("SMTP username (hidden): ").strip()
        password = getpass("SMTP app password or credential (hidden): ").strip()
        sender = input("Approved sender email address: ").strip()
        required = input("Require verified email at sign-in? [y/N]: ").strip().lower()
        try:
            url = Settings.validate_public_url(url)
            sender = str(TypeAdapter(EmailStr).validate_python(sender))
            port = int(port_text or ("465" if security == "ssl" else "587"))
            if (
                not host
                or any(c.isspace() for c in host)
                or security not in {"starttls", "ssl"}
                or not 1 <= port <= 65535
                or not username
                or not password
                or required not in {"", "y", "n"}
            ):
                raise ValueError("Invalid email configuration")
        except ValueError:
            raise SystemExit(
                "Invalid email settings. Existing configuration was preserved."
            ) from None
        write_values(
            {
                "PUBLIC_APP_URL": url,
                "EMAIL_PROVIDER": "smtp",
                "SMTP_HOST": host,
                "SMTP_PORT": str(port),
                "SMTP_SECURITY": security,
                "SMTP_USERNAME": username,
                "SMTP_PASSWORD": password,
                "SMTP_FROM": sender,
                "AUTH_REQUIRE_EMAIL_VERIFICATION": "true" if required == "y" else "false",
            }
        )
    else:
        import sys

        sys.path.insert(0, str(ROOT / "backend"))
        from app.ice_config import parse_ice_servers

        print("Video: 1 direct, 2 STUN discovery, 3 TURN relay, 4 paste ICE JSON")
        choice = input("Choose setup [1]: ").strip() or "1"
        if choice == "1":
            raw = "[]"
        elif choice in {"2", "3"}:
            urls = [
                u.strip()
                for u in input("Provider STUN/TURN URL(s), comma separated: ").split(",")
                if u.strip()
            ]
            server = {"urls": urls}
            if choice == "3":
                server["username"] = getpass("TURN username (hidden): ").strip()
                server["credential"] = getpass("TURN password (hidden): ").strip()
                if not server["username"] or not server["credential"]:
                    raise SystemExit("Enter the TURN credentials supplied by your provider.")
            raw = json.dumps([server])
        elif choice == "4":
            raw = getpass("ICE servers JSON (hidden): ").strip()
        else:
            raise SystemExit("Choose 1, 2, 3 or 4. No configuration was changed.")
        try:
            data = parse_ice_servers(raw)
            urls = [
                u
                for item in data
                for u in ([item["urls"]] if isinstance(item["urls"], str) else item["urls"])
            ]
            if choice == "2" and any(not u.startswith("stun:") for u in urls):
                raise ValueError("Use STUN URLs for discovery mode")
            if choice == "3" and not any(u.startswith(("turn:", "turns:")) for u in urls):
                raise ValueError("At least one TURN URL is required for relay mode")
        except ValueError:
            raise SystemExit("Invalid ICE server configuration.") from None
        write_values({"WEBRTC_ICE_SERVERS": json.dumps(data)})
    print("Integration configuration saved. Restart the backend. Credentials were not printed.")


if __name__ == "__main__":
    main()
