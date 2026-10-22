"""Role-scoped endpoints for the complete clinical delivery workflow."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.appointment_api import doctor
from app.assessment_service import serialize_assessment, timestamp
from app.care_plan_service import generate_care_plan, own_assessment
from app.clinical_service import (
    amend_note,
    doctor_analytics,
    doctor_cases,
    save_review,
    shared_assessment,
)
from app.database import get_db
from app.delivery_schemas import (
    AlertInput,
    CarePlanInput,
    ClinicalReviewInput,
    FollowUpInput,
    ProposalAcceptance,
    RescheduleInput,
)
from app.follow_up_service import (
    accept_follow_up,
    decline_follow_up,
    proposal_out,
    propose_follow_up,
    reschedule,
)
from app.models import (
    Assessment,
    ClinicalReview,
    ClinicalReviewEvent,
    DoctorNote,
    FollowUpProposal,
    PatientProfile,
    User,
    WhatsAppAlert,
    utc_now,
)
from app.schemas import AppointmentOut, AssessmentOut, NoteInput, NoteOut
from app.security import require_role
from app.whatsapp_service import alert_out, configured, refresh_alert, send_alert

router = APIRouter(prefix="/api")
patient = require_role("patient")
admin = require_role("admin")


@router.post("/patients/me/assessments/{assessment_id}/care-plan", response_model=AssessmentOut)
def care_plan(
    assessment_id: str,
    data: CarePlanInput,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    return generate_care_plan(db, user, assessment_id, data)


@router.post(
    "/patients/me/assessments/{assessment_id}/pe/explanation", response_model=AssessmentOut
)
def explain_pe(assessment_id: str, user: User = Depends(patient), db: Session = Depends(get_db)):
    from app.pe_model import PEModelUnavailable, get_pe_model

    row = own_assessment(db, user.id, assessment_id)
    if not row.pe_screening:
        raise HTTPException(409, "Complete PE screening before requesting its explanation")
    if row.pe_screening.explanation is None:
        try:
            result = get_pe_model().infer(row.pe_screening.observations_snapshot)
        except (PEModelUnavailable, ImportError):
            raise HTTPException(503, "PE explanation is currently unavailable") from None
        if result["class_scores"] != row.pe_screening.class_scores:
            raise HTTPException(409, "The explanation did not match the saved PE scores")
        row.pe_screening.explanation = result["explanation"]
        db.commit()
    return serialize_assessment(row)


@router.put(
    "/doctors/me/appointments/{appointment_id}/assessments/{assessment_id}/review",
    response_model=AssessmentOut,
)
def review_assessment(
    appointment_id: str,
    assessment_id: str,
    data: ClinicalReviewInput,
    user: User = Depends(doctor),
    db: Session = Depends(get_db),
):
    return save_review(db, appointment_id, assessment_id, user, data)


def review_events(db, assessment_id):
    rows = db.scalars(
        select(ClinicalReviewEvent)
        .join(ClinicalReview)
        .where(ClinicalReview.assessment_id == assessment_id)
        .order_by(ClinicalReviewEvent.created_at.desc(), ClinicalReviewEvent.version.desc())
        .limit(100)
    )
    return [
        {
            "id": row.id,
            "doctor_name": db.get(User, row.doctor_id).full_name,
            "version": row.version,
            "snapshot": row.snapshot,
            "created_at": timestamp(row.created_at),
        }
        for row in rows
    ]


@router.get("/patients/me/assessments/{assessment_id}/reviews")
def patient_reviews(
    assessment_id: str, user: User = Depends(patient), db: Session = Depends(get_db)
):
    own_assessment(db, user.id, assessment_id)
    return review_events(db, assessment_id)


@router.get("/doctors/me/appointments/{appointment_id}/assessments/{assessment_id}/reviews")
def doctor_reviews(
    appointment_id: str,
    assessment_id: str,
    user: User = Depends(doctor),
    db: Session = Depends(get_db),
):
    shared_assessment(db, appointment_id, assessment_id, user)
    return review_events(db, assessment_id)


@router.post(
    "/doctors/me/appointments/{appointment_id}/notes/{note_id}/amend",
    response_model=NoteOut,
    status_code=201,
)
def amend(
    appointment_id: str,
    note_id: str,
    data: NoteInput,
    user: User = Depends(doctor),
    db: Session = Depends(get_db),
):
    return amend_note(db, appointment_id, note_id, user, data)


@router.post("/doctors/me/appointments/{appointment_id}/follow-ups", status_code=201)
def follow_up(
    appointment_id: str,
    data: FollowUpInput,
    user: User = Depends(doctor),
    db: Session = Depends(get_db),
):
    return propose_follow_up(db, appointment_id, user, data)


@router.get("/patients/me/follow-ups")
def proposals(user: User = Depends(patient), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(FollowUpProposal)
        .where(FollowUpProposal.patient_id == user.id)
        .order_by(FollowUpProposal.created_at.desc())
        .limit(50)
    )
    return [proposal_out(db, row) for row in rows]


@router.post("/patients/me/follow-ups/{proposal_id}/accept", response_model=AppointmentOut)
def accept_proposal(
    proposal_id: str,
    data: ProposalAcceptance,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    return accept_follow_up(db, user, proposal_id, data)


@router.post("/patients/me/follow-ups/{proposal_id}/decline")
def decline_proposal(
    proposal_id: str, user: User = Depends(patient), db: Session = Depends(get_db)
):
    return decline_follow_up(db, user, proposal_id)


@router.patch(
    "/patients/me/appointments/{appointment_id}/reschedule", response_model=AppointmentOut
)
def change_slot(
    appointment_id: str,
    data: RescheduleInput,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    return reschedule(db, appointment_id, user, data)


@router.get("/doctors/me/cases")
def cases(
    q: str = Query("", max_length=80),
    risk: Literal["LOW", "MEDIUM", "HIGH"] | None = None,
    review_status: Literal["PENDING", "REVIEWED", "URGENT_FOLLOW_UP"] | None = None,
    offset: int = Query(0, ge=0, le=100000),
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    user: User = Depends(doctor),
    db: Session = Depends(get_db),
):
    return doctor_cases(db, user, q, risk, review_status, offset, from_at, to_at)


@router.get("/doctors/me/analytics")
def clinician_analytics(user: User = Depends(doctor), db: Session = Depends(get_db)):
    return doctor_analytics(db, user)


@router.get("/admin/clinical-reviews")
def clinical_reviews(
    q: str = Query("", max_length=80),
    status: Literal["PENDING", "REVIEWED", "URGENT_FOLLOW_UP"] | None = None,
    offset: int = Query(0, ge=0, le=100000),
    _user: User = Depends(admin),
    db: Session = Depends(get_db),
):
    query = select(ClinicalReview).join(Assessment).join(User, User.id == Assessment.patient_id)
    if q:
        query = query.where(User.full_name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%"))
    if status:
        query = query.where(ClinicalReview.status == status)
    rows = db.scalars(query.order_by(ClinicalReview.updated_at.desc()).offset(offset).limit(50))
    result = []
    for row in rows:
        assessment = db.get(Assessment, row.assessment_id)
        result.append(
            {
                "id": row.id,
                "assessment_id": row.assessment_id,
                "assessment_removed": assessment.removed_at is not None,
                "patient": db.get(User, assessment.patient_id).full_name,
                "doctor": db.get(User, row.doctor_id).full_name,
                "status": row.status,
                "follow_up_at": timestamp(row.follow_up_at),
                "updated_at": timestamp(row.updated_at),
            }
        )
    return result


def assessment_report(db, row):
    person = db.get(User, row.patient_id)
    profile = db.get(PatientProfile, person.id)
    notes = db.scalars(
        select(DoctorNote)
        .where(DoctorNote.assessment_id == row.id, DoctorNote.patient_visible.is_(True))
        .order_by(DoctorNote.created_at, DoctorNote.id)
        .limit(100)
    )
    return {
        "format_version": "2",
        "generated_at": utc_now(),
        "patient": {"full_name": person.full_name, "email": person.email},
        "due_date": profile.due_date if profile else None,
        "assessment": serialize_assessment(row),
        "notes": [
            {
                "id": n.id,
                "body": n.body,
                "author": db.get(User, n.author_id).full_name,
                "supersedes_id": n.supersedes_id,
                "created_at": timestamp(n.created_at),
            }
            for n in notes
        ],
        "notice": "Screening support only. Model scores are not disease probabilities. "
        "Clinical validation is pending. LOW does not rule out complications.",
    }


@router.get("/patients/me/assessments/{assessment_id}/report-data")
def patient_report(
    assessment_id: str, user: User = Depends(patient), db: Session = Depends(get_db)
):
    return assessment_report(db, own_assessment(db, user.id, assessment_id))


@router.get("/doctors/me/appointments/{appointment_id}/assessments/{assessment_id}/report-data")
def doctor_report(
    appointment_id: str,
    assessment_id: str,
    user: User = Depends(doctor),
    db: Session = Depends(get_db),
):
    _, row = shared_assessment(db, appointment_id, assessment_id, user)
    return assessment_report(db, row)


@router.get("/patients/me/whatsapp/status")
def whatsapp_status(_user: User = Depends(patient)):
    return {"configured": configured()}


@router.get("/patients/me/assessments/{assessment_id}/alerts")
def assessment_alerts(
    assessment_id: str, user: User = Depends(patient), db: Session = Depends(get_db)
):
    own_assessment(db, user.id, assessment_id)
    return [
        alert_out(row)
        for row in db.scalars(
            select(WhatsAppAlert)
            .where(
                WhatsAppAlert.patient_id == user.id,
                WhatsAppAlert.assessment_id == assessment_id,
            )
            .order_by(WhatsAppAlert.created_at.desc())
            .limit(30)
        )
    ]


@router.post("/patients/me/assessments/{assessment_id}/alerts", status_code=201)
def whatsapp_alert(
    assessment_id: str,
    data: AlertInput,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    return send_alert(db, user, assessment_id, data)


@router.get("/patients/me/alerts/{alert_id}")
def alert_status(alert_id: str, user: User = Depends(patient), db: Session = Depends(get_db)):
    return refresh_alert(db, user, alert_id)
