"""Credential-free configuration diagnostics; no implicit provider calls or messages."""

from fastapi import APIRouter, Depends, HTTPException

from app.account_email import configured as email_configured
from app.config import get_settings
from app.ice_config import parse_ice_servers
from app.models import User
from app.security import current_user, require_role
from app.whatsapp_service import configuration_issues

router = APIRouter(prefix="/api")


def video_status(settings):
    try:
        servers = parse_ice_servers(settings.webrtc_ice_servers)
    except ValueError:
        return "INVALID"
    urls = [
        url
        for item in servers
        for url in ([item["urls"]] if isinstance(item["urls"], str) else item["urls"])
    ]
    if any(url.startswith(("turn:", "turns:")) for url in urls):
        return "RELAY_CONFIGURED"
    return "STUN_CONFIGURED" if urls else "DIRECT_ONLY"


def service_configuration(settings=None):
    settings = settings or get_settings()
    video = video_status(settings)
    missing = configuration_issues(settings)
    groq = bool(settings.groq_api_key and settings.groq_api_key.get_secret_value().strip())
    return {
        "email": {
            "status": "CONFIGURED" if email_configured(settings) else "NOT_CONFIGURED",
            "label": "Email settings saved" if email_configured(settings) else "Account email off",
            "summary": (
                "Verification and password-reset email settings are saved. "
                "Request a link from the sign-in page to check actual delivery."
            )
            if email_configured(settings)
            else ("Configure an HTTPS email provider or TLS SMTP for account emails."),
            "verification_required": settings.auth_require_email_verification,
            "missing": []
            if email_configured(settings)
            else ["BREVO_API_KEY", "EMAIL_FROM"] if settings.email_provider == "brevo" else [
                "SMTP_HOST",
                "SMTP_PORT",
                "SMTP_USERNAME",
                "SMTP_PASSWORD",
                "SMTP_FROM",
            ],
            "command": "scripts\\configure-integrations.cmd " + (
                "email-brevo" if settings.email_provider == "brevo" else "email"
            ),
            "provider": settings.email_provider,
            "verified_live": False,
        },
        "groq": {
            "status": "CONFIGURED" if groq else "NOT_CONFIGURED",
            "label": "Key saved" if groq else "Assistant off",
            "summary": (
                "A server key is saved. Open the assistant and submit a consented question "
                "to check the provider."
            )
            if groq
            else "Save a Groq API key to enable assistant questions and care guides.",
            "missing": [] if groq else ["GROQ_API_KEY"],
            "command": "scripts\\configure-integrations.cmd groq",
            "verified_live": False,
        },
        "whatsapp": {
            "status": "NOT_CONFIGURED" if missing else "CONFIGURED",
            "label": "Automatic alerts off" if missing else "Alert settings saved",
            "summary": (
                "Manual PDF sharing is available. Automatic alerts need an approved sender "
                "and opted-in contacts."
            )
            if missing
            else (
                "Sender and contacts are saved. Check the sandbox join or approved template "
                "before a consented alert."
            ),
            "missing": missing,
            "command": "scripts\\configure-whatsapp.cmd",
            "manual_sharing_available": True,
            "template_configured": bool(settings.twilio_content_sid),
            "verified_live": False,
        },
        "video": {
            "status": video,
            "label": {
                "DIRECT_ONLY": "Direct connection mode",
                "STUN_CONFIGURED": "STUN settings saved",
                "RELAY_CONFIGURED": "Relay settings saved",
                "INVALID": "Fix network settings",
            }[video],
            "summary": {
                "DIRECT_ONLY": (
                    "Calls can use direct connections. For different networks or restrictive "
                    "firewalls, configure a TURN relay and test both devices."
                ),
                "STUN_CONFIGURED": (
                    "STUN settings are saved. Some networks still need a TURN relay. "
                    "Test a patient and doctor call on separate devices."
                ),
                "RELAY_CONFIGURED": (
                    "TURN relay settings are saved. Test a patient and doctor call "
                    "to verify credentials and connectivity."
                ),
                "INVALID": (
                    "The saved ICE server JSON is invalid. "
                    "Correct it before starting a consultation."
                ),
            }[video],
            "missing": ["WEBRTC_ICE_SERVERS"] if video == "INVALID" else [],
            "command": "scripts\\configure-integrations.cmd webrtc",
            "verified_live": False,
        },
    }


@router.get("/admin/service-configuration")
def admin_configuration(_user: User = Depends(require_role("admin"))):
    return {"services": service_configuration()}


@router.get("/consultation-readiness")
def consultation_readiness(_user: User = Depends(current_user)):
    if _user.role not in {"patient", "doctor"}:
        raise HTTPException(403, "Only consultation participants can access this view")
    result = service_configuration()["video"]
    return {key: result[key] for key in ("status", "label", "summary", "verified_live")}
