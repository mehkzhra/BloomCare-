"""Register the verified local artifact and enable only experimental assessments."""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from ml.data_contract import load_data  # noqa: E402
from ml.verify_model import verify  # noqa: E402

from app.maternal_model import load_registered_model  # noqa: E402


def atomic_text(path: Path, contents: str):
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".bloomcare-",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(contents)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def activate(root: Path):
    environment = root / "backend" / ".env"
    if not environment.is_file():
        raise ValueError("Backend configuration is missing. Complete the foundation setup first.")
    directory = root / "ml" / "artifacts" / "maternal_rf_v0.2"
    source = root / "ml" / "data" / "maternal_risk_uci.csv"
    verify(model_dir=directory, data_path=source)
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    trust = {
        "schema_version": 1,
        "model_version": manifest["version"],
        "artifact_sha256": hashlib.sha256((directory / "pipeline.joblib").read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "mode": "research_only",
        "activated_at": datetime.now(timezone.utc).isoformat(),
    }
    registry_text = json.dumps(trust, indent=2) + "\n"
    with TemporaryDirectory(prefix="bloomcare-model-check-") as temporary:
        candidate = Path(temporary) / "trust.json"
        candidate.write_text(registry_text, encoding="utf-8")
        model = load_registered_model(directory, candidate)
        features, _, _, _ = load_data(source)
        within = features.index.to_series().notna()
        for name in features.columns:
            minimum, maximum = manifest["observed_training_ranges"][name]
            within &= features[name].between(minimum, maximum)
        if not within.any():
            raise ValueError("No supported public-source example exists for the explanation check")
        # Check real model scores and SHAP on a source example. Do not create a patient record.
        model.infer(features.loc[within].iloc[0].to_dict())
    original = environment.read_text(encoding="utf-8")
    flag = "BLOOMCARE_RESEARCH_ASSESSMENTS=true"
    pattern = r"(?m)^[ \t]*BLOOMCARE_RESEARCH_ASSESSMENTS[ \t]*=[^\r\n]*"
    updated = re.sub(pattern, flag, original)
    if not re.search(pattern, original):
        updated = original + ("" if original.endswith("\n") else "\n") + flag + "\n"
    atomic_text(root / "backend" / "model-trust.json", registry_text)
    atomic_text(environment, updated)
    return trust


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--enable", action="store_true", help="Enable research-only maternal assessments"
    )
    args = parser.parse_args()
    if not args.enable:
        parser.error("Pass --enable to activate the locally trained research model")
    try:
        activate(ROOT)
    except Exception as error:
        print(
            f"Research activation stopped ({type(error).__name__}). "
            "Check the local training checkpoint and installed dependencies.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    print("Research maternal-risk assessment enabled after integrity, evaluation, and SHAP checks.")
    print("Restart the backend. Check the assessment page for maternal and PE availability.")
    print("Existing credentials, database settings, and trained model files were preserved.")


if __name__ == "__main__":
    main()
