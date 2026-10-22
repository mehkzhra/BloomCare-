from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from sqlalchemy import String, cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.account_security import registration_delivery
from app.assessment_service import (
    assess_patient,
    own_record,
    require_active_assessment,
    require_active_record,
    serialize_assessment,
)
from app.auth_limits import enforce
from app.config import get_settings
from app.database import get_db
from app.delivery_schemas import HealthRecordInput
from app.maternal_model import ModelUnavailable, get_maternal_model, model_summary
from app.models import (
    AccountEvent,
    Appointment,
    Assessment,
    ClinicalReview,
    DoctorProfile,
    HealthRecord,
    ModelVersion,
    PatientProfile,
    User,
)
from app.pe_contract import input_contract
from app.pe_model import PEModelUnavailable, get_pe_model, pe_summary
from app.pe_service import run_pe_stage
from app.query_filters import time_range
from app.schemas import (
    AssessmentInput,
    AssessmentOut,
    DoctorRegister,
    HealthOut,
    Login,
    PEAdditionalInput,
    ProfileOut,
    ProfileUpdate,
    Register,
    UserOut,
)
from app.security import (
    DUMMY_HASH,
    current_user,
    hasher,
    issue_token,
    require_role,
    verify_password,
)

router = APIRouter(prefix="/api")
patient = require_role("patient")


@router.post("/auth/register", response_model=UserOut, status_code=201)
def register(
    data: Register, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)
):
    enforce(db, request, "register")
    user = User(
        email=str(data.email),
        full_name=data.full_name,
        password_hash=hasher.hash(data.password),
        role="patient",
    )
    user.patient_profile = PatientProfile()
    db.add(user)
    try:
        db.flush()
        db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="PATIENT_REGISTERED"))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists") from None
    registration_delivery(db, user, background)
    result = UserOut.model_validate(user)
    result.email_verification_required = get_settings().auth_require_email_verification
    return result


@router.post("/auth/login", response_model=UserOut)
def login(data: Login, response: Response, request: Request, db: Session = Depends(get_db)):
    enforce(db, request, "login", str(data.email))
    user = db.scalar(select(User).where(User.email == str(data.email)))
    valid = verify_password(user.password_hash if user else DUMMY_HASH, data.password)
    if not valid or not user or not user.active:
        raise HTTPException(401, "Email or password is incorrect")
    if data.role is not None and data.role != user.role:
        raise HTTPException(401, "Email, password, or selected role is incorrect")
    if get_settings().auth_require_email_verification and user.email_verified_at is None:
        raise HTTPException(403, {
            "code": "EMAIL_VERIFICATION_REQUIRED",
            "message": (
                "Verify your email before signing in. "
                "Request a new verification link if needed."
            ),
        })
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="SIGNED_IN"))
    db.commit()
    request.state.actor_id = user.id
    settings = get_settings()
    response.set_cookie(
        "bloomcare_session",
        issue_token(user),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/api",
        max_age=settings.jwt_minutes * 60,
    )
    return user


@router.post("/auth/logout", status_code=204)
def logout(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="SIGNED_OUT"))
    db.commit()
    response.delete_cookie("bloomcare_session", path="/api", samesite="strict")


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.get("/patients/me/profile", response_model=ProfileOut)
def get_profile(user: User = Depends(patient), db: Session = Depends(get_db)):
    return db.get(PatientProfile, user.id)


@router.put("/patients/me/profile", response_model=ProfileOut)
def update_profile(
    data: ProfileUpdate, user: User = Depends(patient), db: Session = Depends(get_db)
):
    profile = db.get(PatientProfile, user.id)
    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="PROFILE_UPDATED"))
    db.commit()
    return profile


@router.post("/patients/me/health-records", response_model=HealthOut, status_code=201)
def save_health(
    data: HealthRecordInput, user: User = Depends(patient), db: Session = Depends(get_db)
):
    observations = data.model_dump(exclude={"clinical_indicators", "request_id"})
    clinical = (
        data.clinical_indicators.model_dump(exclude_none=True) if data.clinical_indicators else None
    )
    request_id = str(data.request_id) if data.request_id else None
    existing_query = select(HealthRecord).where(
        HealthRecord.patient_id == user.id, HealthRecord.client_request_id == request_id
    )
    if request_id:
        existing = db.scalar(existing_query)
        if existing:
            require_active_record(existing)
            if existing.observations != observations or existing.clinical_indicators != clinical:
                raise HTTPException(
                    409, "This record request ID already has different measurements"
                )
            return existing
    record = HealthRecord(
        patient_id=user.id,
        observations=observations,
        clinical_indicators=clinical,
        client_request_id=request_id,
    )
    db.add(record)
    db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="HEALTH_RECORD_SAVED"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(existing_query) if request_id else None
        if (
            existing
            and existing.observations == observations
            and existing.clinical_indicators == clinical
        ):
            return require_active_record(existing)
        raise HTTPException(
            409, "This health record request conflicts with a saved request"
        ) from None
    return record


@router.get("/patients/me/health-records", response_model=list[HealthOut])
def health_history(
    user: User = Depends(patient),
    db: Session = Depends(get_db),
    offset: int = 0,
    q: str = Query("", max_length=80),
    from_date: date | None = None,
    to_date: date | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
):
    if offset < 0 or offset > 100000:
        raise HTTPException(422, "Invalid history offset")
    query = select(HealthRecord).where(
        HealthRecord.patient_id == user.id, HealthRecord.removed_at.is_(None)
    )
    if q:
        query = query.where(cast(HealthRecord.observations, String).ilike(f"%{q}%"))
    query = date_range(query, HealthRecord.created_at, from_date, to_date)
    query = time_range(query, HealthRecord.created_at, from_at, to_at)
    return db.scalars(
        query.order_by(HealthRecord.created_at.desc(), HealthRecord.id.desc())
        .offset(offset)
        .limit(50)
    ).all()


def date_range(query, column, start, end):
    if start and end and start > end:
        raise HTTPException(422, "The start date must not be after the end date")
    if start:
        query = query.where(column >= datetime.combine(start, datetime.min.time(), timezone.utc))
    if end:
        query = query.where(
            column < datetime.combine(end + timedelta(days=1), datetime.min.time(), timezone.utc)
        )
    return query


@router.post("/patients/me/complete-assessment", response_model=AssessmentOut)
def complete_assessment(
    data: HealthRecordInput,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    record = save_health(data, user, db)
    try:
        return assess_patient(db, user.id, record.id)
    except HTTPException as error:
        detail = error.detail if isinstance(error.detail, dict) else {"message": error.detail}
        raise HTTPException(error.status_code, {**detail, "health_record_id": record.id}) from None


@router.get("/patients/me/health-records/{record_id}", response_model=HealthOut)
def health_detail(record_id: str, user: User = Depends(patient), db: Session = Depends(get_db)):
    return own_record(db, user.id, record_id)


@router.get("/capabilities")
def capabilities(_user: User = Depends(current_user)):
    state = {
        "checkpoint": "pe_screening",
        "pregnancy_model_ready": False,
        "pe_model_ready": False,
        "appointments_ready": True,
        "family_access_ready": True,
        "reminders_ready": True,
        "consultation_signaling_ready": True,
        "interface_languages": ["en", "ur"],
        "research_only": True,
        "maternal_model": None,
        "care_plans_ready": bool(get_settings().groq_api_key),
        "pe_trigger_mode": "risk_or_warning_indicators",
        "reason": "Experimental maternal-risk assessment is currently unavailable",
    }
    try:
        model = get_maternal_model()
        state.update(
            pregnancy_model_ready=True,
            assessment_ranges=model.manifest["observed_training_ranges"],
            maternal_model=model_summary(model.manifest),
            reason="Experimental maternal-risk assessment is available for supported measurements",
        )
    except ModelUnavailable:
        pass
    try:
        pe = get_pe_model()
        state.update(
            pe_model_ready=True, pe_input_fields=input_contract(), pe_model=pe_summary(pe.manifest)
        )
    except PEModelUnavailable:
        pass
    return state


@router.post("/patients/me/assessments", response_model=AssessmentOut)
def assess(
    data: AssessmentInput,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    return assess_patient(db, user.id, str(data.health_record_id))


@router.get("/patients/me/assessments", response_model=list[AssessmentOut])
def assessment_history(
    user: User = Depends(patient),
    db: Session = Depends(get_db),
    offset: int = 0,
    risk: Literal["LOW", "MEDIUM", "HIGH"] | None = None,
    q: str = Query("", max_length=80),
    from_date: date | None = None,
    to_date: date | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    review_status: Literal["PENDING", "REVIEWED", "URGENT_FOLLOW_UP"] | None = None,
):
    if offset < 0 or offset > 100000:
        raise HTTPException(422, "Invalid history offset")
    query = select(Assessment).where(
        Assessment.patient_id == user.id, Assessment.removed_at.is_(None)
    )
    if risk:
        query = query.where(Assessment.maternal_risk == risk)
    if q:
        query = query.where(cast(Assessment.observations_snapshot, String).ilike(f"%{q}%"))
    query = date_range(query, Assessment.created_at, from_date, to_date)
    query = time_range(query, Assessment.created_at, from_at, to_at)
    if review_status:
        query = query.outerjoin(
            ClinicalReview, ClinicalReview.assessment_id == Assessment.id
        ).where(func.coalesce(ClinicalReview.status, "PENDING") == review_status)
    rows = db.scalars(
        query.order_by(Assessment.created_at.desc(), Assessment.id.desc()).offset(offset).limit(50)
    ).all()
    return [serialize_assessment(row) for row in rows]


@router.get(
    "/patients/me/health-records/{record_id}/assessments", response_model=list[AssessmentOut]
)
def record_assessments(
    record_id: str,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    own_record(db, user.id, record_id)
    rows = db.scalars(
        select(Assessment)
        .where(
            Assessment.health_record_id == record_id,
            Assessment.patient_id == user.id,
            Assessment.removed_at.is_(None),
        )
        .order_by(Assessment.created_at.desc(), Assessment.id.desc())
        .limit(50)
    ).all()
    return [serialize_assessment(row) for row in rows]


def own_assessment(db: Session, patient_id: str, assessment_id: str):
    row = db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.patient_id == patient_id,
        )
    )
    if not row:
        raise HTTPException(404, "Assessment not found")
    return require_active_assessment(row)


@router.get("/patients/me/assessments/{assessment_id}", response_model=AssessmentOut)
def assessment_detail(
    assessment_id: str,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    return serialize_assessment(own_assessment(db, user.id, assessment_id))


@router.post("/patients/me/assessments/{assessment_id}/pe", response_model=AssessmentOut)
def pe_stage(
    assessment_id: str,
    data: PEAdditionalInput | None = None,
    user: User = Depends(patient),
    db: Session = Depends(get_db),
):
    return run_pe_stage(db, user.id, assessment_id, data)


@router.get("/doctors")
def doctors(_user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(User, DoctorProfile)
        .join(DoctorProfile)
        .where(User.active.is_(True), DoctorProfile.approved.is_(True))
    )
    return [
        {"id": user.id, "full_name": user.full_name, "specialty": profile.specialty}
        for user, profile in rows
    ]


@router.get("/doctors/me/profile")
def doctor_me(user: User = Depends(require_role("doctor")), db: Session = Depends(get_db)):
    profile = db.get(DoctorProfile, user.id)
    return {
        "full_name": user.full_name,
        "specialty": profile.specialty,
        "registration_number": profile.registration_number,
        "approved": profile.approved,
    }


@router.get("/admin/stats")
def stats(_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    counts = dict(db.execute(select(User.role, func.count(User.id)).group_by(User.role)).all())
    return {
        "patients": counts.get("patient", 0),
        "doctors": counts.get("doctor", 0),
        "admins": counts.get("admin", 0),
        "health_records": db.scalar(
            select(func.count()).select_from(HealthRecord).where(HealthRecord.removed_at.is_(None))
        ),
        "assessments": db.scalar(
            select(func.count()).select_from(Assessment).where(Assessment.removed_at.is_(None))
        ),
        "appointments": db.scalar(select(func.count()).select_from(Appointment)),
        "high_risk_cases": db.scalar(
            select(func.count())
            .select_from(Assessment)
            .where(Assessment.maternal_risk == "HIGH", Assessment.removed_at.is_(None))
        ),
        "urgent_follow_ups": db.scalar(
            select(func.count())
            .select_from(ClinicalReview)
            .join(Assessment)
            .where(ClinicalReview.status == "URGENT_FOLLOW_UP", Assessment.removed_at.is_(None))
        ),
        "reviewed_assessments": db.scalar(
            select(func.count())
            .select_from(ClinicalReview)
            .join(Assessment)
            .where(ClinicalReview.status == "REVIEWED", Assessment.removed_at.is_(None))
        ),
    }


@router.get("/admin/model-evaluation")
def admin_model_evaluation(
    _user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    active = None
    try:
        active = model_summary(get_maternal_model().manifest)
    except ModelUnavailable:
        pass
    rows = db.scalars(
        select(ModelVersion).order_by(ModelVersion.registered_at.desc()).limit(20)
    ).all()
    pe = None
    try:
        pe = pe_summary(get_pe_model().manifest)
    except PEModelUnavailable:
        pass
    return {
        "active_model": active,
        "registered_models": [model_summary(row.manifest) for row in rows],
        "pe_model_ready": pe is not None,
        "pe_model": pe,
    }


@router.post("/auth/register-doctor", response_model=UserOut, status_code=201)
def register_doctor(
    data: DoctorRegister, request: Request, background: BackgroundTasks,
    db: Session = Depends(get_db)
):
    enforce(db, request, "register")
    user = User(
        email=str(data.email),
        full_name=data.full_name,
        password_hash=hasher.hash(data.password),
        role="doctor",
    )
    user.doctor_profile = DoctorProfile(
        registration_number=data.registration_number, specialty=data.specialty, approved=False
    )
    db.add(user)
    try:
        db.flush()
        db.add(AccountEvent(actor_id=user.id, subject_id=user.id, action="DOCTOR_REGISTERED"))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email or registration number is already registered") from None
    registration_delivery(db, user, background)
    result = UserOut.model_validate(user)
    result.email_verification_required = get_settings().auth_require_email_verification
    return result
