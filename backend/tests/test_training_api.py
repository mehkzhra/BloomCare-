import pytest
from conftest import sign_in

from app import training_api


@pytest.mark.parametrize("account", ["patient1", "doctor1"])
def test_training_evidence_is_admin_only(client, accounts, account):
    sign_in(client, account)
    assert client.get("/api/admin/training-evidence").status_code == 403


def test_admin_reads_the_executed_comparison_without_loading_candidate_artifacts(client, accounts):
    sign_in(client, "admin")
    result = client.get("/api/admin/training-evidence")
    assert result.status_code == 200, result.text
    evidence = result.json()
    assert len(evidence["candidates"]) == 3
    assert sum(row["configurations"] for row in evidence["candidates"]) == 85
    assert evidence["split"]["overlapping_groups"] == 0
    assert evidence["active_model_changed"] is False
    assert all(not row["gate"]["active_model_changed"] for row in evidence["candidates"])
    assert evidence["pe"]["usable_rows"] == 90 and evidence["pe"]["exact_duplicates_removed"] == 113
    assert '"trees":' not in result.text


def test_missing_training_files_produce_an_unavailable_state_not_invented_metrics(
    client, accounts, monkeypatch, tmp_path
):
    sign_in(client, "admin")
    monkeypatch.setattr(training_api, "REPORTS", tmp_path)
    response = client.get("/api/admin/training-evidence")
    assert response.status_code == 503 and "unavailable" in response.json()["detail"]
    assert "accuracy" not in response.json()
