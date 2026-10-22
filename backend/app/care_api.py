from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assessment_service import serialize_assessment
from app.database import get_db
from app.models import (
    AccountEvent,
    Appointment,
    AppointmentEvent,
    Assessment,
    DoctorNote,
    HealthRecord,
    MedicalReport,
    MedicationEntry,
    PatientProfile,
    SymptomEntry,
    User,
    utc_now,
)
from app.schemas import Input
from app.security import require_role

router = APIRouter(prefix="/api/patients/me")
patient = require_role("patient")


def utc(value):
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


class SymptomInput(Input):
    description: str = Field(min_length=2, max_length=1000)
    severity: str = Field(pattern="^(MILD|MODERATE|SEVERE)$")
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def observed_time(cls, value):
        if value.tzinfo is None or utc(value) > utc_now():
            raise ValueError("Use a timezone-aware time that is not in the future")
        return utc(value)


class MedicationInput(Input):
    name: str = Field(min_length=2, max_length=120)
    dose: str = Field(min_length=1, max_length=120)
    schedule: str = Field(min_length=2, max_length=200)
    prescriber: str = Field(min_length=2, max_length=120)


class MedicationStatus(Input):
    active: bool = Field(strict=True)


def symptom_out(row):
    return {
        "id": row.id,
        "description": row.description,
        "severity": row.severity,
        "occurred_at": utc(row.occurred_at),
        "created_at": utc(row.created_at),
    }


def medication_out(row):
    return {
        key: getattr(row, key) for key in ("id", "name", "dose", "schedule", "prescriber", "active")
    } | {"created_at": utc(row.created_at), "updated_at": utc(row.updated_at)}


@router.post("/symptoms", status_code=201)
def save_symptom(data: SymptomInput, user: User = Depends(patient), db: Session = Depends(get_db)):
    row = SymptomEntry(patient_id=user.id, **data.model_dump())
    db.add(row)
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="SYMPTOM_SAVED"))
    db.commit()
    return symptom_out(row)


@router.get("/symptoms")
def symptoms(
    user: User = Depends(patient),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0, le=100000),
):
    return [
        symptom_out(r)
        for r in db.scalars(
            select(SymptomEntry)
            .where(SymptomEntry.patient_id == user.id)
            .order_by(SymptomEntry.occurred_at.desc(), SymptomEntry.id)
            .offset(offset)
            .limit(50)
        )
    ]


@router.post("/medications", status_code=201)
def save_medication(
    data: MedicationInput, user: User = Depends(patient), db: Session = Depends(get_db)
):
    row = MedicationEntry(patient_id=user.id, **data.model_dump())
    db.add(row)
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="MEDICATION_SAVED"))
    db.commit()
    return medication_out(row)


@router.get("/medications")
def medications(
    user: User = Depends(patient),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0, le=100000),
):
    return [
        medication_out(r)
        for r in db.scalars(
            select(MedicationEntry)
            .where(MedicationEntry.patient_id == user.id)
            .order_by(MedicationEntry.created_at.desc(), MedicationEntry.id)
            .offset(offset)
            .limit(50)
        )
    ]


@router.patch("/medications/{entry_id}")
def medication_status(
    entry_id: str,
    data: MedicationStatus,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(MedicationEntry).where(
            MedicationEntry.id == entry_id, MedicationEntry.patient_id == user.id
        )
    )
    if not row:
        raise HTTPException(404, "Medication record not found")
    if row.active != data.active:
        row.active = data.active
        row.updated_at = utc_now()
        db.add(
            AccountEvent(actor_id=user.id, subject_id=user.id, action="MEDICATION_STATUS_UPDATED")
        )
        db.commit()
    return medication_out(row)


def patient_timeline(db, user_id, offset, limit=50):
    rows = []

    def add(kind, row, title, details, timestamp=None):
        rows.append(
            {
                "id": kind + ":" + row.id,
                "type": kind,
                "title": title,
                "details": details,
                "at": utc(timestamp or row.created_at).isoformat(),
            }
        )

    queries = (
        ("OBSERVATION", HealthRecord, HealthRecord.patient_id),
        ("ASSESSMENT", Assessment, Assessment.patient_id),
        ("SYMPTOM", SymptomEntry, SymptomEntry.patient_id),
        ("MEDICATION", MedicationEntry, MedicationEntry.patient_id),
        ("APPOINTMENT", Appointment, Appointment.patient_id),
        ("REPORT", MedicalReport, MedicalReport.patient_id),
    )
    for kind, model, owner in queries:
        active = [model.removed_at.is_(None)] if model in {Assessment, HealthRecord} else []
        sort_time = model.occurred_at if model is SymptomEntry else model.created_at
        for r in db.scalars(
            select(model)
            .where(owner == user_id, *active)
            .order_by(sort_time.desc(), model.id.desc())
            .limit(offset + limit)
        ):
            if kind == "OBSERVATION":
                add(kind, r, "Health observations saved", r.observations)
            elif kind == "ASSESSMENT":
                result = serialize_assessment(r)
                add(
                    kind,
                    r,
                    "Maternal-risk assessment",
                    {
                        "maternal_risk": r.maternal_risk,
                        "pe_status": result["pe_status"],
                        "pe_category": result["pe_screening"]["risk"]
                        if result["pe_screening"]
                        else "Not completed",
                        "review_status": (result["clinical_review"] or {}).get("status", "PENDING"),
                        "care_plan_saved": result["care_plan"] is not None,
                    },
                )
            elif kind == "SYMPTOM":
                add(kind, r, r.description, {"severity": r.severity}, r.occurred_at)
            elif kind == "MEDICATION":
                add(kind, r, r.name, medication_out(r))
            elif kind == "REPORT":
                add(kind, r, r.title, {"media_type": r.media_type, "byte_size": r.byte_size})
            else:
                add(
                    kind,
                    r,
                    "Appointment",
                    {
                        "doctor": db.get(User, r.doctor_id).full_name,
                        "scheduled_at": utc(r.scheduled_at).isoformat(),
                        "status": r.status,
                    },
                )
    for r in db.scalars(
        select(DoctorNote)
        .join(Appointment)
        .where(Appointment.patient_id == user_id, DoctorNote.patient_visible.is_(True))
        .order_by(DoctorNote.created_at.desc(), DoctorNote.id.desc())
        .limit(offset + limit)
    ):
        add(
            "NOTE",
            r,
            "Clinician note",
            {"body": r.body, "author": db.get(User, r.author_id).full_name},
        )
    for r in db.scalars(
        select(AppointmentEvent)
        .join(Appointment)
        .where(Appointment.patient_id == user_id)
        .order_by(AppointmentEvent.created_at.desc(), AppointmentEvent.id.desc())
        .limit(offset + limit)
    ):
        add("APPOINTMENT_EVENT", r, "Appointment " + r.to_status.lower(), {})
    rows.sort(key=lambda r: (r["at"], r["id"]), reverse=True)
    return rows[offset : offset + limit]


@router.get("/timeline")
def timeline(
    user: User = Depends(patient),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0, le=10000),
):
    return patient_timeline(db, user.id, offset)


@router.get("/passport")
def passport(user: User = Depends(patient), db: Session = Depends(get_db)):
    profile = db.get(PatientProfile, user.id)
    medicine_rows = db.scalars(
        select(MedicationEntry)
        .where(MedicationEntry.patient_id == user.id, MedicationEntry.active.is_(True))
        .order_by(MedicationEntry.created_at.desc(), MedicationEntry.id)
        .limit(101)
    ).all()
    return {
        "format_version": "1",
        "generated_at": utc_now(),
        "patient": {"full_name": user.full_name, "email": user.email},
        "profile": {
            key: getattr(profile, key)
            for key in ("date_of_birth", "due_date", "phone", "preferred_language")
        }
        if profile
        else {},
        "active_medications": [medication_out(r) for r in medicine_rows[:100]],
        "medications_truncated": len(medicine_rows) > 100,
        "recent_timeline": patient_timeline(db, user.id, 0, 101)[:100],
        "timeline_limit": 100,
        "assessments": [
            serialize_assessment(row)
            for row in db.scalars(
                select(Assessment)
                .where(Assessment.patient_id == user.id, Assessment.removed_at.is_(None))
                .order_by(Assessment.created_at.desc())
                .limit(20)
            ).all()
        ],
        "notice": "A summary of patient-entered records and saved screening results. "
        "Clinical validation is pending. Review results with a qualified clinician; "
        "a LOW category does not rule out complications.",
    }


@router.get("/pregnancy-tracker")
def pregnancy_tracker(user: User = Depends(patient), db: Session = Depends(get_db)):
    profile = db.get(PatientProfile, user.id)
    latest = db.scalar(
        select(HealthRecord)
        .where(HealthRecord.patient_id == user.id, HealthRecord.removed_at.is_(None))
        .order_by(HealthRecord.created_at.desc(), HealthRecord.id)
        .limit(1)
    )
    today = utc_now().date()
    weeks, source, recorded = None, None, None
    if profile and profile.due_date:
        weeks = (280 - (profile.due_date - today).days) / 7
        source, recorded = "due_date", profile.due_date.isoformat()
    elif latest:
        days = (today - utc(latest.created_at).date()).days
        weeks = latest.observations["gestational_weeks"] + days / 7
        source, recorded = "recorded_week", utc(latest.created_at).date().isoformat()
    needs_update = weeks is not None and not 0 <= weeks <= 45
    if needs_update:
        weeks = None
    trimester = (
        1
        if weeks is not None and weeks < 14
        else 2
        if weeks is not None and weeks < 28
        else 3
        if weeks is not None
        else None
    )
    milestones = [
        {
            "week": 8,
            "title": "Your care team",
            "detail": "Keep your care contact and pregnancy dates together.",
        },
        {
            "week": 12,
            "title": "Early pregnancy review",
            "detail": "Bring your records and questions to your antenatal discussion.",
        },
        {
            "week": 20,
            "title": "Mid-pregnancy planning",
            "detail": "Review your appointment plan and discuss concerns with your care team.",
        },
        {
            "week": 28,
            "title": "Third trimester",
            "detail": "Keep your latest reports and prescribed medication list up to date.",
        },
        {
            "week": 36,
            "title": "Birth preparation",
            "detail": "Discuss birth preferences, transport and care contacts with your team.",
        },
        {
            "week": 40,
            "title": "Due-date discussion",
            "detail": "Confirm the next follow-up plan with your maternity team.",
        },
    ]
    return {
        "estimated_weeks": round(weeks, 1) if weeks is not None else None,
        "trimester": trimester,
        "source": source,
        "source_date": recorded,
        "needs_date_update": needs_update,
        "milestones": milestones,
        "guidance": {
            1: "Keep pregnancy dates, questions and early care records together.",
            2: "Review your care schedule and keep recording actual observations.",
            3: "Prepare your health summary and discuss birth and follow-up arrangements.",
        }.get(trimester),
        "source_url": "https://www.nhs.uk/pregnancy/week-by-week/",
        "notice": (
            "Planning milestones are general guidance, "
            "not a prescribed appointment or test schedule."
        ),
    }
