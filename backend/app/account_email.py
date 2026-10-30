"""TLS SMTP or HTTPS email delivery; never log bodies, tokens, keys or addresses."""

import logging
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from app.config import get_settings
from app.database import SessionLocal
from app.models import AccountEvent

logger = logging.getLogger("bloomcare")


def configured(settings=None):
    settings = settings or get_settings()
    if settings.email_provider == "brevo":
        return bool(
            settings.email_from
            and settings.brevo_api_key
            and settings.brevo_api_key.get_secret_value().strip()
        )
    return bool(
        settings.smtp_host
        and settings.smtp_from
        and settings.smtp_username
        and settings.smtp_password
        and settings.smtp_password.get_secret_value().strip()
    )


def send(recipient, purpose, token):
    settings = get_settings()
    if not configured(settings):
        raise ValueError("Account email is not configured")
    verify = purpose == "VERIFY_EMAIL"
    path = "/account/verify" if verify else "/account/reset"
    link = settings.public_app_url + path + "#token=" + token
    message = EmailMessage()
    message["From"] = str(
        settings.email_from if settings.email_provider == "brevo" else settings.smtp_from
    )
    message["To"] = recipient
    message["Subject"] = (
        "Verify your BloomCare email" if verify else "Reset your BloomCare password"
    )
    message.set_content(
        ("Verify your email address" if verify else "Choose a new password")
        + " using this one-time BloomCare link:\n\n"
        + link
        + (
            "\n\nThis link expires in 24 hours."
            if verify
            else "\n\nThis link expires in 30 minutes."
        )
        + " Use the latest link if you requested more than one.\n"
        + "If you did not make this request, ignore this email. Do not share the link.\n"
    )
    submit_message(settings, recipient, message)


def send_test(recipient):
    settings = get_settings()
    if not configured(settings):
        raise ValueError("Account email is not configured")
    message = EmailMessage()
    message["From"] = str(
        settings.email_from if settings.email_provider == "brevo" else settings.smtp_from
    )
    message["To"] = recipient
    message["Subject"] = "BloomCare service test"
    message.set_content(
        "You requested this service test from BloomCare administration. "
        "No patient information or account reset links are included."
    )
    submit_message(settings, recipient, message)


def submit_message(settings, recipient, message):
    if settings.email_provider == "brevo":
        # Fixed endpoint, verified TLS, no redirect or implicit retry. Avoid exception
        # bodies/URLs that could expose the reset link or provider credential.
        try:
            with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
                response = client.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={"api-key": settings.brevo_api_key.get_secret_value()},
                    json={
                        "sender": {"name": "BloomCare", "email": str(settings.email_from)},
                        "to": [{"email": recipient}],
                        "subject": str(message["Subject"]),
                        "textContent": message.get_content(),
                    },
                )
                if response.status_code != 201 or not response.json().get("messageId"):
                    raise ValueError("Email provider did not accept the message")
        except Exception:
            raise ValueError("Account email could not be submitted") from None
        return
    context = ssl.create_default_context()
    if settings.smtp_security == "ssl":
        connection = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=10, context=context
        )
    else:
        connection = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
    with connection as smtp:
        if settings.smtp_security == "starttls":
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
        smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        smtp.send_message(message)


def deliver(user_id, recipient, purpose, token):
    try:
        send(recipient, purpose, token)
        action = "ACCOUNT_EMAIL_SUBMITTED"
    except Exception:
        action = "ACCOUNT_EMAIL_FAILED"
        logger.warning("Account email delivery failed; no credentials or message were logged")
    try:
        with SessionLocal() as db:
            db.add(AccountEvent(actor_id=user_id, subject_id=user_id, action=action))
            db.commit()
    except Exception:
        logger.warning("Account email status could not be recorded")
