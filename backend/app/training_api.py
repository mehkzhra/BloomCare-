"""Administrative projection of shipped, reproducible training evidence."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.models import User
from app.security import require_role

router = APIRouter(prefix="/api/admin")
REPORTS = Path(__file__).resolve().parents[2] / "ml/training_reports"


@router.get("/training-evidence")
def training_evidence(_user: User = Depends(require_role("admin"))):
    try:
        maternal = json.loads((REPORTS / "v1.0.0/comparison.json").read_text())
        pe = json.loads((REPORTS / "pe-v1.0.0/pe-retraining-report.json").read_text())
        candidates = []
        for row in maternal["comparisons"]:
            score = row["held_out"]
            candidates.append(
                {
                    "family": row["family"],
                    "configurations": row["candidate_count"],
                    "cv_macro_f1": row["winner_cv"]["macro_f1"],
                    "accuracy": score["accuracy"],
                    "macro_f1": score["macro_f1"],
                    "medium_recall": score["class_report"]["MEDIUM"]["recall"],
                    "high_recall": score["class_report"]["HIGH"]["recall"],
                    "gate": row["gate"],
                }
            )
        return {
            "created_at": maternal["created_at"],
            "baseline": maternal["baseline"],
            "dataset_audit": maternal["audit"],
            "split": maternal["split"],
            "candidates": candidates,
            "active_model_changed": maternal["active_model_changed"],
            "limitations": maternal["limitations"],
            "pe": {
                key: pe[key]
                for key in [
                    "raw_rows",
                    "usable_rows",
                    "exact_duplicates_removed",
                    "train_rows",
                    "test_rows",
                    "test_accuracy",
                    "test_macro_f1",
                    "activation",
                    "limitations",
                ]
            },
        }
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(
            503, "Training evidence is unavailable. Check the installed release files."
        ) from None
