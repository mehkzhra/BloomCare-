from copy import deepcopy
from datetime import timezone
from typing import Literal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.maternal_model import (
    ModelUnavailable,
    UnsupportedMeasurements,
    get_maternal_model,
    model_summary,
)
from app.models import Assessment, HealthRecord, ModelVersion
from app.pe_contract import BASE_FIELDS, input_contract
from app.pe_model import PEModelUnavailable, get_pe_model
from app.schemas import HealthInput, PEAdditionalInput

Risk = Literal["LOW", "MEDIUM", "HIGH"]


def timestamp(value):
    if value is None:
        return None
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def require_active_assessment(row):
    if row.removed_at is not None:
        raise HTTPException(
            410,
            "This assessment was removed because it was entered in error. "
            "Add a corrected health record for a new assessment.",
        )
    return row


def require_active_record(row):
    if row.removed_at is not None:
        raise HTTPException(
            410,
            "This health record was deleted from active care. "
            "Add a corrected health record to continue.",
        )
    return row


def pe_screening_required(risk: Risk, observations=None, clinical=None) -> bool:
    if risk not in {"LOW", "MEDIUM", "HIGH"}:
        raise ValueError("Unexpected pregnancy risk label")
    observations, clinical = observations or {}, clinical or {}
    return risk in {"MEDIUM", "HIGH"} or bool(
        observations.get("systolic_mmhg", 0) >= 140
        or observations.get("diastolic_mmhg", 0) >= 90
        or clinical.get("history_of_hypertension") is True
        or clinical.get("protein_uria") is True
    )


def pe_input_issues(row):
    values = {**row.observations_snapshot, **(row.clinical_snapshot or {})}
    return [
        {**field, "value": values[field["name"]]}
        for field in input_contract()
        if values.get(field["name"]) is not None
        and (
            values[field["name"]] < field["minimum"] - 1e-8
            or values[field["name"]] > field["maximum"] + 1e-8
        )
    ]


def pe_state(row):
    if row.pe_screening:
        return "COMPLETED", "PE screening is saved. Review the result with your clinician."
    if not pe_screening_required(
        row.maternal_risk, row.observations_snapshot, row.clinical_snapshot
    ):
        return "NOT_INDICATED", (
            "No PE trigger was recorded by this workflow. LOW does not rule out pre-eclampsia."
        )
    try:
        get_pe_model()
    except PEModelUnavailable:
        return "UNAVAILABLE", "The PE model is currently unavailable. Arrange a doctor review."
    outside = pe_input_issues(row)
    if outside:
        if any(field["name"] == "gestational_weeks" for field in outside):
            return "OUTSIDE_COVERAGE", (
                "Recorded pregnancy duration is outside the PE model's 14–40-week coverage. "
                "The maternal result does not use pregnancy duration. No PE category was "
                "generated; keep the actual duration and arrange a doctor review."
            )
        return "OUTSIDE_COVERAGE", (
            "Actual measurements exceed the PE model's supported range. "
            "No PE category was generated; arrange a doctor review."
        )
    return "AWAITING_INPUTS", "Complete the additional measured values for PE screening."


def care_plan_context(row, language="en"):
    import hashlib
    import json

    status, _ = pe_state(row)
    pe = row.pe_screening
    context = {
        "observations": row.observations_snapshot,
        "clinical_indicators": row.clinical_snapshot or {},
        "maternal_category": row.maternal_risk,
        "maternal_scores": row.class_scores,
        "pe_status": status,
        "pe_category": pe.risk if pe else None,
        "pe_observations": pe.observations_snapshot if pe else None,
        "language": language,
    }
    digest = hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
    return context, digest


def review_out(review):
    if not review:
        return None
    return {
        "id": review.id,
        "status": review.status,
        "reason": review.reason,
        "follow_up_at": timestamp(review.follow_up_at),
        "version": review.version,
        "doctor_id": review.doctor_id,
        "updated_at": timestamp(review.updated_at),
    }


def complete_saved_pe(db, row, record):
    clinical = record.clinical_indicators or {}
    fields = {f["name"] for f in input_contract()} - BASE_FIELDS
    if (
        row.pe_screening
        or not pe_screening_required(
            row.maternal_risk, row.observations_snapshot, row.clinical_snapshot
        )
        or not fields.issubset(clinical)
    ):
        return serialize_assessment(row)
    if pe_state(row)[0] == "OUTSIDE_COVERAGE":
        return serialize_assessment(row)
    from app.pe_service import run_pe_stage

    try:
        return run_pe_stage(db, row.patient_id, row.id, PEAdditionalInput(**clinical))
    except HTTPException as error:
        if error.status_code not in {422, 503}:
            raise
        return serialize_assessment(row)


def serialize_assessment(row: Assessment):
    # Maternal results stay immutable. PE is an additional, separately saved stage.
    pe = row.pe_screening
    status, reason = pe_state(row)
    ready_plans = [plan for plan in row.care_plans if plan.status == "READY"]
    plan = max(ready_plans, key=lambda p: p.created_at.replace(tzinfo=timezone.utc), default=None)
    return {
        "id": row.id,
        "health_record_id": row.health_record_id,
        "observations": row.observations_snapshot,
        "maternal_risk": row.maternal_risk,
        "class_scores": row.class_scores,
        "explanation": row.explanation,
        "pe_required": pe_screening_required(
            row.maternal_risk, row.observations_snapshot, row.clinical_snapshot
        ),
        "pe_status": status,
        "pe_reason": reason,
        "pe_input_issues": pe_input_issues(row) if not pe else [],
        "clinical_indicators": row.clinical_snapshot,
        "clinical_review": review_out(row.clinical_review),
        "care_plan": {
            "id": plan.id,
            "content": plan.content,
            "language": plan.language,
            "provider_model": plan.provider_model,
            "created_at": timestamp(plan.created_at),
            "current": plan.context_sha256 == care_plan_context(row, plan.language)[1],
        }
        if plan
        else None,
        "pe_screening": {
            "id": pe.id,
            "observations": pe.observations_snapshot,
            "risk": pe.risk,
            "class_scores": pe.class_scores,
            "model": pe.model_snapshot,
            "explanation": pe.explanation,
            "created_at": timestamp(pe.created_at),
        }
        if pe
        else None,
        "research_only": row.research_only,
        "created_at": timestamp(row.created_at),
        "model": model_summary(row.model_version.manifest),
    }


def own_record(db: Session, patient_id: str, record_id: str, *, lock=False):
    query = select(HealthRecord).where(
        HealthRecord.id == record_id,
        HealthRecord.patient_id == patient_id,
    )
    if lock:
        query = query.with_for_update(of=HealthRecord)
    record = db.scalar(query)
    if not record:
        raise HTTPException(404, "Health record not found")
    return require_active_record(record)


def assess_patient(db: Session, patient_id: str, record_id: str):
    record = own_record(db, patient_id, record_id, lock=True)
    try:
        observations = HealthInput.model_validate(record.observations).model_dump()
    except ValidationError:
        raise HTTPException(
            409,
            "This saved record does not match the current observation format",
        ) from None
    try:
        model = get_maternal_model()
    except ModelUnavailable as error:
        raise HTTPException(503, str(error)) from None
    existing_query = select(Assessment).where(
        Assessment.health_record_id == record_id,
        Assessment.patient_id == patient_id,
        Assessment.model_version_id == model.id,
    )
    existing = db.scalar(existing_query)
    if existing:
        require_active_assessment(existing)
        return complete_saved_pe(db, existing, record)
    try:
        result = model.infer(observations)
    except UnsupportedMeasurements as error:
        raise HTTPException(
            422,
            {
                "code": "MODEL_INPUT_OUTSIDE_RANGE",
                "message": (
                    "No assessment was created: measurements are outside this model's training "
                    "range. Your health record is still saved."
                ),
                "fields": error.fields,
            },
        ) from None
    except Exception:
        raise HTTPException(
            503,
            "The experimental assessment could not be verified. No result was saved.",
        ) from None
    required = pe_screening_required(
        result["maternal_risk"], observations, record.clinical_indicators
    )
    reason = (
        "BloomCare's software rule requires the PE stage, but no verified PE model is available. "
        "This assessment is incomplete."
        if required
        else "The PE stage is not indicated by BloomCare's software rule for LOW. "
        "This does not rule out pre-eclampsia."
    )
    # A stable model identity and database uniqueness also handle concurrent retries.
    for attempt in range(2):
        try:
            version = db.get(ModelVersion, model.id)
            if not version:
                version = ModelVersion(
                    id=model.id,
                    version=model.manifest["version"],
                    artifact_sha256=model.artifact_sha256,
                    manifest=deepcopy(model.manifest),
                )
                db.add(version)
                db.flush()
            row = Assessment(
                patient_id=patient_id,
                health_record_id=record_id,
                model_version=version,
                observations_snapshot=deepcopy(observations),
                clinical_snapshot=deepcopy(record.clinical_indicators),
                **result,
                pe_required=required,
                pe_status="UNAVAILABLE" if required else "NOT_INDICATED",
                pe_reason=reason,
                research_only=True,
            )
            db.add(row)
            db.commit()
            return complete_saved_pe(db, row, record)
        except IntegrityError:
            db.rollback()
            existing = db.scalar(existing_query)
            if existing:
                require_active_assessment(existing)
                return serialize_assessment(existing)
            if attempt == 1:
                raise HTTPException(
                    409, "The assessment could not be saved. Please retry."
                ) from None
