"""Offline export of node weights from the exact owner-authorized legacy forest."""

import argparse
import hashlib
import json
from pathlib import Path

SOURCE_SHA256 = "4959ef608bd58ece855566d292c1940be3edf0ddb0e1028ea8923f2c887032bd"


def export(source, output):
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("The original PE artifact does not match the pinned source")
    import joblib

    model = joblib.load(source)
    weights = [
        tree.tree_.weighted_n_node_samples.tolist() for tree in model.estimators_
    ]
    data = {"source_sha256": SOURCE_SHA256, "node_sample_weights": weights}
    raw = (json.dumps(data, separators=(",", ":"), allow_nan=False) + "\n").encode()
    output.write_bytes(raw)
    print(
        "Exported actual fitted node weights; SHA-256:", hashlib.sha256(raw).hexdigest()
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    export(args.source, args.output)
