"""Clinician proposals and patient-confirmed, conflict-checked appointment changes."""

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.appointment_service import (
    approved_doctor,
    book_appointment,
    participant_appointment,
    serialize_appointment,
    utc,
)
from app.clinical_service import shared_assessment
from app.delivery_schemas import proposal_booking
from app.models import (
    Appointment,
    AppointmentEvent,
    Assessment,
    Consultation,
    FollowUpProposal,
    ReportShare,
    User,
    utc_now,
)
from app.notifications import notify


def proposal_out(db, row):
    assessment = db.get(Assessment, row.assessment_id)
    return {
        "id": row.id,
        "appointment_id": row.appointment_id,
        "assessment_id": row.assessment_id,
        "health_record_id": assessment.health_record_id,
        "assessment_removed": assessment.removed_at is not None,
        "doctor_name": db.get(User, row.doctor_id).full_name,
        "patient_name": db.get(User, row.patient_id).full_name,
        "scheduled_at": utc(row.scheduled_at),
        "reason": row.reason,
        "expires_at": utc(row.expires_at),
        "declined": row.declined,
        "accepted_appointment_id": row.accepted_appointment_id,
        "expired": utc(row.expires_at) <= utc_now(),
    }


def propose_follow_up(db, appointment_id, doctor, data):
    appointment, assessment = shared_assessment(db, appointment_id, str(data.assessment_id), doctor)
    existing = db.scalar(
        select(FollowUpProposal).where(
            FollowUpProposal.doctor_id == doctor.id,
            FollowUpProposal.request_id == str(data.request_id),
        )
    )
    if existing:
        if (
            existing.assessment_id != assessment.id
            or utc(existing.scheduled_at) != data.scheduled_at
            or existing.reason != data.reason
        ):
            raise HTTPException(409, "This follow-up request ID already has different details")
        return proposal_out(db, existing)
    now = utc_now()
    row = FollowUpProposal(
        appointment_id=appointment.id,
        assessment_id=assessment.id,
        patient_id=appointment.patient_id,
        doctor_id=doctor.id,
        request_id=str(data.request_id),
        scheduled_at=data.scheduled_at,
        reason=data.reason,
        expires_at=min(now + timedelta(hours=72), data.scheduled_at),
    )
    db.add(row)
    notify(db, appointment.patient_id, "FOLLOW_UP_PROPOSED", appointment.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "This follow-up request was saved. Refresh before retrying."
        ) from None
    return proposal_out(db, row)


def own_proposal(db, patient_id, proposal_id):
    row = db.scalar(
        select(FollowUpProposal)
        .where(
            FollowUpProposal.id == proposal_id,
            FollowUpProposal.patient_id == patient_id,
        )
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Follow-up proposal not found")
    return row


def accept_follow_up(db, patient, proposal_id, data):
    row = own_proposal(db, patient.id, proposal_id)
    if row.accepted_appointment_id:
        return serialize_appointment(db, db.get(Appointment, row.accepted_appointment_id))
    if row.declined or utc(row.expires_at) <= utc_now():
        raise HTTPException(409, "This proposal is declined or expired")
    result = book_appointment(db, patient, proposal_booking(row, data), commit=False)
    row.accepted_appointment_id = result["id"]
    db.commit()
    return result


def decline_follow_up(db, patient, proposal_id):
    row = own_proposal(db, patient.id, proposal_id)
    if row.accepted_appointment_id:
        raise HTTPException(409, "The proposed appointment has already been requested")
    if not row.declined:
        row.declined = True
        notify(db, row.doctor_id, "FOLLOW_UP_DECLINED", row.appointment_id)
        db.commit()
    return proposal_out(db, row)


def reschedule(db, appointment_id, patient, data):
    row = participant_appointment(db, appointment_id, patient, lock=True)
    if not approved_doctor(db, row.doctor_id):
        raise HTTPException(409, "The doctor is currently unavailable for appointment requests")
    if row.status not in {"PENDING", "ACCEPTED"}:
        raise HTTPException(409, "Only an active appointment can be rescheduled")
    if utc(row.scheduled_at) == data.scheduled_at and row.reason == data.reason:
        return serialize_appointment(db, row)
    if data.expected_updated_at.tzinfo is None or (
        utc(row.updated_at) != data.expected_updated_at.astimezone(utc_now().tzinfo)
    ):
        raise HTTPException(409, "This appointment changed. Refresh before rescheduling.")
    now = utc_now()
    if utc(row.scheduled_at) <= now:
        raise HTTPException(409, "A past appointment cannot be rescheduled")
    with db.no_autoflush:
        previous = row.status
        row.scheduled_at, row.reason, row.status = data.scheduled_at, data.reason, "PENDING"
        row.accepted_at = row.access_until = row.closed_at = None
        row.updated_at = row.consent_at = now
        for call in db.scalars(
            select(Consultation).where(
                Consultation.appointment_id == row.id, Consultation.ended_at.is_(None)
            )
        ):
            call.ended_at = now
        db.execute(delete(ReportShare).where(ReportShare.appointment_id == row.id))
        db.add(
            AppointmentEvent(
                appointment_id=row.id,
                actor_id=patient.id,
                from_status=previous,
                to_status="PENDING",
            )
        )
        notify(db, row.doctor_id, "APPOINTMENT_RESCHEDULED", row.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "The doctor or patient already has a request at this time"
        ) from None
    return serialize_appointment(db, row)
