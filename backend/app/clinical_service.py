"""Assessment-scoped clinical decisions with optimistic versions and immutable events."""

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.appointment_service import record_access_available, review_appointment, shared_record, utc
from app.assessment_service import require_active_assessment, review_out, serialize_assessment
from app.models import (
    Appointment,
    AppointmentRecord,
    Assessment,
    ClinicalReview,
    ClinicalReviewEvent,
    DoctorNote,
    HealthRecord,
    User,
    utc_now,
)
from app.notifications import notify
from app.query_filters import time_range


def shared_assessment(db, appointment_id, assessment_id, doctor):
    appointment = review_appointment(db, appointment_id, doctor)
    row = db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.patient_id == appointment.patient_id
        )
    )
    if row is None:
        raise HTTPException(404, "Shared assessment not found")
    shared_record(db, appointment, row.health_record_id)
    require_active_assessment(row)
    return appointment, row


def save_review(db, appointment_id, assessment_id, doctor, data):
    appointment, row = shared_assessment(db, appointment_id, assessment_id, doctor)
    current = db.scalar(
        select(ClinicalReview).where(ClinicalReview.assessment_id == row.id).with_for_update()
    )
    version = current.version if current else 0
    if version != data.expected_version:
        raise HTTPException(
            409, "This assessment was reviewed elsewhere. Refresh its latest state."
        )
    now = utc_now()
    values = dict(
        status=data.status,
        reason=data.reason,
        follow_up_at=data.follow_up_at,
        doctor_id=doctor.id,
        appointment_id=appointment.id,
        updated_at=now,
    )
    if current:
        changed = db.execute(
            update(ClinicalReview)
            .where(ClinicalReview.id == current.id, ClinicalReview.version == version)
            .values(**values, version=version + 1)
        )
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "The review changed. Refresh before saving.")
        db.refresh(current)
    else:
        current = ClinicalReview(assessment_id=row.id, version=1, **values)
        db.add(current)
    try:
        db.flush()
        snapshot = review_out(current)
        snapshot["updated_at"] = now.isoformat()
        if snapshot["follow_up_at"]:
            snapshot["follow_up_at"] = utc(snapshot["follow_up_at"]).isoformat()
        db.add(
            ClinicalReviewEvent(
                review_id=current.id,
                doctor_id=doctor.id,
                appointment_id=appointment.id,
                version=current.version,
                snapshot=snapshot,
            )
        )
        notify(
            db,
            appointment.patient_id,
            "URGENT_FOLLOW_UP" if data.status == "URGENT_FOLLOW_UP" else "ASSESSMENT_REVIEWED",
            appointment.id,
            assessment_id=row.id,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "A review was saved concurrently. Refresh before retrying."
        ) from None
    db.refresh(row)
    return serialize_assessment(row)


def amend_note(db, appointment_id, note_id, doctor, data):
    from app.appointment_service import serialize_note

    appointment = review_appointment(db, appointment_id, doctor)
    original = db.scalar(
        select(DoctorNote)
        .where(
            DoctorNote.id == note_id,
            DoctorNote.appointment_id == appointment.id,
            DoctorNote.author_id == doctor.id,
        )
        .with_for_update()
    )
    if not original:
        raise HTTPException(404, "Clinician note not found")
    if original.patient_visible and not data.patient_visible:
        raise HTTPException(422, "An amendment to a patient-visible note must remain visible")
    if db.scalar(select(DoctorNote.id).where(DoctorNote.supersedes_id == original.id)):
        raise HTTPException(
            409, "This note already has an amendment. Refresh and amend the latest one."
        )
    assessment_id = str(data.assessment_id) if data.assessment_id else original.assessment_id
    if original.assessment_id and assessment_id != original.assessment_id:
        raise HTTPException(422, "An amendment must keep the original assessment link")
    # Amending the author's existing note retains its established assessment link,
    # even when the patient has withdrawn the underlying record. It grants no result access.
    if assessment_id and assessment_id != original.assessment_id:
        shared_assessment(
            db,
            appointment.id,
            assessment_id,
            doctor,
        )
    note = DoctorNote(
        appointment_id=appointment.id,
        author_id=doctor.id,
        assessment_id=assessment_id,
        supersedes_id=original.id,
        body=data.body,
        patient_visible=data.patient_visible,
    )
    db.add(note)
    if note.patient_visible:
        notify(db, appointment.patient_id, "CLINICIAN_NOTE", appointment.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "This note was amended concurrently. Refresh its history."
        ) from None
    return serialize_note(db, note)


def doctor_record_ids(doctor_id):
    now = utc_now()
    return (
        select(AppointmentRecord.health_record_id)
        .join(HealthRecord, HealthRecord.id == AppointmentRecord.health_record_id)
        .join(Appointment, Appointment.id == AppointmentRecord.appointment_id)
        .join(User, User.id == Appointment.patient_id)
        .where(
            Appointment.doctor_id == doctor_id,
            HealthRecord.removed_at.is_(None),
            Appointment.status == "ACCEPTED",
            Appointment.accepted_at <= now,
            Appointment.access_until > now,
            User.active.is_(True),
            User.role == "patient",
        )
    )


def doctor_assessments(db, doctor_id):
    return select(Assessment).where(
        Assessment.health_record_id.in_(doctor_record_ids(doctor_id)),
        Assessment.removed_at.is_(None),
    )


def doctor_cases(db, doctor, q, risk, review_status, offset, from_at=None, to_at=None):
    query = doctor_assessments(db, doctor.id).join(User, User.id == Assessment.patient_id)
    query = time_range(query, Assessment.created_at, from_at, to_at)
    if q:
        query = query.where(User.full_name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%"))
    if risk:
        query = query.where(Assessment.maternal_risk == risk)
    if review_status:
        query = query.outerjoin(
            ClinicalReview, ClinicalReview.assessment_id == Assessment.id
        ).where(func.coalesce(ClinicalReview.status, "PENDING") == review_status)
    rows = db.scalars(
        query.order_by(Assessment.created_at.desc(), Assessment.id).offset(offset).limit(50)
    ).all()
    result = []
    for row in rows:
        appointments = db.scalars(
            select(Appointment)
            .join(AppointmentRecord)
            .where(
                AppointmentRecord.health_record_id == row.health_record_id,
                Appointment.patient_id == row.patient_id,
                Appointment.doctor_id == doctor.id,
                Appointment.status == "ACCEPTED",
            )
            .order_by(Appointment.scheduled_at.desc())
        ).all()
        appointment = next((a for a in appointments if record_access_available(db, a)), None)
        if appointment:
            person = db.get(User, row.patient_id)
            result.append(
                {
                    "patient_name": person.full_name,
                    "patient_email": person.email,
                    "appointment_id": appointment.id,
                    "assessment": serialize_assessment(row),
                }
            )
    return result


def doctor_analytics(db, doctor):
    ids = doctor_assessments(db, doctor.id).with_only_columns(Assessment.id).subquery()
    risk = dict(
        db.execute(
            select(Assessment.maternal_risk, func.count())
            .where(Assessment.id.in_(select(ids.c.id)))
            .group_by(Assessment.maternal_risk)
        ).all()
    )
    status = func.coalesce(ClinicalReview.status, "PENDING")
    reviews = dict(
        db.execute(
            select(status, func.count())
            .select_from(Assessment)
            .outerjoin(ClinicalReview)
            .where(Assessment.id.in_(select(ids.c.id)))
            .group_by(status)
        ).all()
    )
    return {
        "risk_categories": risk,
        "review_statuses": reviews,
        "total": sum(risk.values()),
        "scope": "Active, consented care episodes only",
    }
