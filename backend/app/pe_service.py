"""Patient-owned, immutable PE stage attached to an existing maternal assessment."""

from copy import deepcopy

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.assessment_service import (
    pe_screening_required,
    require_active_assessment,
    serialize_assessment,
)
from app.models import Assessment, PEScreening
from app.pe_contract import BASE_FIELDS
from app.pe_model import (
    PEModelUnavailable,
    PEUnsupportedMeasurements,
    get_pe_model,
    pe_summary,
)


def run_pe_stage(db, patient_id, assessment_id, data):
    row = db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.patient_id == patient_id,
        )
    )
    if not row:
        raise HTTPException(404, "Assessment not found")
    require_active_assessment(row)
    if not pe_screening_required(
        row.maternal_risk, row.observations_snapshot, row.clinical_snapshot
    ):
        raise HTTPException(400, "No PE trigger was recorded for this assessment")
    if row.pe_screening:
        if data is not None and any(
            row.pe_screening.observations_snapshot[name] != value
            for name, value in data.model_dump().items()
        ):
            raise HTTPException(
                409,
                "This PE screening is already saved. "
                "Create a new health record for changed measurements.",
            )
        return serialize_assessment(row)
    try:
        model = get_pe_model()
    except PEModelUnavailable:
        raise HTTPException(
            503,
            {
                "code": "PE_MODEL_UNAVAILABLE",
                "message": "The PE screening model is currently unavailable.",
            },
        ) from None
    if data is None:
        raise HTTPException(
            422,
            {
                "code": "PE_INPUT_REQUIRED",
                "message": "Complete the additional PE measurements first.",
            },
        )
    observations = {name: row.observations_snapshot[name] for name in BASE_FIELDS}
    observations.update(data.model_dump())
    try:
        result = model.infer(observations)
    except PEUnsupportedMeasurements as error:
        raise HTTPException(
            422,
            {
                "code": "PE_INPUT_OUTSIDE_RANGE",
                "message": "No PE screening was saved: actual measurements are outside this "
                "model's supported range. Keep your actual readings and arrange a "
                "doctor review.",
                "fields": error.fields,
            },
        ) from None
    except Exception:
        raise HTTPException(
            503,
            {
                "code": "PE_MODEL_UNAVAILABLE",
                "message": "PE screening could not be verified. No PE result was saved.",
            },
        ) from None
    screening = PEScreening(
        assessment_id=row.id,
        observations_snapshot=deepcopy(observations),
        model_snapshot=pe_summary(deepcopy(model.manifest)),
        **result,
    )
    db.add(screening)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Unique assessment_id resolves a retried/concurrent submit without overwriting history.
        db.refresh(row)
        if not row.pe_screening:
            raise HTTPException(409, "PE screening could not be saved. Please retry.") from None
        if row.pe_screening.observations_snapshot != observations:
            raise HTTPException(
                409,
                "A PE screening with different measurements was saved. Refresh this assessment.",
            ) from None
    db.refresh(row)
    return serialize_assessment(row)
