"""Map the independently downloaded UCI data into BloomCare's explicit units."""

import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

RAW_FEATURES = ["Age", "SystolicBP", "DiastolicBP", "BS", "BodyTemp", "HeartRate"]
FEATURES = [
    "age_years",
    "systolic_mmhg",
    "diastolic_mmhg",
    "glucose_mmol_l",
    "temperature_c",
    "heart_rate_bpm",
]
LABEL_MAP = {"low risk": "LOW", "mid risk": "MEDIUM", "high risk": "HIGH"}
CLASS_ORDER = ["LOW", "MEDIUM", "HIGH"]
UNITS = ["years", "mmHg", "mmHg", "mmol/L", "degrees Celsius", "beats/minute"]
# Match the existing observation contract. These are input bounds, not normal ranges.
BOUNDS = [(10, 65), (60, 260), (30, 180), (1, 40), (32, 43), (30, 220)]


def feature_group(values) -> str:
    payload = json.dumps([float(value) for value in values], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_data(path: Path):
    source_bytes = path.read_bytes()
    raw = pd.read_csv(path)
    if set(raw.columns) != set(RAW_FEATURES + ["RiskLevel"]):
        raise ValueError("The source CSV columns do not match the verified UCI dataset")
    normalized_labels = raw["RiskLevel"].astype(str).str.strip().str.lower()
    if not normalized_labels.isin(LABEL_MAP).all():
        raise ValueError("Source contains a missing or unrecognized risk label")
    features = raw[RAW_FEATURES].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(features.to_numpy(dtype=float)).all():
        raise ValueError("Source contains missing or non-finite feature values")
    features.columns = FEATURES
    features["temperature_c"] = (features["temperature_c"] - 32.0) * 5.0 / 9.0
    labels = normalized_labels.map(LABEL_MAP)
    all_data = features.assign(risk=labels)
    duplicate_count = int(all_data.duplicated().sum())
    unique = all_data.drop_duplicates().reset_index(drop=True)
    valid = pd.Series(True, index=unique.index)
    exclusion_counts = {}
    for feature, (minimum, maximum) in zip(FEATURES, BOUNDS, strict=True):
        out_of_bounds = ~unique[feature].between(minimum, maximum)
        exclusion_counts[feature] = int(out_of_bounds.sum())
        valid &= ~out_of_bounds
    wrong_bp_order = unique["diastolic_mmhg"] >= unique["systolic_mmhg"]
    exclusion_counts["blood_pressure_order"] = int(wrong_bp_order.sum())
    valid &= ~wrong_bp_order
    clean = unique.loc[valid].reset_index(drop=True)
    groups = clean[FEATURES].apply(lambda row: feature_group(row), axis=1)
    conflict_count = int((clean.assign(group=groups).groupby("group")["risk"].nunique() > 1).sum())
    audit = {
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "downloaded_rows": len(raw),
        "raw_class_counts": dict(Counter(labels)),
        "exact_duplicate_rows_removed": duplicate_count,
        "unique_rows_before_input_bounds": len(unique),
        "excluded_unique_rows": int((~valid).sum()),
        "exclusion_counts_may_overlap": exclusion_counts,
        "usable_rows": len(clean),
        "usable_class_counts": dict(Counter(clean["risk"])),
        "unique_measurement_groups": int(groups.nunique()),
        "groups_with_conflicting_labels_retained": conflict_count,
        "unit_conversion": "BodyTemp: Fahrenheit to Celsius; (F - 32) * 5 / 9",
        "feature_bounds": dict(zip(FEATURES, BOUNDS, strict=True)),
        "cleaning_policy": (
            "Remove exact duplicate feature-label rows; exclude records incompatible "
            "with the current input contract; retain conflicting labels in one group"
        ),
    }
    return clean[FEATURES], clean["risk"], groups, audit


def split_data(features, labels, groups, seed=20261010):
    if len(set(labels)) != 3:
        raise ValueError("Training data must contain LOW, MEDIUM, and HIGH labels")
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    train, held_out = next(splitter.split(features, labels, groups))
    if set(groups.iloc[train]) & set(groups.iloc[held_out]):
        raise RuntimeError("Identical measurement groups crossed the evaluation boundary")
    if set(labels.iloc[train]) != set(CLASS_ORDER) or set(labels.iloc[held_out]) != set(
        CLASS_ORDER
    ):
        raise ValueError("The fixed split does not contain all classes on both sides")
    return train, held_out
