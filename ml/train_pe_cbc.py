"""Train an isolated CBC/PE candidate on a pinned CC-BY dataset; never promote it."""

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SHA256 = "ae382883f33166be157fafb36c5aab75217bbf9e5746bb7bae73f38bb33d6092"
FEATURES = ["WBC", "RBC", "Neutrophils", "Lymphocytes", "Monocytes", "Platelets"]
SOURCE = "https://data.mendeley.com/datasets/j7d8cdndpw/1"


def read_workbook(path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA256:
        raise ValueError("Dataset checksum mismatch")
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        strings = ["".join(node.itertext()) for node in ET.fromstring(
            archive.read("xl/sharedStrings.xml")
        ).findall("s:si", ns)]
        rows = []
        for row in ET.fromstring(archive.read("xl/worksheets/sheet1.xml")).findall(
            ".//s:row", ns
        ):
            values = {}
            for cell in row.findall("s:c", ns):
                text = cell.findtext("s:v", default=None, namespaces=ns)
                if cell.get("t") == "s" and text is not None:
                    text = strings[int(text)]
                values["".join(c for c in cell.get("r") if c.isalpha())] = text
            rows.append(values)
    header = rows[0]
    frame = pd.DataFrame([{name: row.get(col) for col, name in header.items()}
                          for row in rows[1:]])
    if list(frame.columns) != ["Serial", "Status", *FEATURES]:
        raise ValueError("Unexpected dataset columns")
    return frame


def scores(y, probability):
    tn, fp, fn, tp = confusion_matrix(y, probability >= .5, labels=[0, 1]).ravel()
    return {
        "auroc": float(roc_auc_score(y, probability)),
        "average_precision": float(average_precision_score(y, probability)),
        "brier_score": float(brier_score_loss(y, probability)),
        "sensitivity_at_fixed_0_5": float(tp / (tp + fn)),
        "specificity_at_fixed_0_5": float(tn / (tn + fp)),
        "confusion_matrix_actual_rows": [[int(tn), int(fp)], [int(fn), int(tp)]],
    }


def train(source, output):
    frame = read_workbook(source)
    x = frame[FEATURES].apply(pd.to_numeric, errors="raise").astype(float)
    y = frame.Status.map({"Controls": 0, "Patients": 1})
    if y.isna().any() or np.isinf(x.to_numpy()).any() or (x < 0).any().any():
        raise ValueError("Unexpected labels or invalid numeric data")
    if x.isna().all(axis=1).any() or frame.Serial.duplicated().any():
        raise ValueError("Unusable rows or duplicate source identifiers")
    groups = x.apply(lambda row: hashlib.sha256(json.dumps(
        [None if pd.isna(v) else float(v) for v in row]
    ).encode()).hexdigest(), axis=1)
    # Fix split and model before inspecting held-out performance; never tune on the test fold.
    development, heldout = next(StratifiedGroupKFold(
        n_splits=5, shuffle=True, random_state=20261029
    ).split(x, y, groups))
    if set(groups.iloc[development]) & set(groups.iloc[heldout]):
        raise ValueError("Overlapping measurement groups")
    model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                          LogisticRegression(C=1.0, max_iter=2000, random_state=20261029))
    model.fit(x.iloc[development], y.iloc[development])
    probability = model.predict_proba(x.iloc[heldout])[:, 1]
    y_test = y.iloc[heldout].to_numpy()
    rng = np.random.default_rng(20261029)
    aucs = []
    for _ in range(2000):
        ids = rng.integers(0, len(heldout), len(heldout))
        if len(np.unique(y_test[ids])) == 2:
            aucs.append(roc_auc_score(y_test[ids], probability[ids]))
    report = {
        "source": SOURCE, "doi": "10.17632/j7d8cdndpw.1",
        "attribution": "Wassim Almawi (2025), Preeclampsia Hematological Indices, V1",
        "license": "CC BY 4.0", "source_sha256": SHA256,
        "sklearn_version": sklearn.__version__,
        "task": "Retrospective PE/control classification using CBC source values",
        "source_rows": len(frame), "control_rows": int((y == 0).sum()),
        "pe_rows": int((y == 1).sum()), "features": FEATURES,
        "missing_values": {c: int(x[c].isna().sum()) for c in FEATURES},
        "unique_measurement_groups": int(groups.nunique()),
        "training_rows": len(development), "heldout_rows": len(heldout),
        "heldout_positive_rows": int(y_test.sum()), "overlapping_groups": 0,
        "split_seed": 20261029, "threshold": 0.5,
        "preprocessing": "Median imputation and standardisation fitted on development rows only",
        "heldout_metrics": scores(y_test, probability),
        "heldout_auroc_bootstrap_95_percent_interval": np.quantile(aucs, [.025, .975]).tolist(),
        "constant_training_prevalence_baseline": scores(
            y_test, np.full(len(heldout), float(y.iloc[development].mean()))
        ),
        "active": False, "clinical_validation": "NOT_ESTABLISHED",
        "deployment_blockers": [
            "CBC units and assay conventions are undocumented in retrieved workbook/metadata.",
            "Measurement timing and PE adjudication criteria need confirmation.",
            "No gestational age or BP columns: this does not repair current model BP coverage.",
            "Case-control sampling cannot supply calibrated real-world disease probabilities.",
            "No external cohort or patient-identity linkage verifies clinical generalisation.",
            "Two-class labels cannot justify fabricated LOW/MEDIUM/HIGH PE categories.",
        ],
    }
    imputer, scaler, classifier = model.steps[0][1], model.steps[1][1], model.steps[2][1]
    artifact = {
        "schema": "offline-cbc-logistic-candidate-v1", "active": False,
        "clinical_use": False, "features": FEATURES, "classes": classifier.classes_.tolist(),
        "median": imputer.statistics_.tolist(), "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(), "coefficients": classifier.coef_[0].tolist(),
        "intercept": float(classifier.intercept_[0]), "source_sha256": SHA256,
        "training_rows": len(development),
    }
    # Verify the non-executable JSON representation reproduces held-out pipeline scores.
    z = x.iloc[heldout].to_numpy().copy()
    z = np.where(np.isnan(z), np.array(artifact["median"]), z)
    logits = ((z - artifact["mean"]) / artifact["scale"]) @ artifact["coefficients"]
    exported = 1 / (1 + np.exp(-(logits + artifact["intercept"])))
    if not np.allclose(exported, probability, atol=1e-12, rtol=0):
        raise ValueError("Candidate export parity failed")
    report["json_export_parity_passed"] = True
    output.mkdir(parents=True, exist_ok=False)
    for name, content in [("report.json", report), ("candidate.json", artifact)]:
        (output / name).write_text(json.dumps(content, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report["heldout_metrics"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    train(args.source, args.output)
