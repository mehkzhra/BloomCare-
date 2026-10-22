from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(Input):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password", mode="before")
    @classmethod
    def no_edge_whitespace(cls, value):
        if isinstance(value, str) and value != value.strip():
            raise ValueError("Passwords must not start or end with whitespace")
        return value


class Register(Credentials):
    full_name: str = Field(min_length=2, max_length=120)


class DoctorRegister(Register):
    registration_number: str = Field(min_length=2, max_length=80)
    specialty: str = Field(min_length=2, max_length=120)


class Login(Credentials):
    role: Literal["patient", "doctor", "admin"] | None = None


class AccountStatus(Input):
    active: bool = Field(strict=True)


class DoctorApproval(Input):
    approved: bool = Field(strict=True)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str
    role: Literal["patient", "doctor", "admin"]
    email_verified_at: datetime | None = None
    email_verification_required: bool = False


class ProfileUpdate(Input):
    date_of_birth: date | None = None
    due_date: date | None = None
    phone: str | None = Field(default=None, max_length=32, pattern=r"^[+0-9()\s-]{5,32}$")
    preferred_language: Literal["en", "ur"] = "en"

    @field_validator("date_of_birth")
    @classmethod
    def birth_in_past(cls, value):
        if value and value >= datetime.now(timezone.utc).date():
            raise ValueError("Date of birth must be in the past")
        return value


class ProfileOut(ProfileUpdate):
    model_config = ConfigDict(from_attributes=True)
    user_id: str


class HealthInput(Input):
    age_years: int = Field(ge=10, le=65)
    gestational_weeks: float = Field(ge=0, le=45, allow_inf_nan=False)
    systolic_mmhg: int = Field(ge=60, le=260)
    diastolic_mmhg: int = Field(ge=30, le=180)
    glucose_mmol_l: float = Field(ge=1, le=40, allow_inf_nan=False)
    temperature_c: float = Field(ge=32, le=43, allow_inf_nan=False)
    heart_rate_bpm: int = Field(ge=30, le=220)

    @model_validator(mode="after")
    def blood_pressure_order(self):
        if self.diastolic_mmhg >= self.systolic_mmhg:
            raise ValueError("Systolic pressure must be greater than diastolic pressure")
        return self


class HealthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    observations: dict
    clinical_indicators: dict | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def utc_timestamp(cls, value):
        return (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )


class AssessmentInput(Input):
    health_record_id: UUID


class PEAdditionalInput(Input):
    gravida: int = Field(ge=1, le=30, strict=True)
    parity: int = Field(ge=0, le=25, strict=True)
    bmi: float = Field(ge=5, le=100, allow_inf_nan=False)
    diabetes: StrictBool
    history_of_hypertension: StrictBool
    hb: float = Field(ge=0, le=30, allow_inf_nan=False)
    fetal_weight_kg: float = Field(gt=0, le=15, allow_inf_nan=False)
    protein_uria: StrictBool
    amniotic_fluid_level_cm: float = Field(ge=0, le=60, allow_inf_nan=False)

    @model_validator(mode="after")
    def previous_births(self):
        if self.parity >= self.gravida:
            raise ValueError("Previous births must be fewer than total pregnancies")
        return self


class PEScreeningOut(BaseModel):
    id: str
    observations: dict
    risk: Literal["LOW", "MEDIUM", "HIGH"]
    class_scores: dict[str, float]
    model: dict
    explanation: dict | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def utc_timestamp(cls, value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class AssessmentOut(BaseModel):
    id: str
    health_record_id: str
    observations: HealthInput
    maternal_risk: Literal["LOW", "MEDIUM", "HIGH"]
    class_scores: dict[str, float]
    explanation: dict
    pe_required: bool
    pe_status: Literal[
        "NOT_INDICATED", "UNAVAILABLE", "AWAITING_INPUTS", "COMPLETED", "OUTSIDE_COVERAGE"
    ]
    pe_reason: str
    pe_input_issues: list[dict] = Field(default_factory=list)
    pe_screening: PEScreeningOut | None = None
    clinical_indicators: dict | None = None
    care_plan: dict | None = None
    clinical_review: dict | None = None
    research_only: Literal[True]
    model: dict
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def utc_timestamp(cls, value):
        return (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )


class AppointmentInput(Input):
    doctor_id: UUID
    scheduled_at: AwareDatetime
    reason: str = Field(min_length=3, max_length=1000)
    share_profile: StrictBool
    health_record_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @field_validator("scheduled_at")
    @classmethod
    def half_hour_slot(cls, value):
        value = value.astimezone(timezone.utc)
        if value.minute not in {0, 30} or value.second or value.microsecond:
            raise ValueError("Choose a start time on a UTC half-hour boundary")
        return value

    @field_validator("share_profile")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Profile sharing consent is required to request an appointment")
        return value

    @field_validator("health_record_ids")
    @classmethod
    def unique_records(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Select each health record only once")
        return value


class AppointmentDecision(Input):
    action: Literal["ACCEPT", "REJECT", "CANCEL", "COMPLETE"]


class AppointmentOut(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor_name: str
    scheduled_at: datetime
    duration_minutes: Literal[30] = 30
    reason: str
    status: Literal["PENDING", "ACCEPTED", "REJECTED", "CANCELLED", "COMPLETED"]
    health_record_ids: list[str]
    consent_at: datetime
    accepted_at: datetime | None
    access_until: datetime | None
    closed_at: datetime | None
    created_at: datetime
    record_access_available: bool
    updated_at: datetime | None = None


class NoteInput(Input):
    body: str = Field(min_length=1, max_length=4000)
    patient_visible: StrictBool = True
    assessment_id: UUID | None = None


class NoteOut(BaseModel):
    assessment_removed: bool = False
    id: str
    appointment_id: str
    assessment_id: str | None = None
    supersedes_id: str | None = None
    author_name: str
    body: str
    patient_visible: bool
    created_at: datetime


class ReviewOut(BaseModel):
    appointment: AppointmentOut
    profile: ProfileOut
    records: list[HealthOut]
    assessments: list[AssessmentOut] = Field(default_factory=list)
