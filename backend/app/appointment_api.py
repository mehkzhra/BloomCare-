"""Participant-only appointment, review, and clinician-note routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.appointment_service import (
    approved_doctor,
    book_appointment,
    participant_appointment,
    review_appointment,
    save_note,
    serialize_appointment,
    serialize_note,
    shared_record,
    transition,
)
from app.assessment_service import serialize_assessment
from app.database import get_db
from app.models import (
    Appointment,
    AppointmentRecord,
    Assessment,
    DoctorNote,
    HealthRecord,
    PatientProfile,
    User,
)
from app.schemas import (
    AppointmentDecision,
    AppointmentInput,
    AppointmentOut,
    AssessmentOut,
    NoteInput,
    NoteOut,
    ReviewOut,
)
from app.security import require_role

router = APIRouter(prefix="/api")
patient = require_role("patient")


def doctor(user: User = Depends(require_role("doctor")), db: Session = Depends(get_db)):
    if not approved_doctor(db, user.id):
        raise HTTPException(403, "An approved, active doctor account is required")
    return user


def appointment_list(db, user, offset):
    column = Appointment.patient_id if user.role == "patient" else Appointment.doctor_id
    rows = db.scalars(
        select(Appointment)
        .where(column == user.id)
        .order_by(Appointment.scheduled_at.desc(), Appointment.id.desc())
        .offset(offset)
        .limit(50)
    )
    return [serialize_appointment(db, row) for row in rows]


@router.post("/patients/me/appointments", response_model=AppointmentOut, status_code=201)
def book(data: AppointmentInput, user: User = Depends(patient), db: Session = Depends(get_db)):
    return book_appointment(db, user, data)


@router.get("/patients/me/appointments", response_model=list[AppointmentOut])
def patient_appointments(
    user: User = Depends(patient),
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0, le=100000),
):
    return appointment_list(db, user, offset)


@router.get("/doctors/me/appointments", response_model=list[AppointmentOut])
def doctor_appointments(
    user: User = Depends(doctor),
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0, le=100000),
):
    return appointment_list(db, user, offset)


@router.post("/patients/me/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel(appointment_id: str, user: User = Depends(patient), db: Session = Depends(get_db)):
    return transition(db, appointment_id, user, "CANCEL")


@router.post("/doctors/me/appointments/{appointment_id}/decision", response_model=AppointmentOut)
def decision(
    appointment_id: str,
    data: AppointmentDecision,
    user: User = Depends(doctor),
    db: Session = Depends(get_db),
):
    return transition(db, appointment_id, user, data.action)


@router.get("/doctors/me/appointments/{appointment_id}/review", response_model=ReviewOut)
def review(appointment_id: str, user: User = Depends(doctor), db: Session = Depends(get_db)):
    appointment = review_appointment(db, appointment_id, user)
    records = db.scalars(
        select(HealthRecord)
        .join(AppointmentRecord, AppointmentRecord.health_record_id == HealthRecord.id)
        .where(
            AppointmentRecord.appointment_id == appointment.id,
            HealthRecord.patient_id == appointment.patient_id,
            HealthRecord.removed_at.is_(None),
        )
        .order_by(HealthRecord.created_at.desc(), HealthRecord.id.desc())
    ).all()
    return {
        "appointment": serialize_appointment(db, appointment),
        "profile": db.get(PatientProfile, appointment.patient_id),
        "records": records,
        "assessments": [
            serialize_assessment(row)
            for row in db.scalars(
                select(Assessment)
                .where(
                    Assessment.patient_id == appointment.patient_id,
                    Assessment.health_record_id.in_([record.id for record in records]),
                    Assessment.removed_at.is_(None),
                )
                .order_by(Assessment.created_at.desc())
                .limit(200)
            ).all()
        ],
    }


@router.get(
    "/doctors/me/appointments/{appointment_id}/records/{record_id}/assessments",
    response_model=list[AssessmentOut],
)
def shared_assessments(
    appointment_id: str,
    record_id: str,
    user: User = Depends(doctor),
    db: Session = Depends(get_db),
):
    appointment = review_appointment(db, appointment_id, user)
    shared_record(db, appointment, record_id)
    rows = db.scalars(
        select(Assessment)
        .where(
            Assessment.patient_id == appointment.patient_id,
            Assessment.health_record_id == record_id,
            Assessment.removed_at.is_(None),
        )
        .order_by(Assessment.created_at.desc(), Assessment.id.desc())
        .limit(50)
    )
    return [serialize_assessment(row) for row in rows]


def notes(db, appointment_id, user):
    participant_appointment(db, appointment_id, user)
    query = select(DoctorNote).where(DoctorNote.appointment_id == appointment_id)
    if user.role == "patient":
        query = query.where(DoctorNote.patient_visible.is_(True))
    else:
        query = query.where(DoctorNote.author_id == user.id)
    rows = db.scalars(query.order_by(DoctorNote.created_at.desc(), DoctorNote.id.desc()).limit(100))
    return [serialize_note(db, row) for row in rows]


@router.get("/patients/me/appointments/{appointment_id}/notes", response_model=list[NoteOut])
def patient_notes(
    appointment_id: str, user: User = Depends(patient), db: Session = Depends(get_db)
):
    return notes(db, appointment_id, user)


@router.get("/doctors/me/appointments/{appointment_id}/notes", response_model=list[NoteOut])
def doctor_notes(appointment_id: str, user: User = Depends(doctor), db: Session = Depends(get_db)):
    return notes(db, appointment_id, user)


@router.post(
    "/doctors/me/appointments/{appointment_id}/notes", response_model=NoteOut, status_code=201
)
def add_note(
    appointment_id: str,
    data: NoteInput,
    user: User = Depends(doctor),
    db: Session = Depends(get_db),
):
    return save_note(db, appointment_id, user, data)
