"""Appointment transitions and the central, expiring record-access policy."""

from datetime import timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Appointment,
    AppointmentEvent,
    AppointmentRecord,
    DoctorNote,
    DoctorProfile,
    HealthRecord,
    User,
    utc_now,
)
from app.notifications import notify


def utc(value):
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def approved_doctor(db, doctor_id):
    user = db.get(User, doctor_id)
    profile = db.get(DoctorProfile, doctor_id)
    return bool(user and user.active and user.role == "doctor" and profile and profile.approved)


def record_access_available(db, appointment):
    patient = db.get(User, appointment.patient_id)
    return bool(
        appointment.status == "ACCEPTED"
        and appointment.accepted_at is not None
        and appointment.access_until is not None
        and utc(appointment.accepted_at) <= utc_now() < utc(appointment.access_until)
        and patient
        and patient.active
        and patient.role == "patient"
        and approved_doctor(db, appointment.doctor_id)
    )


def participant_appointment(db, appointment_id, user, *, lock=False):
    column = Appointment.patient_id if user.role == "patient" else Appointment.doctor_id
    query = select(Appointment).where(Appointment.id == appointment_id, column == user.id)
    if lock:
        query = query.with_for_update()
    appointment = db.scalar(query)
    if appointment is None:
        raise HTTPException(404, "Appointment not found")
    return appointment


def review_appointment(db, appointment_id, doctor):
    appointment = participant_appointment(db, appointment_id, doctor, lock=True)
    if not record_access_available(db, appointment):
        raise HTTPException(403, "Record access requires an accepted, unexpired care episode")
    return appointment


def shared_record(db, appointment, record_id):
    record = db.scalar(
        select(HealthRecord)
        .join(AppointmentRecord, AppointmentRecord.health_record_id == HealthRecord.id)
        .where(
            AppointmentRecord.appointment_id == appointment.id,
            HealthRecord.patient_id == appointment.patient_id,
            HealthRecord.id == record_id,
            HealthRecord.removed_at.is_(None),
        )
    )
    if record is None:
        raise HTTPException(404, "Shared health record not found")
    return record


def serialize_appointment(db, appointment):
    return {
        "id": appointment.id,
        "patient_id": appointment.patient_id,
        "patient_name": db.get(User, appointment.patient_id).full_name,
        "doctor_id": appointment.doctor_id,
        "doctor_name": db.get(User, appointment.doctor_id).full_name,
        "scheduled_at": utc(appointment.scheduled_at),
        "reason": appointment.reason,
        "status": appointment.status,
        "health_record_ids": list(
            db.scalars(
                select(AppointmentRecord.health_record_id)
                .join(HealthRecord, HealthRecord.id == AppointmentRecord.health_record_id)
                .where(
                    AppointmentRecord.appointment_id == appointment.id,
                    HealthRecord.removed_at.is_(None),
                )
                .order_by(AppointmentRecord.health_record_id)
            )
        ),
        "consent_at": utc(appointment.consent_at),
        "accepted_at": utc(appointment.accepted_at) if appointment.accepted_at else None,
        "access_until": utc(appointment.access_until) if appointment.access_until else None,
        "closed_at": utc(appointment.closed_at) if appointment.closed_at else None,
        "created_at": utc(appointment.created_at),
        "updated_at": utc(appointment.updated_at),
        "record_access_available": record_access_available(db, appointment),
    }


def book_appointment(db, patient, data, *, commit=True):
    now = utc_now()
    if not now < data.scheduled_at <= now + timedelta(days=90):
        raise HTTPException(422, "Choose a future appointment within the next 90 days")
    if not approved_doctor(db, str(data.doctor_id)):
        raise HTTPException(404, "Approved doctor not found")
    ids = [str(value) for value in data.health_record_ids]
    owned = (
        list(
            db.scalars(
                select(HealthRecord.id).where(
                    HealthRecord.id.in_(ids),
                    HealthRecord.patient_id == patient.id,
                    HealthRecord.removed_at.is_(None),
                )
            )
        )
        if ids
        else []
    )
    if len(owned) != len(ids):
        raise HTTPException(404, "One or more selected health records were not found")
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=str(data.doctor_id),
        scheduled_at=data.scheduled_at,
        reason=data.reason,
        status="PENDING",
        consent_at=now,
        created_at=now,
        updated_at=now,
    )
    try:
        db.add(appointment)
        db.flush()
        db.add_all(
            AppointmentRecord(appointment_id=appointment.id, health_record_id=value)
            for value in ids
        )
        db.add(
            AppointmentEvent(
                appointment_id=appointment.id,
                actor_id=patient.id,
                from_status=None,
                to_status="PENDING",
            )
        )
        notify(db, appointment.doctor_id, "APPOINTMENT_REQUESTED", appointment.id)
        db.flush()
        if commit:
            db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "The doctor or patient already has a request at this time"
        ) from None
    return serialize_appointment(db, appointment)


def transition(db, appointment_id, user, action):
    appointment = participant_appointment(db, appointment_id, user, lock=True)
    targets = {
        "ACCEPT": "ACCEPTED",
        "REJECT": "REJECTED",
        "CANCEL": "CANCELLED",
        "COMPLETE": "COMPLETED",
    }
    target = targets[action]
    if appointment.status == target:
        return serialize_appointment(db, appointment)
    allowed = {
        "patient": {"CANCEL": {"PENDING", "ACCEPTED"}},
        "doctor": {
            "ACCEPT": {"PENDING"},
            "REJECT": {"PENDING"},
            "CANCEL": {"PENDING", "ACCEPTED"},
            "COMPLETE": {"ACCEPTED"},
        },
    }
    if appointment.status not in allowed.get(user.role, {}).get(action, set()):
        raise HTTPException(409, "This appointment cannot make the requested transition")
    now = utc_now()
    previous = appointment.status
    if action == "ACCEPT":
        patient = db.get(User, appointment.patient_id)
        if utc(appointment.scheduled_at) <= now or not patient.active:
            raise HTTPException(409, "A past appointment or inactive patient cannot be accepted")
        appointment.accepted_at = now
        appointment.access_until = utc(appointment.scheduled_at) + timedelta(hours=24)
    appointment.status = target
    appointment.updated_at = now
    if target in {"REJECTED", "CANCELLED", "COMPLETED"}:
        appointment.closed_at = now
    db.add(
        AppointmentEvent(
            appointment_id=appointment.id,
            actor_id=user.id,
            from_status=previous,
            to_status=target,
            created_at=now,
        )
    )
    recipient = appointment.doctor_id if user.role == "patient" else appointment.patient_id
    notify(db, recipient, "APPOINTMENT_" + target, appointment.id)
    db.commit()
    return serialize_appointment(db, appointment)


def serialize_note(db, note):
    from app.models import Assessment

    linked = db.get(Assessment, note.assessment_id) if note.assessment_id else None
    return {
        "id": note.id,
        "appointment_id": note.appointment_id,
        "assessment_id": note.assessment_id,
        "assessment_removed": bool(linked and linked.removed_at is not None),
        "supersedes_id": note.supersedes_id,
        "author_name": db.get(User, note.author_id).full_name,
        "body": note.body,
        "patient_visible": note.patient_visible,
        "created_at": utc(note.created_at),
    }


def save_note(db, appointment_id, doctor, data):
    appointment = review_appointment(db, appointment_id, doctor)
    if data.assessment_id:
        from app.clinical_service import shared_assessment

        shared_assessment(db, appointment_id, str(data.assessment_id), doctor)
    note = DoctorNote(
        appointment_id=appointment.id,
        author_id=doctor.id,
        assessment_id=str(data.assessment_id) if data.assessment_id else None,
        body=data.body,
        patient_visible=data.patient_visible,
    )
    db.add(note)
    if note.patient_visible:
        notify(db, appointment.patient_id, "CLINICIAN_NOTE", appointment.id)
    db.commit()
    return serialize_note(db, note)
