"""Reproducible internal PE audit; never activates or overwrites a model."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline

from ml.data_contract import feature_group
from ml.import_legacy_pe import FEATURES, SOURCE_HASHES, UNUSED_INDICES, read_source_sheet

CLASSES = ["HIGH", "LOW", "MEDIUM"]


def metrics(truth, prediction):
    return {
        "accuracy": float(accuracy_score(truth, prediction)),
        "macro_f1": float(f1_score(truth, prediction, labels=CLASSES, average="macro")),
        "confusion_matrix_actual_rows_predicted_columns": confusion_matrix(
            truth, prediction, labels=CLASSES
        ).tolist(),
        "class_report": classification_report(
            truth, prediction, labels=CLASSES, output_dict=True, zero_division=0
        ),
    }


def validate(source):
    from app.pe_model import forest_scores, get_pe_model

    frames = []
    for name in ("train_dataset.xlsx", "test_dataset.xlsx"):
        relative = "ml/datasets/" + name
        path = source / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_HASHES[relative]:
            raise ValueError("Source workbook checksum mismatch")
        frames.append(read_source_sheet(path, impute_missing=False))
    fields = [field for i, field in enumerate(FEATURES) if i not in UNUSED_INDICES]
    columns = [field[1] for field in fields]
    raw = pd.concat(frames, ignore_index=True)[columns + ["Risk_level"]]
    if np.isinf(raw[columns].to_numpy(dtype=float)).any():
        raise ValueError("Infinite source measurements")
    missing = {f[0]: int(raw[f[1]].isna().sum()) for f in fields}
    data = raw.drop_duplicates().reset_index(drop=True)
    x = data[columns].astype(float)
    y = data.Risk_level.map({"low": "LOW", "mid": "MEDIUM", "high": "HIGH"})
    if y.isna().any():
        raise ValueError("Unknown source label")
    groups = x.apply(feature_group, axis=1)
    label_counts = pd.DataFrame({"group": groups, "label": y}).groupby("group").label.nunique()
    train_groups = set(frames[0][columns].apply(feature_group, axis=1))
    test_groups = frames[1][columns].apply(feature_group, axis=1)
    model = get_pe_model()
    old_prediction = []
    legacy_test = read_source_sheet(source / "ml/datasets/test_dataset.xlsx")
    for _, row in legacy_test.iterrows():
        values = [None if i in UNUSED_INDICES else float(row[f[1]])
                  for i, f in enumerate(FEATURES)]
        old_prediction.append(CLASSES[int(np.argmax(forest_scores(model.artifact, values)))])
    old_y = frames[1].Risk_level.map({"low": "LOW", "mid": "MEDIUM", "high": "HIGH"})
    parameters = dict(n_estimators=400, max_depth=6, min_samples_leaf=2,
                      class_weight="balanced_subsample", random_state=20261016, n_jobs=1)
    folds, seen = [], []
    oof, baseline = np.empty(len(y), dtype=object), np.empty(len(y), dtype=object)
    for index, (fit, test) in enumerate(StratifiedGroupKFold(
        n_splits=5, shuffle=True, random_state=20261016
    ).split(x, y, groups), start=1):
        overlap = set(groups.iloc[fit]) & set(groups.iloc[test])
        if overlap:
            raise ValueError("Feature groups overlap")
        candidate = make_pipeline(
            SimpleImputer(strategy="median"), RandomForestClassifier(**parameters)
        ).fit(x.iloc[fit], y.iloc[fit])
        oof[test] = candidate.predict(x.iloc[test])
        baseline[test] = DummyClassifier(strategy="most_frequent").fit(
            x.iloc[fit], y.iloc[fit]
        ).predict(x.iloc[test])
        seen.extend(test.tolist())
        folds.append({"fold": index, "training_rows": len(fit), "test_rows": len(test),
                      "overlap_feature_groups": len(overlap), **metrics(y.iloc[test], oof[test])})
    if sorted(seen) != list(range(len(y))):
        raise ValueError("Not every row has exactly one out-of-fold prediction")
    return {
        "scope": "Internal legacy-label validation only; not clinical or external validation",
        "source_hashes": {k: v for k, v in SOURCE_HASHES.items() if k.endswith(".xlsx")},
        "sklearn_version": sklearn.__version__, "class_order": CLASSES,
        "missing_used_measurements": missing,
        "preprocessing": "Median imputer fitted inside each training fold only",
        "raw_rows": len(raw), "unique_labelled_rows": len(data),
        "exact_duplicates_removed": len(raw) - len(data),
        "unique_feature_groups": int(groups.nunique()),
        "conflicting_label_feature_groups": int((label_counts > 1).sum()),
        "original_test_rows": len(old_y),
        "original_test_rows_matching_training_features": int(test_groups.isin(train_groups).sum()),
        "deployed_model_original_test": metrics(old_y, old_prediction),
        "candidate_parameters_fixed_before_this_run": parameters,
        "candidate_grouped_folds": folds, "candidate_out_of_fold": metrics(y, oof),
        "most_frequent_baseline_out_of_fold": metrics(y, baseline),
        "observed_ranges": {f[0]: [float(x[f[1]].min()), float(x[f[1]].max())] for f in fields},
        "activation": "NOT_PROMOTED",
        "clinical_validation": "NOT_ESTABLISHED",
        "limitations": [
            "Legacy category labels do not establish confirmed PE outcomes or diagnostic accuracy.",
            "Feature grouping prevents identical-input overlap, not unidentified-patient leakage.",
            "Data previously examined; cross-validation is not a new external test.",
            "Small sample, conflicting labels and undocumented units/provenance remain unresolved.",
            "No systolic BP above 130 in source data; this audit cannot extend model coverage.",
            "No hyperparameter selection or model promotion is performed by this audit.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = validate(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({k: report[k] for k in (
        "raw_rows", "unique_labelled_rows", "unique_feature_groups",
        "conflicting_label_feature_groups", "candidate_out_of_fold", "clinical_validation"
    )}, indent=2))
