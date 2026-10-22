import hashlib
import secrets
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.appointment_service import utc
from app.assessment_service import serialize_assessment
from app.care_api import medication_out, symptom_out
from app.communication_api import downloadable
from app.database import get_db
from app.models import (
    AccountEvent,
    Assessment,
    FamilyGrant,
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

router = APIRouter(prefix="/api/family")
patient = require_role("patient")
Scope = Literal["profile", "observations", "assessments", "symptoms", "medications", "reports"]


class InvitationInput(Input):
    recipient_email: EmailStr
    scopes: list[Scope] = Field(min_length=1, max_length=6)
    access_days: Literal[7, 30] = 7
    consent: bool = Field(strict=True)

    @field_validator("recipient_email")
    @classmethod
    def lower(cls, value):
        return str(value).lower()

    @field_validator("scopes")
    @classmethod
    def unique(cls, values):
        return sorted(set(values))


class AcceptInput(Input):
    code: str = Field(min_length=30, max_length=100)


def grant_out(db, grant):
    return {
        "id": grant.id,
        "owner_name": db.get(User, grant.owner_id).full_name,
        "recipient_email": grant.recipient_email,
        "scopes": grant.scopes,
        "accepted": grant.reader_id is not None,
        "revoked": grant.revoked,
        "access_until": utc(grant.access_until),
    }


def authorized(db, grant_id, reader):
    grant = db.scalar(
        select(FamilyGrant).where(FamilyGrant.id == grant_id, FamilyGrant.reader_id == reader.id)
    )
    if not grant:
        raise HTTPException(404, "Family share not found")
    owner = db.get(User, grant.owner_id)
    if grant.revoked or utc(grant.access_until) <= utc_now() or not owner or not owner.active:
        raise HTTPException(403, "Family access has expired or been revoked")
    return grant


@router.post("/invitations", status_code=201)
def invite(data: InvitationInput, user: User = Depends(patient), db: Session = Depends(get_db)):
    if not data.consent:
        raise HTTPException(422, "Consent is required to share selected categories")
    if data.recipient_email == user.email:
        raise HTTPException(422, "Choose a different family member email")
    token = secrets.token_urlsafe(32)
    row = FamilyGrant(
        owner_id=user.id,
        recipient_email=data.recipient_email,
        scopes=data.scopes,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        invite_expires_at=utc_now() + timedelta(hours=48),
        access_until=utc_now() + timedelta(days=data.access_days),
    )
    db.add(row)
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="FAMILY_INVITED"))
    db.commit()
    return {**grant_out(db, row), "invitation_code": token}


@router.post("/accept")
def accept(data: AcceptInput, user: User = Depends(patient), db: Session = Depends(get_db)):
    row = db.scalar(
        select(FamilyGrant)
        .where(
            FamilyGrant.token_hash == hashlib.sha256(data.code.encode()).hexdigest(),
            FamilyGrant.recipient_email == user.email,
        )
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Invitation not found for this email")
    if row.reader_id == user.id and not row.revoked and utc(row.access_until) > utc_now():
        return grant_out(db, row)
    if row.revoked or row.reader_id or utc(row.invite_expires_at) <= utc_now():
        raise HTTPException(403, "Invitation is no longer available")
    owner = db.get(User, row.owner_id)
    if not owner or not owner.active:
        raise HTTPException(403, "Invitation is no longer available")
    row.reader_id = user.id
    db.add(AccountEvent(actor_id=user.id, subject_id=owner.id, action="FAMILY_ACCEPTED"))
    db.commit()
    return grant_out(db, row)


@router.get("/grants")
def grants(user: User = Depends(patient), db: Session = Depends(get_db)):
    return {
        "owned": [
            grant_out(db, r)
            for r in db.scalars(
                select(FamilyGrant)
                .where(FamilyGrant.owner_id == user.id)
                .order_by(FamilyGrant.created_at.desc())
                .limit(100)
            )
        ],
        "received": [
            grant_out(db, r)
            for r in db.scalars(
                select(FamilyGrant)
                .where(FamilyGrant.reader_id == user.id)
                .order_by(FamilyGrant.created_at.desc())
                .limit(100)
            )
        ],
    }


@router.delete("/grants/{grant_id}", status_code=204)
def revoke(grant_id: str, user: User = Depends(patient), db: Session = Depends(get_db)):
    row = db.scalar(
        select(FamilyGrant).where(FamilyGrant.id == grant_id, FamilyGrant.owner_id == user.id)
    )
    if not row:
        raise HTTPException(404, "Family share not found")
    row.revoked = True
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="FAMILY_REVOKED"))
    db.commit()


@router.get("/grants/{grant_id}/records")
def records(grant_id: str, user: User = Depends(patient), db: Session = Depends(get_db)):
    row = authorized(db, grant_id, user)
    result = {"grant": grant_out(db, row), "limit_per_section": 50}
    if "profile" in row.scopes:
        profile = db.get(PatientProfile, row.owner_id)
        result["profile"] = (
            {
                k: getattr(profile, k)
                for k in ("date_of_birth", "due_date", "phone", "preferred_language")
            }
            if profile
            else {}
        )
    for scope, model in (
        ("observations", HealthRecord),
        ("assessments", Assessment),
        ("symptoms", SymptomEntry),
        ("medications", MedicationEntry),
        ("reports", MedicalReport),
    ):
        if scope not in row.scopes:
            continue
        active = [model.removed_at.is_(None)] if model in {Assessment, HealthRecord} else []
        entries = db.scalars(
            select(model)
            .where(model.patient_id == row.owner_id, *active)
            .order_by(model.created_at.desc(), model.id)
            .limit(50)
        ).all()
        if scope == "observations":
            result[scope] = [
                {"id": e.id, "observations": e.observations, "created_at": utc(e.created_at)}
                for e in entries
            ]
        elif scope == "assessments":
            result[scope] = []
            for e in entries:
                summary = serialize_assessment(e)
                result[scope].append(
                    {
                        "id": e.id,
                        "maternal_risk": e.maternal_risk,
                        "pe_status": summary["pe_status"],
                        "pe_category": summary["pe_screening"]["risk"]
                        if summary["pe_screening"]
                        else None,
                        "review_status": (summary["clinical_review"] or {}).get(
                            "status", "PENDING"
                        ),
                        "created_at": utc(e.created_at),
                    }
                )
        elif scope == "symptoms":
            result[scope] = [symptom_out(e) for e in entries]
        elif scope == "medications":
            result[scope] = [medication_out(e) for e in entries]
        else:
            result[scope] = [
                {"id": e.id, "title": e.title, "media_type": e.media_type} for e in entries
            ]
    return result


@router.get("/grants/{grant_id}/reports/{report_id}/download")
def report_download(
    grant_id: str, report_id: str, user: User = Depends(patient), db: Session = Depends(get_db)
):
    row = authorized(db, grant_id, user)
    if "reports" not in row.scopes:
        raise HTTPException(403, "Reports were not included in this family share")
    report = db.scalar(
        select(MedicalReport).where(
            MedicalReport.id == report_id, MedicalReport.patient_id == row.owner_id
        )
    )
    if not report:
        raise HTTPException(404, "Report not found")
    return downloadable(report)
