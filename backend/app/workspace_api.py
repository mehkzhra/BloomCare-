"""Small, role-scoped dashboard projections with database totals, never demo values."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.admin_api import account_out
from app.appointment_service import approved_doctor, serialize_appointment
from app.assessment_service import serialize_assessment, timestamp
from app.care_api import pregnancy_tracker
from app.clinical_service import doctor_analytics, doctor_cases, doctor_record_ids
from app.config import get_settings
from app.database import get_db
from app.integration_status import service_configuration
from app.models import (
    AccountEvent,
    Appointment,
    Assessment,
    ClinicalReview,
    DoctorProfile,
    HealthRecord,
    MedicalReport,
    MedicationEntry,
    Notification,
    User,
    utc_now,
)
from app.security import require_role

router = APIRouter(prefix="/api")


def count(model, *criteria):
    return select(func.count()).select_from(model).where(*criteria).scalar_subquery()


def totals(db, values):
    """Independent dashboard totals share one database round trip."""
    return dict(zip(values, db.execute(select(*values.values())).one(), strict=True))


def appointments(db, user, limit=4):
    owner = Appointment.patient_id if user.role == "patient" else Appointment.doctor_id
    rows = db.scalars(
        select(Appointment)
        .where(
            owner == user.id,
            Appointment.status.in_(["PENDING", "ACCEPTED"]),
            Appointment.scheduled_at >= utc_now(),
        )
        .order_by(Appointment.scheduled_at, Appointment.id)
        .limit(limit)
    ).all()
    return [serialize_appointment(db, row) for row in rows]


@router.get("/patients/me/workspace")
def patient_workspace(user: User = Depends(require_role("patient")), db: Session = Depends(get_db)):
    records = db.scalars(
        select(HealthRecord)
        .where(HealthRecord.patient_id == user.id, HealthRecord.removed_at.is_(None))
        .order_by(HealthRecord.created_at.desc(), HealthRecord.id)
        .limit(7)
    ).all()
    latest = db.scalar(
        select(Assessment)
        .where(Assessment.patient_id == user.id, Assessment.removed_at.is_(None))
        .order_by(Assessment.created_at.desc(), Assessment.id)
        .limit(1)
    )
    urgent = db.scalars(
        select(Assessment)
        .join(ClinicalReview)
        .where(
            Assessment.patient_id == user.id,
            Assessment.removed_at.is_(None),
            ClinicalReview.status == "URGENT_FOLLOW_UP",
        )
        .order_by(ClinicalReview.updated_at.desc())
        .limit(3)
    ).all()
    team = db.execute(
        select(User, DoctorProfile)
        .join(DoctorProfile)
        .where(
            User.role == "doctor",
            User.active.is_(True),
            DoctorProfile.approved.is_(True),
        )
        .order_by(User.full_name, User.id)
        .limit(3)
    ).all()
    return {
        "generated_at": utc_now(),
        "counts": totals(
            db,
            {
                "records": count(
                    HealthRecord,
                    HealthRecord.patient_id == user.id,
                    HealthRecord.removed_at.is_(None),
                ),
                "assessments": count(
                    Assessment, Assessment.patient_id == user.id, Assessment.removed_at.is_(None)
                ),
                "reports": count(MedicalReport, MedicalReport.patient_id == user.id),
                "medications": count(
                    MedicationEntry,
                    MedicationEntry.patient_id == user.id,
                    MedicationEntry.active.is_(True),
                ),
                "unread_notifications": count(
                    Notification, Notification.recipient_id == user.id, Notification.read.is_(False)
                ),
            },
        ),
        "records": [
            {"id": r.id, "observations": r.observations, "created_at": timestamp(r.created_at)}
            for r in records
        ],
        "latest_assessment": serialize_assessment(latest) if latest else None,
        "urgent_reviews": [serialize_assessment(a) for a in urgent],
        "appointments": appointments(db, user),
        "pregnancy": pregnancy_tracker(user, db),
        "care_team": [
            {"id": u.id, "full_name": u.full_name, "specialty": p.specialty} for u, p in team
        ],
    }


@router.get("/doctors/me/workspace")
def doctor_workspace(user: User = Depends(require_role("doctor")), db: Session = Depends(get_db)):
    profile = db.get(DoctorProfile, user.id)
    enabled = approved_doctor(db, user.id)
    result = {
        "generated_at": utc_now(),
        "profile": {
            "full_name": user.full_name,
            "specialty": profile.specialty if profile else "",
            "registration_number": profile.registration_number if profile else "",
            "approved": enabled,
        },
        "counts": {"requests": 0, "confirmed": 0, "patients": 0, "awaiting_review": 0, "urgent": 0},
        "appointments": [],
        "priority_cases": [],
        "analytics": None,
    }
    if not enabled:
        return result
    analytics = doctor_analytics(db, user)
    people = (
        select(HealthRecord.patient_id)
        .where(HealthRecord.id.in_(doctor_record_ids(user.id)))
        .distinct()
        .subquery()
    )
    now = utc_now()
    result.update(
        counts=totals(
            db,
            {
                "requests": count(
                    Appointment,
                    Appointment.doctor_id == user.id,
                    Appointment.status == "PENDING",
                    Appointment.scheduled_at >= now,
                ),
                "confirmed": count(
                    Appointment,
                    Appointment.doctor_id == user.id,
                    Appointment.status == "ACCEPTED",
                    Appointment.scheduled_at >= now,
                ),
                "patients": db.scalar(select(func.count()).select_from(people)),
                "awaiting_review": analytics["review_statuses"].get("PENDING", 0),
                "urgent": analytics["review_statuses"].get("URGENT_FOLLOW_UP", 0),
            },
        ),
        appointments=appointments(db, user, 5),
        priority_cases=(
            doctor_cases(db, user, "", None, "URGENT_FOLLOW_UP", 0)[:3]
            + doctor_cases(db, user, "", None, "PENDING", 0)[:3]
        )[:5],
        analytics=analytics,
    )
    return result


@router.get("/admin/workspace")
def admin_workspace(_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    pending_query = (
        select(User)
        .join(DoctorProfile)
        .where(
            User.role == "doctor",
            User.active.is_(True),
            DoctorProfile.approved.is_(False),
        )
    )
    review_status = func.coalesce(ClinicalReview.status, "PENDING")
    reviews = dict(
        db.execute(
            select(review_status, func.count())
            .select_from(Assessment)
            .outerjoin(ClinicalReview)
            .where(Assessment.removed_at.is_(None))
            .group_by(review_status)
        ).all()
    )
    risk = dict(
        db.execute(
            select(Assessment.maternal_risk, func.count())
            .where(Assessment.removed_at.is_(None))
            .group_by(Assessment.maternal_risk)
        ).all()
    )
    events = db.scalars(
        select(AccountEvent).order_by(AccountEvent.created_at.desc(), AccountEvent.id).limit(5)
    ).all()
    actor_names = (
        dict(
            db.execute(
                select(User.id, User.full_name).where(User.id.in_({e.actor_id for e in events}))
            ).all()
        )
        if events
        else {}
    )
    settings = get_settings()
    return {
        "generated_at": utc_now(),
        "counts": totals(
            db,
            {
                "patients": count(User, User.role == "patient"),
                "doctors": count(User, User.role == "doctor"),
                "active_accounts": count(User, User.active.is_(True)),
                "assessments": count(Assessment, Assessment.removed_at.is_(None)),
                "removed_assessments": count(Assessment, Assessment.removed_at.is_not(None)),
                "pending_doctors": db.scalar(
                    select(func.count()).select_from(pending_query.subquery())
                ),
                "urgent": reviews.get("URGENT_FOLLOW_UP", 0),
                "awaiting_review": reviews.get("PENDING", 0),
                "appointments": count(Appointment),
            },
        ),
        "pending_doctors": [
            account_out(u)
            for u in db.scalars(pending_query.order_by(User.created_at, User.id).limit(5))
        ],
        "risk_categories": risk,
        "review_statuses": reviews,
        "recent_activity": [
            {
                "id": e.id,
                "actor": actor_names.get(e.actor_id, "Deleted account"),
                "action": e.action,
                "created_at": timestamp(e.created_at),
            }
            for e in events
        ],
        "integrations": {
            "database": "CONNECTED",
            **{key: value["status"] for key, value in service_configuration(settings).items()},
        },
        "service_configuration": service_configuration(settings),
    }
