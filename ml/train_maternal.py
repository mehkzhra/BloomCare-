"""Train one fixed Random Forest and evaluate on measurement groups never used for fitting."""

import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.pipeline import Pipeline

from ml.data_contract import CLASS_ORDER, FEATURES, UNITS, load_data, split_data
from ml.fetch_data import EXPECTED_CSV_SHA256, ROOT, fetch_data


def evaluate(model, features, labels):
    predictions = model.predict(features)
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "macro_f1": float(f1_score(labels, predictions, labels=CLASS_ORDER, average="macro")),
        "class_report": classification_report(
            labels, predictions, labels=CLASS_ORDER, output_dict=True, zero_division=0
        ),
        "confusion_matrix_class_order": CLASS_ORDER,
        "confusion_matrix_rows_actual_columns_predicted": confusion_matrix(
            labels, predictions, labels=CLASS_ORDER
        ).tolist(),
    }


def train(*, data_path=None, output_path=None):
    source = Path(data_path) if data_path is not None else fetch_data()
    if hashlib.sha256(source.read_bytes()).hexdigest() != EXPECTED_CSV_SHA256:
        raise ValueError("Source checksum differs from the reviewed UCI download")
    features, labels, groups, audit = load_data(source)
    train_rows, held_out_rows = split_data(features, labels, groups)
    training_features, training_labels = (
        features.iloc[train_rows],
        labels.iloc[train_rows],
    )
    held_out_features, held_out_labels = (
        features.iloc[held_out_rows],
        labels.iloc[held_out_rows],
    )
    parameters = {
        "n_estimators": 400,
        "max_depth": 12,
        "min_samples_leaf": 2,
        "max_features": "sqrt",
        "class_weight": "balanced_subsample",
        "random_state": 20261010,
        "n_jobs": 1,
    }
    pipeline = Pipeline(
        [
            ("preprocess", SimpleImputer(strategy="median")),
            ("model", RandomForestClassifier(**parameters)),
        ]
    )
    pipeline.fit(training_features, training_labels)
    baseline = DummyClassifier(strategy="most_frequent").fit(training_features, training_labels)
    evaluation = {
        "audit": audit,
        "split": {
            "method": "First fold of StratifiedGroupKFold(5, shuffle=True, random_state=20261010)",
            "group": "Exact six-feature measurement vector, regardless of its label",
            "train_rows": len(train_rows),
            "held_out_rows": len(held_out_rows),
            "train_groups": int(groups.iloc[train_rows].nunique()),
            "held_out_groups": int(groups.iloc[held_out_rows].nunique()),
            "identical_feature_group_overlap": 0,
            "train_class_counts": training_labels.value_counts().to_dict(),
            "held_out_class_counts": held_out_labels.value_counts().to_dict(),
            "hyperparameter_tuning": False,
            "held_out_data_used_for_fitting": False,
        },
        "random_forest": evaluate(pipeline, held_out_features, held_out_labels),
        "most_frequent_baseline": evaluate(baseline, held_out_features, held_out_labels),
        "limitations": [
            "No patient identifiers: repeated-subject leakage cannot be ruled out.",
            "Labels are the dataset's risk categories, not prospectively observed complications.",
            "Conflicting risk labels occur for some identical measurements and are retained.",
            "Blood glucose below 6 mmol/L has no support in this dataset.",
            "No independent external validation or clinical validation was performed.",
            "The model was fitted only on the training partition, not refitted on held-out data.",
            "No pre-eclampsia outcome label is present; no PE model was trained.",
        ],
    }
    output = (
        Path(output_path) if output_path is not None else ROOT / "artifacts" / "maternal_rf_v0.2"
    )
    if output.exists():
        raise ValueError("Output already exists. Keep the checkpoint or move it before retraining")
    output.mkdir(parents=True)
    artifact = output / "pipeline.joblib"
    joblib.dump(pipeline, artifact, compress=3)
    versions = {
        name: importlib.metadata.version(name)
        for name in ["scikit-learn", "pandas", "numpy", "joblib", "scipy"]
    }
    manifest = {
        "model_kind": "maternal_risk",
        "version": "maternal_rf_v0.2",
        "algorithm": "RandomForestClassifier",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "dependencies": versions,
        "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "features": [
            {"name": name, "unit": unit, "dtype": "numeric"}
            for name, unit in zip(FEATURES, UNITS, strict=True)
        ],
        "class_order_in_artifact": pipeline.named_steps["model"].classes_.tolist(),
        "parameters": parameters,
        "dataset_sha256": audit["source_sha256"],
        "observed_training_ranges": {
            name: [
                float(training_features[name].min()),
                float(training_features[name].max()),
            ]
            for name in FEATURES
        },
        "evaluation": evaluation,
        "application_activation": "DISABLED_PENDING_INTEGRATION_AND_REVIEW",
        "class_probabilities": (
            "Uncalibrated class probabilities; not probabilities of complications"
        ),
        "explanation": "Global impurity feature importance; not a patient-specific explanation",
        "global_feature_importance": dict(
            zip(
                FEATURES,
                pipeline.named_steps["model"].feature_importances_.tolist(),
                strict=True,
            )
        ),
        "gestational_weeks": "Recorded by the application but absent from this model's features",
        "pe_model": "UNAVAILABLE_SEPARATE_VERIFIED_OUTCOME_DATA_REQUIRED",
        "old_project_artifacts_used": False,
    }
    for filename, data in [
        ("evaluation.json", evaluation),
        ("manifest.json", manifest),
    ]:
        (output / filename).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    assignments = [
        {"group_sha256": groups.iloc[index], "partition": partition}
        for partition, rows in [("train", train_rows), ("held_out", held_out_rows)]
        for index in rows
    ]
    (output / "split.json").write_text(json.dumps(assignments, indent=2) + "\n", encoding="utf-8")
    score = evaluation["random_forest"]
    print(
        f"Fresh model trained. Held-out accuracy: {score['accuracy']:.4f}; "
        f"macro-F1: {score['macro_f1']:.4f}"
    )
    print(f"Output: {output}")
    print("Training does not activate this research artifact. PE model has not been trained.")
    return output


if __name__ == "__main__":
    train()
