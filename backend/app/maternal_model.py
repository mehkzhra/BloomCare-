"""Load only a locally registered research artifact and explain its actual output."""

import hashlib
import importlib.metadata
import io
import json
import logging
import math
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.config import get_settings

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "ml" / "artifacts" / "maternal_rf_v0.2"
TRUST_PATH = ROOT / "backend" / "model-trust.json"
SOURCE_SHA256 = "a1f7025719f84715096e0d1f95ae2e56b57809b9b15449e1836c96a7d976ae9b"
FEATURES = [
    "age_years",
    "systolic_mmhg",
    "diastolic_mmhg",
    "glucose_mmol_l",
    "temperature_c",
    "heart_rate_bpm",
]
UNITS = ["years", "mmHg", "mmHg", "mmol/L", "degrees Celsius", "beats/minute"]
LABELS = ["LOW", "MEDIUM", "HIGH"]
FEATURE_LABELS = [
    "Age",
    "Systolic blood pressure",
    "Diastolic blood pressure",
    "Blood glucose",
    "Body temperature",
    "Heart rate",
]
logger = logging.getLogger("bloomcare.models")


class ModelUnavailable(Exception):
    pass


class UnsupportedMeasurements(Exception):
    def __init__(self, fields):
        self.fields = fields
        super().__init__("Measurements are outside this model's training range")


def model_summary(manifest):
    evaluation = manifest["evaluation"]
    score = evaluation["random_forest"]
    return {
        "version": manifest["version"],
        "research_only": True,
        "evaluation": {
            "accuracy": score["accuracy"],
            "macro_f1": score["macro_f1"],
            "medium_recall": score["class_report"]["MEDIUM"]["recall"],
            "held_out_rows": evaluation["split"]["held_out_rows"],
        },
        "source": {
            "name": "UCI Maternal Health Risk",
            "doi": "10.24432/C5DP5D",
            "license": "CC BY 4.0",
        },
        "limitations": [
            (
                "The maternal-risk dataset has no pre-eclampsia outcomes. "
                "PE screening uses a separate model and additional measurements."
            )
            if item == "No pre-eclampsia outcome label is present; no PE model was trained."
            else item
            for item in evaluation["limitations"]
        ],
    }


@dataclass(frozen=True)
class MaternalModel:
    pipeline: object
    explainer: object
    manifest: dict
    artifact_sha256: str

    @property
    def id(self):
        return str(uuid5(NAMESPACE_URL, f"bloomcare:maternal:{self.artifact_sha256}"))

    def infer(self, observations):
        import numpy as np
        import pandas as pd

        unsupported = []
        for feature, label, unit in zip(FEATURES, FEATURE_LABELS, UNITS, strict=True):
            value = float(observations[feature])
            minimum, maximum = self.manifest["observed_training_ranges"][feature]
            if not math.isfinite(value) or value < minimum - 1e-8 or value > maximum + 1e-8:
                unsupported.append(
                    {
                        "feature": feature,
                        "label": label,
                        "value": value,
                        "minimum": minimum,
                        "maximum": maximum,
                        "unit": unit,
                    }
                )
        if unsupported:
            raise UnsupportedMeasurements(unsupported)

        frame = pd.DataFrame([[observations[name] for name in FEATURES]], columns=FEATURES)
        probabilities = np.asarray(self.pipeline.predict_proba(frame)[0], dtype=float)
        classes = self.pipeline.named_steps["model"].classes_.tolist()
        if (
            probabilities.shape != (3,)
            or not np.isfinite(probabilities).all()
            or (probabilities < 0).any()
            or (probabilities > 1).any()
            or not np.isclose(probabilities.sum(), 1.0, atol=1e-8, rtol=0)
        ):
            raise ModelUnavailable("The model returned an invalid score")
        class_index = int(np.argmax(probabilities))
        risk = classes[class_index]
        transformed = self.pipeline.named_steps["preprocess"].transform(frame)
        values = np.asarray(self.explainer.shap_values(transformed), dtype=float)
        base = np.asarray(self.explainer.expected_value, dtype=float)
        if (
            values.shape != (1, len(FEATURES), 3)
            or base.shape != (3,)
            or not np.isfinite(values).all()
            or not np.isfinite(base).all()
            or not np.allclose(base + values[0].sum(axis=0), probabilities, atol=1e-7, rtol=0)
        ):
            raise ModelUnavailable("The explanation does not reconstruct the model score")
        return {
            "maternal_risk": risk,
            "class_scores": dict(zip(classes, probabilities.tolist(), strict=True)),
            "explanation": {
                "method": "Tree SHAP",
                "feature_perturbation": "tree_path_dependent",
                "explained_class": risk,
                "base_score": float(base[class_index]),
                "model_score": float(probabilities[class_index]),
                "features": [
                    {
                        "feature": name,
                        "label": label,
                        "unit": unit,
                        "value": observations[name],
                        "contribution": float(values[0, index, class_index]),
                    }
                    for index, (name, label, unit) in enumerate(
                        zip(FEATURES, FEATURE_LABELS, UNITS, strict=True)
                    )
                ],
            },
        }


def load_registered_model(model_dir: Path, trust_path: Path):
    """The registry is created by the local activation CLI, never by an API upload."""
    try:
        artifact = model_dir / "pipeline.joblib"
        manifest_path = model_dir / "manifest.json"
        if (
            trust_path.stat().st_size > 64_000
            or manifest_path.stat().st_size > 64_000
            or artifact.stat().st_size > 20_000_000
        ):
            raise ValueError("Unexpected artifact size")
        trust = json.loads(trust_path.read_text(encoding="utf-8"))
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        artifact_bytes = artifact.read_bytes()
        digest = hashlib.sha256(artifact_bytes).hexdigest()
        if (
            trust["schema_version"] != 1
            or trust["mode"] != "research_only"
            or trust["model_version"] != "maternal_rf_v0.2"
            or trust["artifact_sha256"] != digest
            or trust["manifest_sha256"] != hashlib.sha256(manifest_bytes).hexdigest()
            or manifest["artifact_sha256"] != digest
            or manifest["version"] != "maternal_rf_v0.2"
            or manifest["model_kind"] != "maternal_risk"
            or manifest["dataset_sha256"] != SOURCE_SHA256
            or manifest["old_project_artifacts_used"] is not False
        ):
            raise ValueError("Model provenance or local registration does not match")
        expected_features = [
            {"name": name, "unit": unit, "dtype": "numeric"}
            for name, unit in zip(FEATURES, UNITS, strict=True)
        ]
        if manifest["features"] != expected_features:
            raise ValueError("Feature order or units do not match")
        if manifest["python_version"].split(".")[:2] != [str(v) for v in sys.version_info[:2]]:
            raise ValueError("Python minor version differs from training")
        if set(manifest["dependencies"]) != {"scikit-learn", "pandas", "numpy", "joblib", "scipy"}:
            raise ValueError("Training dependency contract is not recognized")
        for name, version in manifest["dependencies"].items():
            if importlib.metadata.version(name) != version:
                raise ValueError("Training dependency versions differ")
        for name in FEATURES:
            minimum, maximum = manifest["observed_training_ranges"][name]
            if not all(math.isfinite(v) for v in [minimum, maximum]) or minimum > maximum:
                raise ValueError("Training ranges are invalid")
        summary = model_summary(manifest)
        if any(
            not math.isfinite(summary["evaluation"][name])
            or not 0 <= summary["evaluation"][name] <= 1
            for name in ["accuracy", "macro_f1", "medium_recall"]
        ):
            raise ValueError("Evaluation metrics are invalid")

        import joblib
        import shap
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline

        # Only the hash-pinned local artifact is loaded. Hashes do not make an
        # arbitrary third-party pickle safe; activation requires local training.
        pipeline = joblib.load(io.BytesIO(artifact_bytes))
        if (
            not isinstance(pipeline, Pipeline)
            or list(pipeline.named_steps) != ["preprocess", "model"]
            or not isinstance(pipeline.named_steps["preprocess"], SimpleImputer)
            or not isinstance(pipeline.named_steps["model"], RandomForestClassifier)
            or pipeline.feature_names_in_.tolist() != FEATURES
            or set(pipeline.named_steps["model"].classes_) != set(LABELS)
            or pipeline.named_steps["model"].classes_.tolist()
            != manifest["class_order_in_artifact"]
        ):
            raise ValueError("Pipeline structure or class mapping does not match")
        explainer = shap.TreeExplainer(
            pipeline.named_steps["model"],
            model_output="raw",
            feature_perturbation="tree_path_dependent",
        )
        return MaternalModel(pipeline, explainer, manifest, digest)
    except Exception as error:
        logger.warning("Research model unavailable; type=%s", type(error).__name__)
        raise ModelUnavailable("A verified local maternal-risk model is not available") from None


@lru_cache(maxsize=1)
def _cached_model():
    return load_registered_model(MODEL_DIR, TRUST_PATH)


def get_maternal_model():
    if not get_settings().bloomcare_research_assessments:
        raise ModelUnavailable("Experimental maternal-risk assessment is disabled")
    return _cached_model()
