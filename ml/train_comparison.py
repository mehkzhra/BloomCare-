"""Reproducible model comparisons. Never replace a registered model with a worse candidate."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import numpy as np
from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.utils.class_weight import compute_sample_weight

from ml.data_contract import CLASS_ORDER, load_data, split_data
from ml.fetch_data import EXPECTED_CSV_SHA256, ROOT, fetch_data
from ml.train_maternal import evaluate

SEED = 20261010
CV_SEED = 20261016
BASELINE = dict(
    n_estimators=400,
    max_depth=12,
    min_samples_leaf=2,
    max_features="sqrt",
    class_weight="balanced_subsample",
    random_state=SEED,
    n_jobs=1,
)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def promotion_gate(baseline, candidate):
    """All four non-regression checks must pass; no score is substituted or rounded."""
    checks = {
        "accuracy": candidate["accuracy"] >= baseline["accuracy"],
        "macro_f1": candidate["macro_f1"] >= baseline["macro_f1"],
        "medium_recall": candidate["class_report"]["MEDIUM"]["recall"]
        >= baseline["class_report"]["MEDIUM"]["recall"],
        "high_recall": candidate["class_report"]["HIGH"]["recall"]
        >= baseline["class_report"]["HIGH"]["recall"],
    }
    improved = candidate["macro_f1"] > baseline["macro_f1"]
    return {
        "checks": checks,
        "internal_gate_passed": all(checks.values()) and improved,
        "active_model_changed": False,
    }


def export_forest(model, path, features, metadata):
    """Portable, non-executable evidence artifact; deliberately not an active application model."""
    trees = []
    for estimator in model.estimators_:
        tree = estimator.tree_
        values = tree.value[:, 0, :]
        probabilities = values / values.sum(axis=1, keepdims=True)
        trees.append(
            {
                "left": tree.children_left.tolist(),
                "right": tree.children_right.tolist(),
                "feature": tree.feature.tolist(),
                "threshold": tree.threshold.tolist(),
                "scores": probabilities.tolist(),
                "node_sample_weights": tree.weighted_n_node_samples.tolist(),
            }
        )
    payload = {
        "schema_version": 1,
        "purpose": "INACTIVE_TRAINING_EVIDENCE",
        "classes": model.classes_.tolist(),
        "features": list(features),
        "metadata": metadata,
        "trees": trees,
    }
    write_json(path, payload)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configurations(family):
    if family == "random_forest":
        items = [
            dict(max_depth=d, min_samples_leaf=leaf, max_features=m, class_weight=w)
            for d, leaf, m, w in product(
                [6, 12, None],
                [1, 2, 4],
                ["sqrt", 1.0],
                ["balanced_subsample", {"LOW": 1, "MEDIUM": 2, "HIGH": 1.5}],
            )
        ]
        items.insert(
            0,
            {
                k: BASELINE[k]
                for k in [
                    "max_depth",
                    "min_samples_leaf",
                    "max_features",
                    "class_weight",
                ]
            },
        )
        return items
    if family == "extra_trees":
        return [
            dict(max_depth=d, min_samples_leaf=leaf, max_features=m, class_weight=w)
            for d, leaf, m, w in product(
                [12, None],
                [1, 2, 4],
                ["sqrt", 1.0],
                ["balanced", {"LOW": 1, "MEDIUM": 2, "HIGH": 1.5}],
            )
        ]
    return [
        dict(n_estimators=n, learning_rate=r, max_depth=d, min_samples_leaf=leaf)
        for n, r, d, leaf in product([160, 320], [0.04, 0.1], [1, 2, 3], [3, 8])
    ]


def fit_candidate(family, parameters, features, labels):
    if family == "gradient_boosting":
        return GradientBoostingClassifier(random_state=SEED, **parameters).fit(
            features, labels, sample_weight=compute_sample_weight("balanced", labels)
        )
    constructor = (
        RandomForestClassifier if family == "random_forest" else ExtraTreesClassifier
    )
    return constructor(n_estimators=400, random_state=SEED, n_jobs=1, **parameters).fit(
        features, labels
    )


def compare(source, output, families):
    source = Path(source)
    if hashlib.sha256(source.read_bytes()).hexdigest() != EXPECTED_CSV_SHA256:
        raise ValueError(
            "The source must match the reviewed UCI dataset. New datasets need a reviewed contract."
        )
    if output.exists():
        raise ValueError(
            "Choose a new output directory; previous training evidence is retained."
        )
    features, labels, groups, audit = load_data(source)
    train_rows, held_out = split_data(features, labels, groups)
    training, target, group = (
        features.iloc[train_rows],
        labels.iloc[train_rows],
        groups.iloc[train_rows],
    )
    folds = list(
        StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=CV_SEED).split(
            training, target, group
        )
    )
    for fit, valid in folds:
        if set(group.iloc[fit]) & set(group.iloc[valid]):
            raise ValueError(
                "A measurement group crossed the cross-validation boundary"
            )
    baseline = RandomForestClassifier(**BASELINE).fit(training, target)
    base_score = evaluate(baseline, features.iloc[held_out], labels.iloc[held_out])
    comparisons = []
    for family in families:
        rows, options = [], configurations(family)
        for index, params in enumerate(options):
            predictions = np.empty(len(target), dtype=object)
            for fit, valid in folds:
                model = fit_candidate(
                    family, params, training.iloc[fit], target.iloc[fit]
                )
                predictions[valid] = model.predict(training.iloc[valid])
            report = classification_report(
                target,
                predictions,
                labels=CLASS_ORDER,
                output_dict=True,
                zero_division=0,
            )
            rows.append(
                {
                    "index": index,
                    "parameters": params,
                    "accuracy": float(accuracy_score(target, predictions)),
                    "macro_f1": float(
                        f1_score(
                            target, predictions, labels=CLASS_ORDER, average="macro"
                        )
                    ),
                    "class_report": report,
                }
            )
            write_json(output / (family + "-progress.json"), rows)
            print(
                f"{family}: {index + 1}/{len(options)} CV configurations completed",
                flush=True,
            )
        winner = max(
            rows,
            key=lambda r: (
                r["macro_f1"],
                r["class_report"]["MEDIUM"]["recall"],
                -r["index"],
            ),
        )
        model = fit_candidate(family, winner["parameters"], training, target)
        score = evaluate(model, features.iloc[held_out], labels.iloc[held_out])
        entry = {
            "family": family,
            "candidate_count": len(options),
            "winner_cv": winner,
            "held_out": score,
            "gate": promotion_gate(base_score, score),
        }
        if family != "gradient_boosting":
            entry["candidate_artifact_sha256"] = export_forest(
                model,
                output / (family + "-candidate.json"),
                features.columns,
                {
                    "selected_by": "Training partition grouped CV",
                    "score": score,
                    "active": False,
                    "dataset_sha256": audit["source_sha256"],
                },
            )
        comparisons.append(entry)
        write_json(
            output / (family + "-report.json"), {**entry, "all_cv_results": rows}
        )
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "UCI Maternal Health Risk; CC BY 4.0; DOI 10.24432/C5DP5D",
        "audit": audit,
        "split": {
            "train_rows": len(train_rows),
            "test_rows": len(held_out),
            "overlapping_groups": 0,
        },
        "method": (
            "Five-fold grouped CV inside original training partition; "
            "macro-F1 selects each family candidate"
        ),
        "baseline": {
            "version": "maternal_rf_v0.2",
            "parameters": BASELINE,
            "held_out": base_score,
        },
        "comparisons": comparisons,
        "active_model_changed": False,
        "limitations": [
            "The historical holdout results were already published; "
            "these are exploratory internal comparisons, not external validation.",
            "No patient identifiers are available; repeated-patient leakage cannot be ruled out.",
            "35 measurement groups have conflicting source labels; "
            "none were relabelled to improve scores.",
            "No synthetic measurements, shifted test groups or invented PE outcomes are used.",
            "Passing an internal gate would still not establish clinical validity. "
            "This command does not change application registration.",
        ],
    }
    write_json(output / "comparison.json", report)
    print(
        "Training and comparisons completed. Reports saved; existing model registration retained."
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--family",
        choices=["all", "random_forest", "extra_trees", "gradient_boosting"],
        default="all",
    )
    args = parser.parse_args()
    fallback = ROOT.parent / "backend/tests/fixtures/maternal_risk_uci.csv"
    source = args.data or (fallback if fallback.is_file() else fetch_data())
    output = args.output or ROOT / "training_reports/runs" / datetime.now(
        timezone.utc
    ).strftime("%Y%m%d-%H%M%S")
    families = (
        ["random_forest", "extra_trees", "gradient_boosting"]
        if args.family == "all"
        else [args.family]
    )
    compare(source, output, families)


if __name__ == "__main__":
    main()
