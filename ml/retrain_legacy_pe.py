"""Retrain the supplied legacy categories with grouped evaluation, without inventing PE outcomes."""

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedGroupKFold

from ml.data_contract import feature_group
from ml.import_legacy_pe import (
    FEATURES,
    SOURCE_HASHES,
    UNUSED_INDICES,
    read_source_sheet,
)
from ml.train_comparison import export_forest, write_json


def retrain(source, output):
    frames = []
    for name in ["train_dataset.xlsx", "test_dataset.xlsx"]:
        path = Path(source) / "ml/datasets" / name
        if (
            hashlib.sha256(path.read_bytes()).hexdigest()
            != SOURCE_HASHES["ml/datasets/" + name]
        ):
            raise ValueError("Legacy workbook integrity check failed")
        frames.append(read_source_sheet(path))
    fields = [f for i, f in enumerate(FEATURES) if i not in UNUSED_INDICES]
    columns = [f[1] for f in fields]
    data = pd.concat(frames, ignore_index=True)[columns + ["Risk_level"]]
    raw_rows = len(data)
    data = data.drop_duplicates().reset_index(drop=True)
    features = data[columns].astype(float)
    features.columns = [f[0] for f in fields]
    labels = data.Risk_level.map({"low": "LOW", "mid": "MEDIUM", "high": "HIGH"})
    if labels.isna().any() or not np.isfinite(features.to_numpy()).all():
        raise ValueError("Unsupported labels or missing used measurements")
    groups = features.apply(feature_group, axis=1)
    fit, test = next(
        StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261016).split(
            features, labels, groups
        )
    )
    if set(groups.iloc[fit]) & set(groups.iloc[test]):
        raise ValueError("PE comparison groups overlap")
    parameters = dict(
        n_estimators=400,
        max_depth=6,
        min_samples_leaf=2,
        class_weight="balanced_subsample",
        random_state=20261016,
        n_jobs=1,
    )
    model = RandomForestClassifier(**parameters).fit(
        features.iloc[fit], labels.iloc[fit]
    )
    predictions = model.predict(features.iloc[test])
    report = {
        "source": (
            "Pinned original BloomCare workbooks; "
            "legacy category labels retained, not confirmed PE outcomes"
        ),
        "raw_rows": raw_rows,
        "exact_duplicates_removed": raw_rows - len(data),
        "usable_rows": len(data),
        "train_rows": len(fit),
        "test_rows": len(test),
        "overlap_feature_groups": 0,
        "parameters": parameters,
        "test_accuracy": float(accuracy_score(labels.iloc[test], predictions)),
        "test_macro_f1": float(
            f1_score(labels.iloc[test], predictions, average="macro")
        ),
        "test_class_report": classification_report(
            labels.iloc[test], predictions, output_dict=True, zero_division=0
        ),
        "observed_ranges": {
            n: [float(features[n].min()), float(features[n].max())] for n in features
        },
        "activation": "NOT_PROMOTED_DATA_PROVENANCE_AND_INDEPENDENT_OUTCOMES_REQUIRED",
        "limitations": [
            "Only 90 unique rows remain; "
            "this is a small internal grouped comparison, not external validation.",
            "No source support for systolic BP above 130 mmHg; training cannot extend coverage.",
            "Original HB units and confirmed PE outcome definition remain undocumented.",
            "The original overlapping train/test score is not comparable to this grouped test.",
            "Unused all-missing Doppler features are omitted; no observations are synthesized.",
        ],
    }
    output = Path(output)
    if (output / "pe-retraining-report.json").exists():
        raise ValueError("Choose a fresh output directory; prior evidence is preserved")
    report["candidate_artifact_sha256"] = export_forest(
        model,
        output / "pe-candidate.json",
        features.columns,
        {
            "active": False,
            "source": "Legacy labels, not clinically verified PE outcomes",
        },
    )
    write_json(output / "pe-retraining-report.json", report)
    print(
        "Legacy PE retraining completed with grouped evaluation. Candidate not activated."
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    destination = args.output or Path(__file__).parent / "training_reports/runs" / (
        "pe-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    )
    retrain(args.source, destination)
