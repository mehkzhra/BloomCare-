"""Build the reviewed model from the bundled, checksum-pinned public fixture."""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]

from app.maternal_model import load_registered_model  # noqa: E402
from app.pe_explanation import WEIGHTS_SHA256  # noqa: E402
from app.pe_model import load_pe_model  # noqa: E402

from ml.data_contract import load_data  # noqa: E402
from ml.train_maternal import train  # noqa: E402
from ml.verify_model import verify  # noqa: E402


def prepare(root=ROOT):
    source = root / "backend/tests/fixtures/maternal_risk_uci.csv"
    directory = root / "ml/artifacts/maternal_rf_v0.2"
    train(data_path=source, output_path=directory)
    verify(model_dir=directory, data_path=source)
    manifest_bytes = (directory / "manifest.json").read_bytes()
    trust = {
        "schema_version": 1,
        "model_version": "maternal_rf_v0.2",
        "artifact_sha256": hashlib.sha256((directory / "pipeline.joblib").read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "mode": "research_only",
        "activated_at": datetime.now(timezone.utc).isoformat(),
    }
    trust_path = root / "backend/model-trust.json"
    trust_path.write_text(json.dumps(trust, indent=2) + "\n", encoding="utf-8")
    model = load_registered_model(directory, trust_path)
    features, _, _, _ = load_data(source)
    within = features.index.to_series().notna()
    for name, (low, high) in model.manifest["observed_training_ranges"].items():
        within &= features[name].between(low, high)
    model.infer(features.loc[within].iloc[0].to_dict())
    pe_directory = root / "ml/artifacts/legacy_pe_v0.7.1"
    load_pe_model(pe_directory)
    if hashlib.sha256((pe_directory / "explanation-weights.json").read_bytes()).hexdigest() != (
        WEIGHTS_SHA256
    ):
        raise ValueError("The original PE explanation weights are missing or changed")
    print("Cloud maternal model built and verified, including real SHAP inference.")
    print("The pinned original PE forest and explanation weights are included and verified.")


if __name__ == "__main__":
    prepare()
