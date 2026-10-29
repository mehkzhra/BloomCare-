import json
from pathlib import Path

import pytest

from ml.evaluate_pe_cbc import FEATURES, evaluate, interval

CANDIDATE = (
    Path(__file__).parents[1] / "training_reports/pe-cbc-2026-10-29/candidate.json"
)


def inputs(tmp_path):
    # Synthetic fixtures test mechanics only; they are never validation evidence.
    model = json.loads(CANDIDATE.read_text())
    model.update(
        median=[0] * 6,
        mean=[0] * 6,
        scale=[1] * 6,
        coefficients=[1, 0, 0, 0, 0, 0],
        intercept=-5,
    )
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(model))
    cohort = tmp_path / "cohort.csv"
    cohort.write_text(
        "patient_id,Status," + ",".join(FEATURES) + "\n"
        "a,Controls,1,1,1,1,1,1\n"
        "b,Patients,8,1,1,1,1,1\n"
        "c,Patients,2,1,1,1,1,1\n"
    )
    metadata = tmp_path / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                k: "Synthetic unit-test fixture"
                for k in (
                    "cohort_name",
                    "data_custodian",
                    "unit_mapping_evidence",
                    "measurement_timing",
                    "diagnostic_criteria",
                    "patient_separation_evidence",
                )
            }
            | {"units_match_training": True}
        )
    )
    return candidate, cohort, metadata


def test_fixed_threshold_and_missed_cases(tmp_path):
    report = evaluate(*inputs(tmp_path))
    assert report["confusion_matrix_actual_rows"] == [[1, 0], [1, 1]]
    assert report["sensitivity"] == 0.5 and report["missed_pe_cases"] == 1
    assert report["clinical_use"] is False and report["automatically_promoted"] is False
    assert "patient_id" not in json.dumps(report)
    assert interval(34, 39) == pytest.approx([0.7329425662, 0.9439718246])


@pytest.mark.parametrize("invalid", ["nan", "-1", "inf"])
def test_invalid_numeric_values_rejected(tmp_path, invalid):
    candidate, cohort, metadata = inputs(tmp_path)
    cohort.write_text(
        cohort.read_text().replace("a,Controls,1,", f"a,Controls,{invalid},")
    )
    with pytest.raises(ValueError, match="Invalid CBC"):
        evaluate(candidate, cohort, metadata)


def test_missing_units_and_repeat_patients_rejected(tmp_path):
    candidate, cohort, metadata = inputs(tmp_path)
    cohort.write_text(cohort.read_text().replace("b,Patients", "a,Patients"))
    with pytest.raises(ValueError, match="repeated"):
        evaluate(candidate, cohort, metadata)
    metadata.write_text("{}")
    with pytest.raises(ValueError, match="metadata"):
        evaluate(candidate, cohort, metadata)
