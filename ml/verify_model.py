"""Verify the artifact generated locally by this kit and replay its held-out evaluation."""

import hashlib
import importlib.metadata
import json
from pathlib import Path

import joblib

from ml.data_contract import CLASS_ORDER, FEATURES, load_data, split_data
from ml.fetch_data import ROOT
from ml.train_maternal import evaluate


def verify(*, model_dir=None, data_path=None):
    output = Path(model_dir) if model_dir is not None else ROOT / "artifacts" / "maternal_rf_v0.2"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    artifact = output / "pipeline.joblib"
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != manifest["artifact_sha256"]:
        raise ValueError("Artifact checksum differs from the training manifest")
    for name, version in manifest["dependencies"].items():
        if importlib.metadata.version(name) != version:
            raise ValueError(f"{name} version differs from the training environment")
    source = Path(data_path) if data_path is not None else ROOT / "data" / "maternal_risk_uci.csv"
    features, labels, groups, audit = load_data(source)
    if audit["source_sha256"] != manifest["dataset_sha256"]:
        raise ValueError("Dataset checksum differs from the training manifest")
    if [item["name"] for item in manifest["features"]] != FEATURES:
        raise ValueError("Manifest feature contract is not recognized")
    _, held_out = split_data(features, labels, groups)
    # Only load this trusted artifact just created by the local training command.
    # A hash is an integrity check, not proof that a third-party pickle is safe.
    pipeline = joblib.load(artifact)
    if set(pipeline.named_steps["model"].classes_) != set(CLASS_ORDER):
        raise ValueError("The model classes do not match BloomCare's risk labels")
    actual = evaluate(pipeline, features.iloc[held_out], labels.iloc[held_out])
    expected = manifest["evaluation"]["random_forest"]
    if actual != expected:
        raise ValueError("Reloaded model evaluation differs from the stored held-out results")
    split_rows = json.loads((output / "split.json").read_text(encoding="utf-8"))
    train_groups = {row["group_sha256"] for row in split_rows if row["partition"] == "train"}
    test_groups = {row["group_sha256"] for row in split_rows if row["partition"] == "held_out"}
    if train_groups & test_groups:
        raise ValueError("Saved split contains overlapping measurement groups")
    print(
        "Verified: artifact integrity, dependency versions, feature contract, "
        "non-overlapping groups, and replayed held-out evaluation."
    )
    print("Research artifact verified. This command does not change application activation.")


if __name__ == "__main__":
    verify()
