"""Consent-bound, versioned educational plans for actual saved assessments."""

import json
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.assessment_service import (
    care_plan_context,
    require_active_assessment,
    serialize_assessment,
)
from app.config import get_settings
from app.groq_service import GroqFailure, complete
from app.models import Assessment, AssessmentCarePlan, utc_now
from app.notifications import notify


def own_assessment(db, patient_id, assessment_id):
    row = db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.patient_id == patient_id
        )
    )
    if row is None:
        raise HTTPException(404, "Assessment not found")
    return require_active_assessment(row)


def generate_care_plan(db, patient, assessment_id, data):
    row = own_assessment(db, patient.id, assessment_id)
    context, digest = care_plan_context(row, data.language)
    settings = get_settings()
    plan = db.scalar(
        select(AssessmentCarePlan)
        .where(
            AssessmentCarePlan.assessment_id == row.id,
            AssessmentCarePlan.context_sha256 == digest,
        )
        .with_for_update()
    )
    now = utc_now()
    if plan and plan.status == "READY":
        return serialize_assessment(row)
    if not settings.groq_api_key:
        raise HTTPException(503, "The care-plan service is currently unavailable")
    if plan:
        updated = plan.updated_at.replace(tzinfo=now.tzinfo)
        if plan.status == "GENERATING" and updated > now - timedelta(minutes=2):
            raise HTTPException(409, "This care plan is being prepared. Refresh before retrying.")
        if plan.status == "FAILED" and updated > now - timedelta(seconds=30):
            raise HTTPException(429, "Wait 30 seconds before retrying the care plan")
    else:
        attempts = db.scalar(
            select(func.count())
            .select_from(AssessmentCarePlan)
            .join(Assessment)
            .where(
                Assessment.patient_id == patient.id,
                AssessmentCarePlan.created_at > now - timedelta(minutes=15),
            )
        )
        if attempts >= 10:
            raise HTTPException(429, "The care-plan request limit was reached. Try again later.")
        plan = AssessmentCarePlan(
            assessment_id=row.id,
            context_sha256=digest,
            context_snapshot=context,
            status="GENERATING",
            provider_model=settings.groq_model,
            language=data.language,
            consent_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(plan)
    plan.status, plan.updated_at = "GENERATING", now
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "A care-plan request is already in progress. Refresh first."
        ) from None
    messages = [
        {
            "role": "system",
            "content": (
                "You provide an educational maternal care guide, not a prescription or diagnosis. "
                "Use only the supplied actual measurements and saved screening categories. "
                "The models have not been clinically validated; their scores are not disease "
                "probabilities. Never describe a LOW result as ruling out complications. "
                "Do not invent missing findings or interpret model coverage as healthy ranges. "
                "Do not prescribe medicines, doses, tests, or treatment changes. "
                "Describe practical non-treatment preparation for a clinician discussion and "
                "questions to ask. For urgent concerns advise seeking professional care, without "
                "diagnosing. Mention an incomplete or unsupported PE stage accurately. "
                "Use short headings: Your recorded results; Care discussion; Daily routine; "
                "When to contact your care team. Keep the guide under 450 words. Answer in "
                + ("Urdu." if data.language == "ur" else "English.")
            ),
        },
        {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
    ]
    try:
        content = complete(settings, messages)
    except GroqFailure as error:
        plan.status, plan.updated_at = "FAILED", utc_now()
        db.commit()
        raise HTTPException(
            error.status_code, {"code": error.code, "message": error.message}
        ) from None
    plan.content, plan.status, plan.updated_at = content, "READY", utc_now()
    notify(db, patient.id, "CARE_PLAN_READY", assessment_id=row.id)
    db.commit()
    db.refresh(row)
    return serialize_assessment(row)
