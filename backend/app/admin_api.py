from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AccountEvent,
    Appointment,
    AppointmentEvent,
    Assessment,
    DoctorNote,
    DoctorProfile,
    User,
)
from app.schemas import AccountStatus, DoctorApproval
from app.security import require_role

router = APIRouter(prefix="/api/admin")
admin = require_role("admin")


def account_out(user):
    profile = user.doctor_profile
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "active": user.active,
        "created_at": user.created_at,
        "approved": profile.approved if profile else None,
        "registration_number": profile.registration_number if profile else None,
        "specialty": profile.specialty if profile else None,
    }


@router.get("/accounts")
def accounts(
    _user: User = Depends(admin),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0, le=100000),
    q: str = Query("", max_length=80),
    role: Literal["patient", "doctor", "admin"] | None = None,
    active: bool | None = None,
    approval: Literal["pending", "approved"] | None = None,
):
    query = select(User)
    if q:
        query = query.where(User.full_name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%"))
    if role:
        query = query.where(User.role == role)
    if active is not None:
        query = query.where(User.active.is_(active))
    if approval:
        query = query.join(DoctorProfile).where(
            User.role == "doctor", DoctorProfile.approved.is_(approval == "approved")
        )
    return [
        account_out(u)
        for u in db.scalars(
            query.order_by(User.created_at.desc(), User.id).offset(offset).limit(50)
        ).all()
    ]


@router.patch("/accounts/{user_id}/status")
def status(
    user_id: str, data: AccountStatus, actor: User = Depends(admin), db: Session = Depends(get_db)
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Account not found")
    if user.role == "admin":
        raise HTTPException(403, "Administrator accounts cannot be changed here")
    if user.active != data.active:
        user.active = data.active
        db.add(
            AccountEvent(
                actor_id=actor.id,
                subject_id=user.id,
                action="ACCOUNT_ENABLED" if data.active else "ACCOUNT_DISABLED",
            )
        )
        db.commit()
    return account_out(user)


@router.patch("/doctors/{user_id}/approval")
def approval(
    user_id: str, data: DoctorApproval, actor: User = Depends(admin), db: Session = Depends(get_db)
):
    user = db.get(User, user_id)
    if not user or user.role != "doctor" or not user.doctor_profile:
        raise HTTPException(404, "Doctor not found")
    if user.doctor_profile.approved != data.approved:
        user.doctor_profile.approved = data.approved
        db.add(
            AccountEvent(
                actor_id=actor.id,
                subject_id=user.id,
                action="DOCTOR_APPROVED" if data.approved else "DOCTOR_APPROVAL_REVOKED",
            )
        )
        db.commit()
    return account_out(user)


@router.get("/appointments")
def appointments(
    _user: User = Depends(admin),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0, le=100000),
):
    return [
        {
            "id": a.id,
            "patient": db.get(User, a.patient_id).full_name,
            "doctor": db.get(User, a.doctor_id).full_name,
            "scheduled_at": a.scheduled_at,
            "status": a.status,
        }
        for a in db.scalars(
            select(Appointment)
            .order_by(Appointment.created_at.desc(), Appointment.id)
            .offset(offset)
            .limit(50)
        )
    ]


@router.get("/activity")
def activity(
    _user: User = Depends(admin),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0, le=100000),
):
    # Operational metadata only: no passwords, tokens, measurements or note bodies.
    # Each source is limited to the prefix needed for this page.
    rows = []
    for model in (AccountEvent, AppointmentEvent, Assessment, DoctorNote):
        for event in db.scalars(
            select(model).order_by(model.created_at.desc(), model.id).limit(offset + 50)
        ):
            if isinstance(event, AccountEvent):
                actor, subject, action = event.actor_id, event.subject_id, event.action
            elif isinstance(event, AppointmentEvent):
                actor, subject = event.actor_id, event.appointment_id
                action = "APPOINTMENT_" + event.to_status
            elif isinstance(event, Assessment):
                actor, subject, action = (
                    event.patient_id,
                    event.health_record_id,
                    "ASSESSMENT_SAVED",
                )
            else:
                actor, subject, action = (
                    event.author_id,
                    event.appointment_id,
                    "CLINICIAN_NOTE_SAVED",
                )
            rows.append(
                {
                    "id": event.id,
                    "actor": db.get(User, actor).full_name,
                    "subject_id": subject,
                    "action": action,
                    "created_at": event.created_at.isoformat(),
                }
            )
    rows.sort(key=lambda r: (r["created_at"], r["id"]), reverse=True)
    return rows[offset : offset + 50]
