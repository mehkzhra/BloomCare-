"""Owner-confirmed removal of erroneous results; immutable clinical audit is retained."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.appointment_service import record_access_available
from app.assessment_service import timestamp
from app.database import get_db
from app.models import (
    AccountEvent,
    Appointment,
    AppointmentRecord,
    Assessment,
    FollowUpProposal,
    HealthRecord,
    Notification,
    User,
    utc_now,
)
from app.notifications import notify
from app.schemas import Input
from app.security import require_role

router = APIRouter(prefix="/api")
patient = require_role("patient")


class RemovalInput(Input):
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Add a short reason for removing this assessment")
        return value


def removal_out(row):
    return {
        "id": row.id,
        "health_record_id": row.health_record_id,
        "created_at": timestamp(row.created_at),
        "removed_at": timestamp(row.removed_at),
        "reason": row.removal_reason,
    }


def record_removal_out(row):
    return {
        "id": row.id,
        "created_at": timestamp(row.created_at),
        "removed_at": timestamp(row.removed_at),
        "reason": row.removal_reason,
    }


def mark_assessment_removed(db, row, reason, now):
    """Participate in the caller's transaction; never commit a partial record removal."""
    changed = db.execute(
        update(Assessment)
        .where(Assessment.id == row.id, Assessment.removed_at.is_(None))
        .values(removed_at=now, removal_reason=reason)
    )
    if changed.rowcount != 1:
        return False
    db.execute(
        update(FollowUpProposal)
        .where(
            FollowUpProposal.assessment_id == row.id,
            FollowUpProposal.accepted_appointment_id.is_(None),
            FollowUpProposal.declined.is_(False),
        )
        .values(declined=True)
    )
    db.execute(
        update(Notification)
        .where(Notification.assessment_id == row.id, Notification.recipient_id == row.patient_id)
        .values(read=True)
    )
    return True


def notify_shared_doctors(db, record, kind):
    shared = db.scalars(
        select(Appointment)
        .join(AppointmentRecord)
        .where(
            Appointment.patient_id == record.patient_id,
            AppointmentRecord.health_record_id == record.id,
            Appointment.status == "ACCEPTED",
        )
    ).all()
    notified = set()
    for appointment in shared:
        if appointment.doctor_id not in notified and record_access_available(db, appointment):
            notify(db, appointment.doctor_id, kind, appointment.id)
            notified.add(appointment.doctor_id)


@router.get("/patients/me/removed-health-records")
def removed_health_records(
    offset: int = Query(0, ge=0, le=100000),
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(HealthRecord)
        .where(HealthRecord.patient_id == user.id, HealthRecord.removed_at.is_not(None))
        .order_by(HealthRecord.removed_at.desc(), HealthRecord.id)
        .offset(offset)
        .limit(50)
    )
    return [record_removal_out(row) for row in rows]


@router.delete("/patients/me/health-records/{record_id}")
def remove_health_record(
    record_id: str,
    data: RemovalInput,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    record = db.scalar(
        select(HealthRecord)
        .where(HealthRecord.id == record_id, HealthRecord.patient_id == user.id)
        .with_for_update(of=HealthRecord)
    )
    if record is None:
        raise HTTPException(404, "Health record not found")
    if record.removed_at is not None:
        return record_removal_out(record)
    now = utc_now()
    changed = db.execute(
        update(HealthRecord)
        .where(HealthRecord.id == record.id, HealthRecord.removed_at.is_(None))
        .values(removed_at=now, removal_reason=data.reason)
    )
    if changed.rowcount != 1:
        db.rollback()
        db.refresh(record)
        return record_removal_out(record)
    rows = db.scalars(
        select(Assessment)
        .where(Assessment.health_record_id == record.id, Assessment.removed_at.is_(None))
        .order_by(Assessment.id)
        .with_for_update(of=Assessment)
    ).all()
    for row in rows:
        mark_assessment_removed(db, row, data.reason, now)
    notify_shared_doctors(db, record, "HEALTH_RECORD_REMOVED")
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="HEALTH_RECORD_REMOVED"))
    db.commit()
    db.refresh(record)
    return record_removal_out(record)


@router.get("/patients/me/removed-assessments")
def removed_assessments(
    offset: int = Query(0, ge=0, le=100000),
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(Assessment)
        .where(Assessment.patient_id == user.id, Assessment.removed_at.is_not(None))
        .order_by(Assessment.removed_at.desc(), Assessment.id)
        .offset(offset)
        .limit(50)
    )
    return [removal_out(row) for row in rows]


@router.delete("/patients/me/assessments/{assessment_id}")
def remove_assessment(
    assessment_id: str,
    data: RemovalInput,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(Assessment)
        .where(Assessment.id == assessment_id, Assessment.patient_id == user.id)
        # The model version is eagerly joined; PostgreSQL must lock only the result row.
        .with_for_update(of=Assessment)
    )
    if row is None:
        raise HTTPException(404, "Assessment not found")
    if row.removed_at is not None:
        return removal_out(row)
    now = utc_now()
    if not mark_assessment_removed(db, row, data.reason, now):
        db.rollback()
        db.refresh(row)
        return removal_out(row)
    notify_shared_doctors(db, db.get(HealthRecord, row.health_record_id), "ASSESSMENT_REMOVED")
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="ASSESSMENT_REMOVED"))
    db.commit()
    db.refresh(row)
    return removal_out(row)
