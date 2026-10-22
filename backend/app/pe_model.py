"""Read the pinned original PE forest as JSON; never unpickle a model at runtime."""

import hashlib
import json
import logging
import math
import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.pe_contract import (
    CLASS_ORDER,
    FEATURES,
    SOURCE_COMMIT,
    UNUSED_INDICES,
    VERSION,
    input_contract,
)

MODEL_DIR = Path(__file__).resolve().parents[2] / "ml/artifacts/legacy_pe_v0.7.1"
ARTIFACT_SHA256 = "016784669081afc938704513148cdf17b478907498f36a824dcc2ae589917735"
MANIFEST_SHA256 = "3cafe3a423cdb148641a3eb14e00519b19db3fc6f0de7dcbccf9d3c4b9087c4b"
logger = logging.getLogger("bloomcare.models")


class PEModelUnavailable(Exception):
    pass


class PEUnsupportedMeasurements(Exception):
    def __init__(self, fields):
        self.fields = fields
        super().__init__("Measurements are outside the PE model's training range")


def forest_scores(artifact, values):
    # sklearn's classifier converts inputs to float32 before applying double thresholds.
    vector = [
        None
        if value is None or not math.isfinite(value)
        else struct.unpack("f", struct.pack("f", float(value)))[0]
        for value in values
    ]
    total = [0.0, 0.0, 0.0]
    for tree in artifact["trees"]:
        node = 0
        while tree["left"][node] != -1:
            feature = tree["feature"][node]
            value = vector[feature]
            if value is None:
                raise PEModelUnavailable("A used PE measurement is missing")
            node = tree["left"][node] if value <= tree["threshold"][node] else tree["right"][node]
        for index, score in enumerate(tree["scores"][node]):
            total[index] += score
    return [score / len(artifact["trees"]) for score in total]


def pe_summary(manifest):
    return {
        "version": manifest["version"],
        "validation": "Clinical validation pending",
        "source": {
            "repository": manifest["source"]["repository"],
            "commit": manifest["source"]["commit"],
        },
        "artifact_sha256": manifest["artifact_sha256"],
        "input_fields": input_contract(),
        "evaluation": manifest["evaluation"],
        "limitations": manifest["limitations"],
    }


@dataclass(frozen=True)
class PEModel:
    artifact: dict
    manifest: dict

    def infer(self, observations):
        unsupported = []
        for field in input_contract():
            value = observations[field["name"]]
            if (
                not math.isfinite(value)
                or value < field["minimum"] - 1e-8
                or value > field["maximum"] + 1e-8
            ):
                unsupported.append({**field, "feature": field["name"], "value": value})
        if unsupported:
            raise PEUnsupportedMeasurements(unsupported)
        values = [
            None if index in UNUSED_INDICES else observations[name]
            for index, (name, *_rest) in enumerate(FEATURES)
        ]
        scores = forest_scores(self.artifact, values)
        if not all(math.isfinite(v) and 0 <= v <= 1 for v in scores) or not math.isclose(
            sum(scores), 1.0, abs_tol=1e-10
        ):
            raise PEModelUnavailable("The PE forest returned invalid class scores")
        from app.pe_explanation import explain_scores

        return {
            "risk": CLASS_ORDER[max(range(3), key=lambda i: scores[i])],
            "class_scores": dict(zip(CLASS_ORDER, scores, strict=True)),
            "explanation": explain_scores(self, observations, scores),
        }


def load_pe_model(directory):
    try:
        path = directory / "forest.json"
        manifest_path = directory / "manifest.json"
        if path.stat().st_size > 4_000_000 or manifest_path.stat().st_size > 64_000:
            raise ValueError("Unexpected PE artifact size")
        raw, metadata = path.read_bytes(), manifest_path.read_bytes()
        if (
            hashlib.sha256(raw).hexdigest() != ARTIFACT_SHA256
            or hashlib.sha256(metadata).hexdigest() != MANIFEST_SHA256
        ):
            raise ValueError("PE artifact integrity check failed")
        artifact, manifest = json.loads(raw), json.loads(metadata)
        if (
            artifact["schema_version"] != 1
            or artifact["class_order"] != CLASS_ORDER
            or artifact["columns"] != [feature[1] for feature in FEATURES]
            or manifest["version"] != VERSION
            or manifest["source"]["commit"] != SOURCE_COMMIT
            or manifest["features"] != input_contract()
            or manifest["artifact_sha256"] != ARTIFACT_SHA256
            or len(artifact["trees"]) != 200
        ):
            raise ValueError("PE feature or source contract does not match")
        for tree in artifact["trees"]:
            count = len(tree["left"])
            if not 1 <= count <= 1000 or any(len(v) != count for v in tree.values()):
                raise ValueError("Invalid PE tree dimensions")
            for index in range(count):
                left, right, feature = (
                    tree["left"][index],
                    tree["right"][index],
                    tree["feature"][index],
                )
                if left == -1:
                    if right != -1 or feature != -2:
                        raise ValueError("Invalid PE leaf")
                elif (
                    not index < left < count
                    or not index < right < count
                    or feature not in set(range(15)) - UNUSED_INDICES
                ):
                    raise ValueError("Invalid PE child or feature")
                scores = tree["scores"][index]
                if (
                    len(scores) != 3
                    or not all(math.isfinite(v) and 0 <= v <= 1 for v in scores)
                    or not math.isclose(sum(scores), 1, abs_tol=1e-10)
                    or not math.isfinite(tree["threshold"][index])
                ):
                    raise ValueError("Invalid PE node score")
        return PEModel(artifact, manifest)
    except Exception as error:
        logger.warning("PE model unavailable; type=%s", type(error).__name__)
        raise PEModelUnavailable("The PE screening model is currently unavailable") from None


@lru_cache(maxsize=1)
def get_pe_model():
    return load_pe_model(MODEL_DIR)
