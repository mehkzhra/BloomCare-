"""Validated inputs for assessment completion and clinical follow-up."""

from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictBool, field_validator, model_validator

from app.schemas import AppointmentInput, HealthInput, Input


class ClinicalIndicators(Input):
    gravida: int | None = Field(default=None, ge=1, le=30, strict=True)
    parity: int | None = Field(default=None, ge=0, le=25, strict=True)
    bmi: float | None = Field(default=None, ge=5, le=100, allow_inf_nan=False)
    diabetes: StrictBool | None = None
    history_of_hypertension: StrictBool | None = None
    hb: float | None = Field(default=None, ge=0, le=30, allow_inf_nan=False)
    fetal_weight_kg: float | None = Field(default=None, gt=0, le=15, allow_inf_nan=False)
    protein_uria: StrictBool | None = None
    amniotic_fluid_level_cm: float | None = Field(default=None, ge=0, le=60, allow_inf_nan=False)

    @model_validator(mode="after")
    def birth_order(self):
        if self.gravida is not None and self.parity is not None and self.parity >= self.gravida:
            raise ValueError("Previous births must be fewer than total pregnancies")
        return self


class HealthRecordInput(HealthInput):
    clinical_indicators: ClinicalIndicators | None = None
    request_id: UUID | None = None


class CarePlanInput(Input):
    consent: Literal[True]
    language: Literal["en", "ur"] = "en"
    retry_personalization: bool = Field(default=False, strict=True)


class ClinicalReviewInput(Input):
    status: Literal["PENDING", "REVIEWED", "URGENT_FOLLOW_UP"]
    reason: str = Field(default="", max_length=1000)
    follow_up_at: datetime | None = None
    expected_version: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_follow_up(self):
        if self.status == "URGENT_FOLLOW_UP" and len(self.reason) < 3:
            raise ValueError("Enter a reason for urgent follow-up")
        if self.follow_up_at:
            now = datetime.now(timezone.utc)
            if self.follow_up_at.tzinfo is None:
                raise ValueError("Follow-up time must include its timezone")
            self.follow_up_at = self.follow_up_at.astimezone(timezone.utc)
            if not now < self.follow_up_at <= now + timedelta(days=90):
                raise ValueError("Choose a future follow-up within 90 days")
        return self


class FollowUpInput(Input):
    assessment_id: UUID
    request_id: UUID
    scheduled_at: datetime
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("scheduled_at")
    @classmethod
    def valid_slot(cls, value):
        if value.tzinfo is None:
            raise ValueError("Appointment time must include its timezone")
        value = value.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        if not now < value <= now + timedelta(days=90):
            raise ValueError("Choose a future appointment within 90 days")
        if value.minute not in {0, 30} or value.second or value.microsecond:
            raise ValueError("Choose a half-hour appointment slot")
        return value


class ProposalAcceptance(Input):
    share_profile: Literal[True]
    health_record_ids: list[UUID] = Field(default_factory=list, max_length=20)


class RescheduleInput(Input):
    scheduled_at: datetime
    reason: str = Field(min_length=3, max_length=1000)
    share_profile: Literal[True]
    expected_updated_at: datetime

    _slot = field_validator("scheduled_at")(FollowUpInput.valid_slot.__func__)


class AlertInput(Input):
    request_id: UUID
    consent: Literal[True]
    recipient: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")


def proposal_booking(proposal, data):
    return AppointmentInput(
        doctor_id=proposal.doctor_id,
        scheduled_at=(
            proposal.scheduled_at.replace(tzinfo=timezone.utc)
            if proposal.scheduled_at.tzinfo is None
            else proposal.scheduled_at.astimezone(timezone.utc)
        ),
        reason=proposal.reason,
        share_profile=data.share_profile,
        health_record_ids=data.health_record_ids,
    )
