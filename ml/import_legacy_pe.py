"""Export only the user's hash-pinned original PE forest into non-executable JSON.

Offline maintainer command; the web server never loads the original pickle. This
does not retrain, repair, or clinically validate the original model or its data.
"""

import argparse
import hashlib
import importlib.metadata
import json
import sys
import warnings
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.pe_contract import (  # noqa: E402
    CLASS_ORDER,
    FEATURES,
    SOURCE_COMMIT,
    UNUSED_INDICES,
    VERSION,
    input_contract,
)

SOURCE_HASHES = {
    "ml/models/preeclampsia_model.pkl": (
        "4959ef608bd58ece855566d292c1940be3edf0ddb0e1028ea8923f2c887032bd"
    ),
    "ml/models/preeclampsia_label_encoder.pkl": (
        "1f512be8ebcbe7f813a945d16e13849e7b14f2a0f02a55e50a85fff01c186d2c"
    ),
    "ml/datasets/train_dataset.xlsx": (
        "03cc79c707168b5862686088bde98e07b67cf4ec1587cc103e7a480a785ade2b"
    ),
    "ml/datasets/test_dataset.xlsx": (
        "29f0467b672c2e5b03ee737493a3d8a7d7fd1dd9b3249d5d824ec5e13183b8f2"
    ),
}


def read_source_sheet(path):
    """Read this pinned input workbook without an Excel runtime dependency."""
    import pandas as pd

    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        strings = [
            "".join(item.itertext())
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall(
                "s:si", ns
            )
        ]
        rows = []
        for row in ET.fromstring(archive.read("xl/worksheets/sheet1.xml")).findall(
            ".//s:row", ns
        ):
            cells = {}
            for cell in row.findall("s:c", ns):
                node = cell.find("s:v", ns)
                value = node.text if node is not None else None
                if cell.get("t") == "s" and value is not None:
                    value = strings[int(value)]
                column = "".join(char for char in cell.get("r") if char.isalpha())
                cells[column] = value
            rows.append(cells)
    frame = pd.DataFrame(
        [
            {name: row.get(column) for column, name in rows[0].items()}
            for row in rows[1:]
        ]
    )
    boolean_columns = [FEATURES[index][1] for index in (5, 6, 11)]
    mapping = {"yes": 1, "y": 1, "no": 0, "n": 0, "1": 1, "0": 0, "true": 1, "false": 0}
    for name in boolean_columns:
        frame[name] = frame[name].astype(str).str.strip().str.lower().map(mapping)
    for _name, column, *_rest in FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame[column] = frame[column].fillna(frame[column].median())
    frame["Risk_level"] = frame["Risk_level"].astype(str).str.strip().str.lower()
    return frame


def export(repository_dir, output_dir):
    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.preprocessing import LabelEncoder

    # Do not generalize this command into a model-upload/import endpoint.
    for path, digest in SOURCE_HASHES.items():
        if hashlib.sha256((repository_dir / path).read_bytes()).hexdigest() != digest:
            raise ValueError(
                f"Original repository file does not match pinned source: {path}"
            )
    with warnings.catch_warnings(record=True) as caught:
        model = joblib.load(repository_dir / "ml/models/preeclampsia_model.pkl")
        encoder = joblib.load(
            repository_dir / "ml/models/preeclampsia_label_encoder.pkl"
        )
    columns = [feature[1] for feature in FEATURES]
    if (
        type(model) is not RandomForestClassifier
        or type(encoder) is not LabelEncoder
        or model.feature_names_in_.tolist() != columns
        or encoder.classes_.tolist() != ["high", "low", "mid"]
        or model.classes_.tolist() != [0, 1, 2]
        or len(model.estimators_) != 200
    ):
        raise ValueError("Original PE structure, features, or class mapping changed")
    trees = []
    for estimator in model.estimators_:
        tree = estimator.tree_
        if set(tree.feature.tolist()) & UNUSED_INDICES:
            raise ValueError("Previously empty Doppler columns are unexpectedly used")
        weights = tree.value[:, 0, :]
        weights = weights / weights.sum(axis=1, keepdims=True)
        trees.append(
            {
                "left": tree.children_left.tolist(),
                "right": tree.children_right.tolist(),
                "feature": tree.feature.tolist(),
                "threshold": tree.threshold.tolist(),
                "scores": weights.tolist(),
            }
        )
    artifact = {
        "schema_version": 1,
        "class_order": CLASS_ORDER,
        "columns": columns,
        "trees": trees,
    }
    artifact_bytes = (
        json.dumps(artifact, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()
    from app.pe_model import forest_scores

    frames = [
        read_source_sheet(repository_dir / path)
        for path in ("ml/datasets/train_dataset.xlsx", "ml/datasets/test_dataset.xlsx")
    ]
    all_source = pd.concat([frame[columns] for frame in frames], ignore_index=True)
    rng = np.random.default_rng(42)
    probes = np.zeros((512, len(FEATURES)))
    for index, (_name, _column, _label, _unit, minimum, maximum) in enumerate(FEATURES):
        if index in UNUSED_INDICES:
            probes[:, index] = np.nan
        else:
            probes[:, index] = rng.uniform(minimum, maximum, len(probes))
    # Probe each learned split just below/at/above its threshold after float32 conversion.
    edges = []
    base = probes[0].copy()
    for tree in trees:
        for feature, threshold in zip(tree["feature"], tree["threshold"], strict=True):
            if feature < 0:
                continue
            value = np.float32(threshold)
            for nearby in (
                np.nextafter(value, np.float32(-np.inf)),
                value,
                np.nextafter(value, np.float32(np.inf)),
            ):
                row = base.copy()
                row[feature] = nearby
                edges.append(row)
    candidates = pd.concat(
        [
            all_source,
            pd.DataFrame(probes, columns=columns),
            pd.DataFrame(edges, columns=columns),
        ],
        ignore_index=True,
    )
    expected = model.predict_proba(candidates)
    actual = np.array([forest_scores(artifact, row) for row in candidates.to_numpy()])
    max_error = float(np.abs(expected - actual).max())
    if not np.allclose(actual, expected, atol=1e-12, rtol=0):
        raise ValueError("JSON forest does not preserve the original classifier scores")
    train, test = frames

    def keys(frame):
        return [
            tuple(None if pd.isna(v) else float(v) for v in row)
            for row in frame[columns].to_numpy()
        ]

    train_keys = set(keys(train))
    overlap = sum(key in train_keys for key in keys(test))
    y = encoder.inverse_transform(model.predict(test[columns]))
    report = classification_report(
        test["Risk_level"], y, zero_division=0, output_dict=True
    )
    manifest = {
        "version": VERSION,
        "model_kind": "legacy_pe_screening",
        "schema_version": 1,
        "artifact_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "source": {
            "repository": "https://github.com/mehkzhra/BloomCare",
            "commit": SOURCE_COMMIT,
            "files_sha256": SOURCE_HASHES,
            "authorization": "Owner requested reuse of old BloomCare PE detection.",
            "dataset_origin_and_license": "Not documented in the source repository.",
        },
        "original_sklearn_version": "1.8.0",
        "export_sklearn_version": importlib.metadata.version("scikit-learn"),
        "cross_version_pickle_warnings_observed": bool(caught),
        "conversion": "Original fitted tree arrays; no retraining and no runtime pickle loading.",
        "class_order": CLASS_ORDER,
        "features": input_contract(),
        "unused_columns": [columns[i] for i in sorted(UNUSED_INDICES)],
        "parity": {
            "source_rows": len(all_source),
            "synthetic_rows": len(probes),
            "split_boundary_rows": len(edges),
            "max_absolute_score_error": max_error,
            "reference": "Pinned original pickle loaded in the export environment; "
            "not a re-execution under its original training environment.",
        },
        "evaluation": {
            "training_rows": len(train),
            "test_rows": len(test),
            "unique_test_inputs": len(set(keys(test))),
            "test_rows_matching_training_inputs": overlap,
            "legacy_test_accuracy": float(accuracy_score(test["Risk_level"], y)),
            "legacy_test_macro_f1": report["macro avg"]["f1-score"],
            "independent_validation": False,
        },
        "limitations": [
            "The legacy haemoglobin column is labelled HB without a documented unit. "
            "Its unit and the source measurement definitions require confirmation "
            "before clinical use.",
            "This model has not been clinically or independently validated and cannot diagnose "
            "or exclude pre-eclampsia.",
            "Training has 162 rows; 25 of 41 test rows match training inputs and the test has "
            "only 25 unique input combinations. Its accuracy is not an independent estimate.",
            "Both Doppler columns are completely missing in training and unused by the forest; "
            "BloomCare does not request or invent those measurements.",
            "Some identical training inputs have conflicting target labels. Dataset provenance "
            "and outcome definitions are not documented in the old repository.",
            "The fetal-weight column spans 0.0001–9.55 kg and diastolic BP starts at 20 mmHg. "
            "These source values require a clinical and data-quality review.",
            "Training systolic BP is only 90–130 mmHg. Out-of-range actual readings must not "
            "be changed to obtain a model result; seek a clinical review instead.",
            "Class scores are uncalibrated classifier outputs, not the probability of disease. "
            "LOW does not rule out pre-eclampsia.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "forest.json").write_bytes(artifact_bytes)
    manifest_bytes = (
        json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()
    (output_dir / "manifest.json").write_bytes(manifest_bytes)
    fixtures = []
    for row, scores in zip(
        probes[:24],
        model.predict_proba(pd.DataFrame(probes[:24], columns=columns)),
        strict=True,
    ):
        fixtures.append(
            {
                "values": [None if np.isnan(v) else float(v) for v in row],
                "class_scores_in_original_order": scores.tolist(),
            }
        )
    (output_dir / "parity-fixtures.json").write_text(
        json.dumps(fixtures, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "artifact_sha256": manifest["artifact_sha256"],
                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "parity": manifest["parity"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "ml/artifacts/legacy_pe_v0.7.1"
    )
    args = parser.parse_args()
    export(args.repository_dir, args.output_dir)
