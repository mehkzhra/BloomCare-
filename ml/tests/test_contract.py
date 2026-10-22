from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.data_contract import CLASS_ORDER, FEATURES, RAW_FEATURES, load_data, split_data


def write_csv(tmp_path: Path, rows):
    path = tmp_path / "fixture.csv"
    pd.DataFrame(rows, columns=RAW_FEATURES + ["RiskLevel"]).to_csv(path, index=False)
    return path


def test_convert_source_units_and_label(tmp_path):
    path = write_csv(tmp_path, [[25, 120, 80, 7, 98.6, 80, "mid risk"]])
    features, labels, _, audit = load_data(path)
    assert features.columns.tolist() == FEATURES
    assert features.iloc[0]["temperature_c"] == pytest.approx(37.0)
    assert features.iloc[0]["glucose_mmol_l"] == 7
    assert labels.tolist() == ["MEDIUM"]
    assert audit["usable_rows"] == 1


def test_duplicates_removed_and_conflicting_labels_kept_in_same_group(tmp_path):
    row = [25, 120, 80, 7, 98.6, 80]
    path = write_csv(tmp_path, [row + ["low risk"], row + ["low risk"], row + ["high risk"]])
    _, labels, groups, audit = load_data(path)
    assert len(labels) == 2
    assert groups.nunique() == 1
    assert audit["exact_duplicate_rows_removed"] == 1
    assert audit["groups_with_conflicting_labels_retained"] == 1


def test_excluded_rows_are_counted_without_inventing_replacements(tmp_path):
    path = write_csv(
        tmp_path,
        [
            [25, 120, 80, 7, 98.6, 80, "low risk"],
            [25, 120, 80, 7, 98.6, 7, "high risk"],
            [25, 80, 90, 7, 98.6, 80, "mid risk"],
        ],
    )
    features, _, _, audit = load_data(path)
    assert len(features) == 1
    assert audit["excluded_unique_rows"] == 2
    assert audit["exclusion_counts_may_overlap"]["heart_rate_bpm"] == 1
    assert audit["exclusion_counts_may_overlap"]["blood_pressure_order"] == 1


def test_unknown_label_fails_instead_of_becoming_low(tmp_path):
    path = write_csv(tmp_path, [[25, 120, 80, 7, 98.6, 80, "unknown"]])
    with pytest.raises(ValueError, match="unrecognized"):
        load_data(path)


def test_nonfinite_feature_fails_instead_of_silent_imputation(tmp_path):
    path = write_csv(tmp_path, [[25, 120, 80, np.inf, 98.6, 80, "low risk"]])
    with pytest.raises(ValueError, match="non-finite"):
        load_data(path)


def test_group_split_keeps_repeated_measurements_together():
    # Deliberately keep multiple rows per measurement group to expose leakage.
    groups = pd.Series(np.repeat(np.arange(90), 2).astype(str))
    labels = pd.Series(np.repeat([CLASS_ORDER[index % 3] for index in range(90)], 2))
    features = pd.DataFrame({"measurement": np.repeat(np.arange(90), 2)})
    train, held_out = split_data(features, labels, groups)
    assert set(groups.iloc[train]).isdisjoint(groups.iloc[held_out])
    assert set(train).isdisjoint(held_out)
    assert len(train) + len(held_out) == len(features)
    assert set(labels.iloc[train]) == set(CLASS_ORDER)
    assert set(labels.iloc[held_out]) == set(CLASS_ORDER)


def test_split_refuses_a_missing_class():
    features = pd.DataFrame({"measurement": range(30)})
    labels = pd.Series(["LOW"] * 30)
    groups = pd.Series([str(index) for index in range(30)])
    with pytest.raises(ValueError, match="three|LOW"):
        split_data(features, labels, groups)
