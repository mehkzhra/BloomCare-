"""Explicit, idempotent assessment alerts through Twilio; no automatic external sends."""

import json
import re
from datetime import timedelta

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.assessment_service import pe_state, timestamp
from app.care_plan_service import own_assessment
from app.config import get_settings
from app.models import User, WhatsAppAlert, utc_now

STATUSES = {"accepted", "queued", "sending", "sent", "delivered", "read", "failed", "undelivered"}


def configuration_issues(settings=None):
    settings = settings or get_settings()
    issues = []
    if not settings.twilio_account_sid:
        issues.append("TWILIO_ACCOUNT_SID")
    if not settings.twilio_auth_token or not settings.twilio_auth_token.get_secret_value().strip():
        issues.append("TWILIO_AUTH_TOKEN")
    sender = (settings.twilio_whatsapp_from or "").removeprefix("whatsapp:")
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", sender):
        issues.append("TWILIO_WHATSAPP_FROM")
    recipients = [n.strip() for n in settings.twilio_allowed_recipients.split(",") if n.strip()]
    if not recipients or any(not re.fullmatch(r"\+[1-9][0-9]{7,14}", n) for n in recipients):
        issues.append("TWILIO_ALLOWED_RECIPIENTS")
    return issues


def configured(settings=None):
    return not configuration_issues(settings)


def alert_out(row):
    return {
        "id": row.id,
        "assessment_id": row.assessment_id,
        "recipient": "••••" + row.recipient[-4:],
        "status": row.status,
        "detail": row.detail,
        "created_at": timestamp(row.created_at),
    }


def provider_request(settings, method, sid=None, data=None):
    url = "https://api.twilio.com/2010-04-01/Accounts/" + settings.twilio_account_sid + "/Messages"
    url += "/" + sid + ".json" if sid else ".json"
    with httpx.Client(timeout=httpx.Timeout(12, connect=4), follow_redirects=False) as client:
        response = client.request(
            method,
            url,
            data=data,
            auth=httpx.BasicAuth(
                settings.twilio_account_sid, settings.twilio_auth_token.get_secret_value()
            ),
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Invalid provider response")
    return payload


def apply_provider_status(row, payload):
    sid = payload.get("sid")
    if (
        not isinstance(sid, str)
        or len(sid) != 34
        or not sid.startswith("SM")
        or not all(c in "0123456789abcdefABCDEF" for c in sid[2:])
    ):
        raise ValueError("Invalid provider message identifier")
    if row.provider_sid and row.provider_sid != sid:
        raise ValueError("Provider message identifier changed")
    status = str(payload.get("status", "")).lower()
    row.provider_sid = sid
    row.status = status.upper() if status in STATUSES else "UNKNOWN"
    row.detail = (
        "The provider could not deliver this message. Check the approved contact "
        "and WhatsApp configuration."
        if status in {"failed", "undelivered"}
        else None
    )


def send_alert(db, patient, assessment_id, data):
    assessment = own_assessment(db, patient.id, assessment_id)
    settings = get_settings()
    previous = db.scalar(
        select(WhatsAppAlert).where(
            WhatsAppAlert.patient_id == patient.id, WhatsAppAlert.request_id == str(data.request_id)
        )
    )
    if previous:
        if previous.assessment_id != assessment.id or previous.recipient != data.recipient:
            raise HTTPException(409, "This alert request ID already has different details")
        return alert_out(previous)
    if not configured(settings):
        raise HTTPException(503, "WhatsApp alerts are currently unavailable")
    allowed = {n.strip() for n in settings.twilio_allowed_recipients.split(",") if n.strip()}
    if data.recipient not in allowed:
        raise HTTPException(422, "Choose an approved care contact for WhatsApp alerts")
    db.scalar(select(User.id).where(User.id == patient.id).with_for_update())
    count = db.scalar(
        select(func.count())
        .select_from(WhatsAppAlert)
        .where(
            WhatsAppAlert.patient_id == patient.id,
            WhatsAppAlert.created_at > utc_now() - timedelta(minutes=15),
        )
    )
    if count >= 3:
        raise HTTPException(429, "The WhatsApp alert limit was reached. Wait before sending again.")
    row = WhatsAppAlert(
        patient_id=patient.id,
        assessment_id=assessment.id,
        request_id=str(data.request_id),
        recipient=data.recipient,
        consent_at=utc_now(),
        status="SUBMITTING",
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This alert request was saved. Refresh before retrying.") from None
    status, _ = pe_state(assessment)
    pe_text = assessment.pe_screening.risk if assessment.pe_screening else status
    sender = settings.twilio_whatsapp_from
    payload = {
        "From": sender if sender.startswith("whatsapp:") else "whatsapp:" + sender,
        "To": "whatsapp:" + data.recipient,
    }
    if settings.twilio_content_sid:
        payload.update(
            ContentSid=settings.twilio_content_sid,
            ContentVariables=json.dumps({"1": assessment.maternal_risk, "2": pe_text}),
        )
    else:
        payload["Body"] = (
            "BloomCare assessment alert. Maternal screening category: "
            + assessment.maternal_risk
            + ". PE stage: "
            + pe_text
            + ". Screening is not a diagnosis. Please discuss the saved report with the care team."
        )
    try:
        apply_provider_status(row, provider_request(settings, "POST", data=payload))
    except httpx.HTTPStatusError as error:
        row.status = "UNCERTAIN" if error.response.status_code >= 500 else "FAILED"
        row.detail = (
            "The provider did not confirm this alert. Check its console before sending again."
        )
    except (httpx.RequestError, ValueError):
        row.status = "UNCERTAIN"
        row.detail = (
            "Delivery is unconfirmed. Check the provider console before sending another alert."
        )
    db.commit()
    return alert_out(row)


def refresh_alert(db, patient, alert_id):
    row = db.scalar(
        select(WhatsAppAlert).where(
            WhatsAppAlert.id == alert_id,
            WhatsAppAlert.patient_id == patient.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Alert not found")
    if row.provider_sid and configured():
        try:
            apply_provider_status(
                row, provider_request(get_settings(), "GET", sid=row.provider_sid)
            )
            db.commit()
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError):
            raise HTTPException(
                502, "The delivery status could not be refreshed. Try again later."
            ) from None
    return alert_out(row)
