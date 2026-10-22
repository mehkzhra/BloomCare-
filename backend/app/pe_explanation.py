"""Exact tree-path SHAP over the pinned PE forest and its actual fitted node weights."""

import hashlib
import json
import math
from functools import lru_cache

from app.pe_contract import CLASS_ORDER, FEATURES, UNUSED_INDICES
from app.pe_model import MODEL_DIR, PEModelUnavailable, get_pe_model

WEIGHTS_SHA256 = "c81f12c94041328ac21bcc1b054087ae5e1cc54b8b8d78ece665fcecfd554d3c"


@lru_cache(maxsize=1)
def explainer():
    import numpy as np
    import shap

    model = get_pe_model()
    raw = (MODEL_DIR / "explanation-weights.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != WEIGHTS_SHA256:
        raise PEModelUnavailable("PE explanation weights failed integrity verification")
    data = json.loads(raw)
    if data["source_sha256"] != (
        "4959ef608bd58ece855566d292c1940be3edf0ddb0e1028ea8923f2c887032bd"
    ) or len(data["node_sample_weights"]) != len(model.artifact["trees"]):
        raise PEModelUnavailable("PE explanation source does not match")
    trees = []
    for tree, weights in zip(model.artifact["trees"], data["node_sample_weights"], strict=True):
        if len(weights) != len(tree["left"]) or any(
            not math.isfinite(v) or v <= 0 for v in weights
        ):
            raise PEModelUnavailable("Invalid PE explanation node weights")
        trees.append(
            {
                "children_left": np.asarray(tree["left"], dtype=np.int32),
                "children_right": np.asarray(tree["right"], dtype=np.int32),
                "children_default": np.asarray(tree["left"], dtype=np.int32),
                "features": np.asarray(tree["feature"], dtype=np.int32),
                "thresholds": np.asarray(tree["threshold"], dtype=np.float64),
                "values": np.asarray(tree["scores"], dtype=np.float64)
                / len(model.artifact["trees"]),
                "node_sample_weight": np.asarray(weights, dtype=np.float64),
            }
        )
    return shap.TreeExplainer(
        {"trees": trees, "input_dtype": np.float32, "internal_dtype": np.float64},
        feature_perturbation="tree_path_dependent",
    )


def explain_scores(model, observations, scores):
    import numpy as np

    vector = np.asarray(
        [
            [
                np.nan if i in UNUSED_INDICES else observations[name]
                for i, (name, *_rest) in enumerate(FEATURES)
            ]
        ],
        dtype=np.float32,
    )
    engine = explainer()
    expected = np.asarray(engine.model.predict(vector))[0]
    if not np.allclose(expected, scores, atol=1e-9, rtol=0):
        raise PEModelUnavailable("PE explanation does not match the saved forest output")
    index = int(np.argmax(scores))
    contributions = np.asarray(engine.shap_values(vector, check_additivity=True))[0, :, index]
    base = float(np.asarray(engine.expected_value)[index])
    if (
        not np.isfinite(contributions).all()
        or not math.isclose(base + float(contributions.sum()), scores[index], abs_tol=1e-7)
        or any(abs(float(contributions[i])) > 1e-12 for i in UNUSED_INDICES)
    ):
        raise PEModelUnavailable("PE SHAP additivity verification failed")
    return {
        "method": "TreeSHAP",
        "feature_perturbation": "tree_path_dependent",
        "explained_class": CLASS_ORDER[index],
        "base_score": base,
        "model_score": scores[index],
        "features": [
            {
                "feature": name,
                "label": label,
                "unit": unit,
                "value": observations[name],
                "contribution": float(contributions[i]),
            }
            for i, (name, _column, label, unit, *_rest) in enumerate(FEATURES)
            if i not in UNUSED_INDICES
        ],
    }
