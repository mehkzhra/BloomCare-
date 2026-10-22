"""Verify the delivered PE JSON model and reference scores without any patient data."""

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.pe_model import MODEL_DIR, forest_scores, get_pe_model  # noqa: E402


def verify():
    model = get_pe_model()
    fixtures = json.loads((MODEL_DIR / "parity-fixtures.json").read_text(encoding="utf-8"))
    for fixture in fixtures:
        actual = forest_scores(model.artifact, fixture["values"])
        if not all(math.isclose(left, right, abs_tol=1e-12, rel_tol=0)
                   for left, right in zip(actual, fixture["class_scores_in_original_order"],
                                          strict=True)):
            raise ValueError("PE reference scores did not match")
    return model


if __name__ == "__main__":
    try:
        verify()
    except Exception as error:
        print(f"PE model check stopped ({type(error).__name__}). Re-extract this update.",
              file=sys.stderr)
        raise SystemExit(1) from None
    print("PE forest integrity, column mapping and reference score checks passed.")
    print("Clinical validation is pending. Class scores are not disease probabilities.")
