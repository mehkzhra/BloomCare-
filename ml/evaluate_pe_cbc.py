"""Score a frozen CBC candidate on a documented cohort; never enable clinical use.

CSV: patient_id,Status,WBC,RBC,Neutrophils,Lymphocytes,Monocytes,Platelets.
Status must be Controls or Patients. Numeric values must use the training assay
units, independently verified by the data custodian before this command is run.
No individual identifiers or predictions are written into the aggregate report.
"""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

FEATURES = ["WBC", "RBC", "Neutrophils", "Lymphocytes", "Monocytes", "Platelets"]


def interval(successes, total):
    """Wilson binomial 95% interval, useful with small PE cohorts."""
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total**2)) / denominator
    return [center - half, center + half]


def evaluate(candidate_path, cohort_path, metadata_path):
    candidate = json.loads(candidate_path.read_text())
    metadata = json.loads(metadata_path.read_text())
    required = (
        "cohort_name",
        "data_custodian",
        "unit_mapping_evidence",
        "measurement_timing",
        "diagnostic_criteria",
        "patient_separation_evidence",
    )
    if any(
        not isinstance(metadata.get(k), str) or not metadata[k].strip()
        for k in required
    ):
        raise ValueError("Document all cohort metadata fields before evaluation")
    if metadata.get("units_match_training") is not True:
        raise ValueError(
            "Training-unit compatibility must first be confirmed by the custodian"
        )
    if candidate.get("features") != FEATURES or candidate.get("classes") != [0, 1]:
        raise ValueError("Candidate feature/class mapping mismatch")
    if candidate.get("schema") != "offline-cbc-logistic-candidate-v1":
        raise ValueError("Unsupported candidate format")
    for key in ("median", "mean", "scale", "coefficients"):
        values = candidate.get(key)
        if not isinstance(values, list) or len(values) != len(FEATURES):
            raise ValueError("Invalid candidate vector")
        if any(
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            for v in values
        ):
            raise ValueError("Non-finite candidate parameters")
    if any(v <= 0 for v in candidate["scale"]) or not math.isfinite(
        candidate["intercept"]
    ):
        raise ValueError("Invalid candidate scaling/intercept")
    with cohort_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["patient_id", "Status", *FEATURES]:
            raise ValueError("Unexpected CSV columns or ordering")
        rows = list(reader)
    counts = [[0, 0], [0, 0]]
    seen = set()
    missing = 0
    for row in rows:
        patient = row["patient_id"].strip()
        if not patient or patient in seen:
            raise ValueError(
                "Blank or repeated patient identifier; use one row per patient"
            )
        seen.add(patient)
        if row["Status"] not in ("Controls", "Patients"):
            raise ValueError("Unknown outcome label")
        observed = 0
        logit = candidate["intercept"]
        for i, name in enumerate(FEATURES):
            raw = row[name].strip()
            value = float(raw) if raw else candidate["median"][i]
            if not math.isfinite(value) or value < 0:
                raise ValueError("Invalid CBC value")
            observed += bool(raw)
            missing += not bool(raw)
            logit += (
                (value - candidate["mean"][i])
                / candidate["scale"][i]
                * candidate["coefficients"][i]
            )
        if not observed:
            raise ValueError("All CBC values are missing")
        # Fixed original threshold 0.5; do not tune it on this evaluation cohort.
        counts[int(row["Status"] == "Patients")][int(logit >= 0)] += 1
    (tn, fp), (fn, tp) = counts
    if not tp + fn or not tn + fp:
        raise ValueError("Both outcome classes are required")
    return {
        "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        "cohort_sha256": hashlib.sha256(cohort_path.read_bytes()).hexdigest(),
        "metadata_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        "rows": len(rows),
        "missing_values_imputed": missing,
        "fixed_threshold": 0.5,
        "confusion_matrix_actual_rows": counts,
        "missed_pe_cases": fn,
        "sensitivity": tp / (tp + fn),
        "sensitivity_95_percent_ci": interval(tp, tp + fn),
        "specificity": tn / (tn + fp),
        "specificity_95_percent_ci": interval(tn, tn + fp),
        "clinical_use": False,
        "automatically_promoted": False,
        "limitations": [
            "Metadata and independence declarations require external human verification.",
            "Training patient identifiers are unavailable: cross-cohort identity overlap cannot be checked.",
            "This report does not establish clinical approval or prospective utility.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("candidate", "cohort", "metadata", "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.candidate, args.cohort, args.metadata)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
