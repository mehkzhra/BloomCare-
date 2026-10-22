import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.communication_api import episode
from app.database import get_db
from app.integration_status import parse_ice_servers
from app.models import AccountEvent, Consultation, ConsultationSignal, User, utc_now
from app.notifications import notify
from app.schemas import Input
from app.security import current_user, require_role

router = APIRouter(prefix="/api")


class SignalInput(Input):
    kind: Literal["offer", "answer", "candidate"]
    payload: dict

    @field_validator("payload")
    @classmethod
    def bounded(cls, value):
        if len(json.dumps(value)) > 32000:
            raise ValueError("Signal exceeds the size limit")
        return value


def live_call(db, call_id, user):
    row = db.get(Consultation, call_id)
    if not row:
        raise HTTPException(404, "Consultation not found")
    episode(db, row.appointment_id, user, active=True)
    if row.ended_at:
        raise HTTPException(409, "Consultation has ended")
    return row


def ice_servers():
    from app.config import get_settings

    try:
        return parse_ice_servers(get_settings().webrtc_ice_servers)
    except ValueError:
        raise HTTPException(503, "Consultation network configuration is invalid") from None


@router.get("/appointments/{appointment_id}/consultation")
def consultation(
    appointment_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    episode(db, appointment_id, user, active=True)
    row = db.scalar(
        select(Consultation)
        .where(Consultation.appointment_id == appointment_id, Consultation.ended_at.is_(None))
        .order_by(Consultation.created_at.desc())
    )
    return {"id": row.id if row else None, "ice_servers": ice_servers()}


@router.post("/appointments/{appointment_id}/consultation", status_code=201)
def start(
    appointment_id: str, user: User = Depends(require_role("doctor")), db: Session = Depends(get_db)
):
    appointment = episode(db, appointment_id, user, active=True)
    row = db.scalar(
        select(Consultation).where(
            Consultation.appointment_id == appointment_id, Consultation.ended_at.is_(None)
        )
    )
    if row is None:
        row = Consultation(appointment_id=appointment_id, started_by=user.id)
        db.add(row)
        notify(db, appointment.patient_id, "CONSULTATION_STARTED", appointment.id)
        db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="CONSULTATION_STARTED"))
        db.commit()
    return {"id": row.id, "ice_servers": ice_servers()}


@router.get("/consultations/{call_id}/signals")
def signals(
    call_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    after: int = Query(0, ge=0),
):
    live_call(db, call_id, user)
    return [
        {"id": r.id, "kind": r.kind, "payload": r.payload}
        for r in db.scalars(
            select(ConsultationSignal)
            .where(
                ConsultationSignal.consultation_id == call_id,
                ConsultationSignal.sender_id != user.id,
                ConsultationSignal.id > after,
            )
            .order_by(ConsultationSignal.id)
            .limit(100)
        )
    ]


@router.post("/consultations/{call_id}/signals", status_code=201)
def signal(
    call_id: str,
    data: SignalInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = live_call(db, call_id, user)
    # Keep a bounded per-connection signaling history.
    from sqlalchemy import func

    if (
        db.scalar(
            select(func.count())
            .select_from(ConsultationSignal)
            .where(ConsultationSignal.consultation_id == row.id)
        )
        >= 500
    ):
        raise HTTPException(429, "Consultation signaling limit reached")
    item = ConsultationSignal(
        consultation_id=row.id, sender_id=user.id, kind=data.kind, payload=data.payload
    )
    db.add(item)
    db.commit()
    return {"id": item.id}


@router.post("/consultations/{call_id}/end")
def end(call_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(Consultation, call_id)
    if not row:
        raise HTTPException(404, "Consultation not found")
    episode(db, row.appointment_id, user)
    row.ended_at = row.ended_at or utc_now()
    db.commit()
    return {"ended": True}
