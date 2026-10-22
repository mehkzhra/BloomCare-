from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('patient', 'doctor', 'admin')", name="ck_role"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="patient")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    patient_profile: Mapped["PatientProfile | None"] = relationship(back_populates="user")
    doctor_profile: Mapped["DoctorProfile | None"] = relationship(back_populates="user")


class EmailActionToken(Base):
    __tablename__ = "email_action_tokens"
    __table_args__ = (
        CheckConstraint("purpose IN ('VERIFY_EMAIL', 'RESET_PASSWORD')", name="ck_email_purpose"),
    )

    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))
    session_version: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuthRateBucket(Base):
    __tablename__ = "auth_rate_buckets"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(Integer)


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(2), default="en")
    user: Mapped[User] = relationship(back_populates="patient_profile")


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    specialty: Mapped[str] = mapped_column(String(120), default="Obstetrics")
    registration_number: Mapped[str] = mapped_column(String(80), unique=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    user: Mapped[User] = relationship(back_populates="doctor_profile")


class HealthRecord(Base):
    __tablename__ = "health_records"
    __table_args__ = (
        UniqueConstraint("patient_id", "client_request_id", name="uq_health_record_request"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    observations: Mapped[dict] = mapped_column(JSON)
    clinical_indicators: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    client_request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    removal_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version: Mapped[str] = mapped_column(String(80))
    artifact_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    manifest: Mapped[dict] = mapped_column(JSON)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("health_record_id", "model_version_id", name="uq_assessment_record_model"),
        CheckConstraint("maternal_risk IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_assessment_risk"),
        CheckConstraint(
            "(pe_required = false AND pe_status = 'NOT_INDICATED') OR "
            "(pe_required = true AND pe_status = 'UNAVAILABLE')",
            name="ck_assessment_pe_gate",
        ),
        CheckConstraint("research_only = true", name="ck_assessment_research_only"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    health_record_id: Mapped[str] = mapped_column(ForeignKey("health_records.id"), index=True)
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"))
    observations_snapshot: Mapped[dict] = mapped_column(JSON)
    clinical_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    maternal_risk: Mapped[str] = mapped_column(String(8))
    class_scores: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[dict] = mapped_column(JSON)
    pe_required: Mapped[bool] = mapped_column(Boolean)
    pe_status: Mapped[str] = mapped_column(String(24))
    pe_reason: Mapped[str] = mapped_column(String(500))
    research_only: Mapped[bool] = mapped_column(Boolean, default=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    removal_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    model_version: Mapped[ModelVersion] = relationship(lazy="joined")
    pe_screening: Mapped["PEScreening | None"] = relationship(lazy="selectin", uselist=False)
    care_plans: Mapped[list["AssessmentCarePlan"]] = relationship(lazy="selectin")
    clinical_review: Mapped["ClinicalReview | None"] = relationship(lazy="selectin", uselist=False)


class PEScreening(Base):
    __tablename__ = "pe_screenings"
    __table_args__ = (
        UniqueConstraint("assessment_id", name="uq_pe_screening_assessment"),
        CheckConstraint("risk IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_pe_screening_risk"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    observations_snapshot: Mapped[dict] = mapped_column(JSON)
    risk: Mapped[str] = mapped_column(String(8))
    class_scores: Mapped[dict] = mapped_column(JSON)
    model_snapshot: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED', 'COMPLETED')",
            name="ck_appointment_status",
        ),
        CheckConstraint("patient_id <> doctor_id", name="ck_appointment_participants"),
        CheckConstraint(
            "(status IN ('PENDING', 'ACCEPTED') AND closed_at IS NULL) OR "
            "(status IN ('REJECTED', 'CANCELLED', 'COMPLETED') AND closed_at IS NOT NULL)",
            name="ck_appointment_closed",
        ),
        CheckConstraint(
            "(accepted_at IS NULL AND access_until IS NULL "
            "AND status IN ('PENDING', 'REJECTED', 'CANCELLED')) OR "
            "(accepted_at IS NOT NULL AND access_until IS NOT NULL "
            "AND status IN ('ACCEPTED', 'CANCELLED', 'COMPLETED'))",
            name="ck_appointment_grant",
        ),
        Index(
            "uq_appointment_doctor_slot",
            "doctor_id",
            "scheduled_at",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'ACCEPTED')"),
            sqlite_where=text("status IN ('PENDING', 'ACCEPTED')"),
        ),
        Index(
            "uq_appointment_patient_slot",
            "patient_id",
            "scheduled_at",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'ACCEPTED')"),
            sqlite_where=text("status IN ('PENDING', 'ACCEPTED')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AppointmentRecord(Base):
    __tablename__ = "appointment_records"

    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id"), primary_key=True)
    health_record_id: Mapped[str] = mapped_column(ForeignKey("health_records.id"), primary_key=True)


class AppointmentEvent(Base):
    __tablename__ = "appointment_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DoctorNote(Base):
    __tablename__ = "doctor_notes"
    __table_args__ = (UniqueConstraint("supersedes_id", name="uq_doctor_note_supersedes"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    assessment_id: Mapped[str | None] = mapped_column(ForeignKey("assessments.id"), nullable=True)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("doctor_notes.id"), nullable=True)
    body: Mapped[str] = mapped_column(String(4000))
    patient_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AccountEvent(Base):
    __tablename__ = "account_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SymptomEntry(Base):
    __tablename__ = "symptom_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    description: Mapped[str] = mapped_column(String(1000))
    severity: Mapped[str] = mapped_column(String(16))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MedicationEntry(Base):
    __tablename__ = "medication_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    dose: Mapped[str] = mapped_column(String(120))
    schedule: Mapped[str] = mapped_column(String(200))
    prescriber: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MedicalReport(Base):
    __tablename__ = "medical_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    media_type: Mapped[str] = mapped_column(String(80))
    byte_size: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReportShare(Base):
    __tablename__ = "report_shares"
    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id"), primary_key=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("medical_reports.id"), primary_key=True)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CareMessage(Base):
    __tablename__ = "care_messages"
    __table_args__ = (
        UniqueConstraint(
            "appointment_id", "sender_id", "client_message_id", name="uq_message_retry"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id"), index=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    client_message_id: Mapped[str] = mapped_column(String(36))
    body: Mapped[str] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recipient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assessment_id: Mapped[str | None] = mapped_column(ForeignKey("assessments.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(80))
    appointment_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.id"), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FamilyGrant(Base):
    __tablename__ = "family_grants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_email: Mapped[str] = mapped_column(String(254))
    reader_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list] = mapped_column(JSON)
    invite_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    access_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MedicationReminder(Base):
    __tablename__ = "medication_reminders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    medication_id: Mapped[str] = mapped_column(ForeignKey("medication_entries.id"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_hours: Mapped[int] = mapped_column(Integer, default=0)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AssistantTurn(Base):
    __tablename__ = "assistant_turns"
    __table_args__ = (UniqueConstraint("patient_id", "request_id", name="uq_assistant_retry"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    question: Mapped[str] = mapped_column(String(1500))
    answer: Mapped[str] = mapped_column(String(6000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Consultation(Base):
    __tablename__ = "consultations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id"), index=True)
    started_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConsultationSignal(Base):
    __tablename__ = "consultation_signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    consultation_id: Mapped[str] = mapped_column(ForeignKey("consultations.id"), index=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AccessAudit(Base):
    __tablename__ = "access_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    method: Mapped[str] = mapped_column(String(10))
    route: Mapped[str] = mapped_column(String(200))
    status_code: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AssessmentCarePlan(Base):
    __tablename__ = "assessment_care_plans"
    __table_args__ = (
        UniqueConstraint("assessment_id", "context_sha256", name="uq_care_plan_context"),
        CheckConstraint("status IN ('GENERATING', 'READY', 'FAILED')", name="ck_care_plan_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), index=True)
    context_sha256: Mapped[str] = mapped_column(String(64))
    context_snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16))
    content: Mapped[str | None] = mapped_column(String(6000), nullable=True)
    provider_model: Mapped[str] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(2), default="en")
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ClinicalReview(Base):
    __tablename__ = "clinical_reviews"
    __table_args__ = (
        UniqueConstraint("assessment_id", name="uq_clinical_review_assessment"),
        CheckConstraint(
            "status IN ('PENDING', 'REVIEWED', 'URGENT_FOLLOW_UP')",
            name="ck_clinical_review_status",
        ),
        CheckConstraint("version >= 1", name="ck_clinical_review_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id"))
    doctor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(String(1000), default="")
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ClinicalReviewEvent(Base):
    __tablename__ = "clinical_review_events"
    __table_args__ = (UniqueConstraint("review_id", "version", name="uq_review_event_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    review_id: Mapped[str] = mapped_column(ForeignKey("clinical_reviews.id"), index=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id"))
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FollowUpProposal(Base):
    __tablename__ = "follow_up_proposals"
    __table_args__ = (UniqueConstraint("doctor_id", "request_id", name="uq_follow_up_request"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id"))
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(1000))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_appointment_id: Mapped[str | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True
    )
    declined: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WhatsAppAlert(Base):
    __tablename__ = "whatsapp_alerts"
    __table_args__ = (UniqueConstraint("patient_id", "request_id", name="uq_whatsapp_request"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    recipient: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(24))
    provider_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(200), nullable=True)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
