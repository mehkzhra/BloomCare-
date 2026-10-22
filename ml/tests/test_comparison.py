import hashlib
import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier

from ml.data_contract import load_data
from ml.train_comparison import compare, export_forest, promotion_gate

SOURCE = (
    Path(__file__).resolve().parents[2] / "backend/tests/fixtures/maternal_risk_uci.csv"
)


def score():
    return {
        "accuracy": 0.71,
        "macro_f1": 0.66,
        "class_report": {"MEDIUM": {"recall": 0.33}, "HIGH": {"recall": 0.73}},
    }


def test_more_accuracy_cannot_promote_a_candidate_with_worse_high_risk_recall():
    baseline = score()
    candidate = deepcopy(baseline)
    candidate.update(accuracy=0.8, macro_f1=0.7)
    candidate["class_report"]["HIGH"]["recall"] = 0.6
    gate = promotion_gate(baseline, candidate)
    assert not gate["internal_gate_passed"] and not gate["active_model_changed"]


def test_internal_improvement_is_distinct_from_application_activation():
    baseline = score()
    candidate = deepcopy(baseline)
    candidate.update(accuracy=0.8, macro_f1=0.75)
    gate = promotion_gate(baseline, candidate)
    assert gate["internal_gate_passed"] and not gate["active_model_changed"]


def test_unreviewed_dataset_fails_before_creating_an_output_directory(tmp_path):
    data = tmp_path / "changed.csv"
    data.write_bytes(SOURCE.read_bytes() + b"\n")
    output = tmp_path / "report"
    with pytest.raises(ValueError, match="reviewed UCI"):
        compare(data, output, ["random_forest"])
    assert not output.exists()


def test_portable_forest_evidence_matches_the_actual_fitted_model(tmp_path):
    features, labels, _, _ = load_data(SOURCE)
    model = RandomForestClassifier(n_estimators=9, max_depth=4, random_state=17).fit(
        features, labels
    )
    path = tmp_path / "forest.json"
    checksum = export_forest(model, path, features.columns, {"active": False})
    artifact = json.loads(path.read_text())
    assert checksum == hashlib.sha256(path.read_bytes()).hexdigest()
    assert artifact["purpose"] == "INACTIVE_TRAINING_EVIDENCE"
    actual = []
    for row in features.iloc[:30].to_numpy(dtype=np.float32):
        scores = []
        for tree in artifact["trees"]:
            node = 0
            while tree["left"][node] >= 0:
                node = (
                    tree["left"][node]
                    if row[tree["feature"][node]] <= tree["threshold"][node]
                    else tree["right"][node]
                )
            scores.append(tree["scores"][node])
        actual.append(np.mean(scores, axis=0))
    assert np.allclose(
        actual, model.predict_proba(features.iloc[:30]), atol=1e-12, rtol=0
    )
