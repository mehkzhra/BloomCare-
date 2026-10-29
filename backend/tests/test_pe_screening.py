"""Exercise the actual imported PE trees, ownership, persistence, and failure paths."""

import json
import shutil
from datetime import datetime, timedelta, timezone

import pytest
from conftest import sign_in
from ml.data_contract import load_data
from sqlalchemy import func, select
from test_assessments import (  # noqa: F401
    SOURCE,
    run_assessment,
    saved_record,
)
from test_assessments import (
    available as maternal_available,
)
from test_assessments import (
    trained as maternal_trained,
)

from app import pe_model
from app.database import SessionLocal
from app.models import Assessment, PEScreening
from app.pe_contract import BASE_FIELDS, input_contract

# Reuse the real maternal-model fixtures, preserving their pytest discovery names.
available = maternal_available
trained = maternal_trained

PE_VALUES = {
    "gravida": 2,
    "parity": 1,
    "bmi": 24.5,
    "diabetes": False,
    "history_of_hypertension": False,
    "hb": 10.5,
    "fetal_weight_kg": 1.2,
    "protein_uria": False,
    "amniotic_fluid_level_cm": 12.0,
}


@pytest.fixture(scope="session")
def pe_examples(trained):
    model = trained[2]
    features, _, _, _ = load_data(SOURCE)
    mask = features.index.to_series().notna()
    for name, (minimum, maximum) in model.manifest["observed_training_ranges"].items():
        mask &= features[name].between(minimum, maximum)
    for field in input_contract():
        if field["name"] in features:
            mask &= features[field["name"]].between(field["minimum"], field["maximum"])
    features = features.loc[mask]
    labels = model.pipeline.predict(features)
    examples = {}
    for risk in ["LOW", "MEDIUM", "HIGH"]:
        candidate = features.loc[labels == risk].iloc[0].to_dict()
        for key in ["age_years", "systolic_mmhg", "diastolic_mmhg", "heart_rate_bpm"]:
            candidate[key] = int(candidate[key])
        examples[risk] = {**candidate, "gestational_weeks": 24.0}
    return examples


def create_assessment(client, examples, risk="MEDIUM"):
    record = saved_record(client, examples[risk])
    response = run_assessment(client, record)
    assert response.status_code == 200, response.text
    return record, response.json()


def test_original_tree_conversion_matches_reference_scores():
    model = pe_model.get_pe_model()
    fixtures = json.loads((pe_model.MODEL_DIR / "parity-fixtures.json").read_text())
    for fixture in fixtures:
        scores = pe_model.forest_scores(model.artifact, fixture["values"])
        assert scores == pytest.approx(fixture["class_scores_in_original_order"], abs=1e-12)
    assert model.manifest["parity"]["split_boundary_rows"] == 14928
    assert model.manifest["evaluation"]["test_rows_matching_training_inputs"] == 25
    assert model.manifest["evaluation"]["independent_validation"] is False


@pytest.mark.parametrize("risk", ["MEDIUM", "HIGH"])
def test_real_pe_inference_is_attached_and_retry_safe(
    client, accounts, available, pe_examples, risk
):
    sign_in(client)
    record, maternal = create_assessment(client, pe_examples, risk)
    assert maternal["pe_status"] == "AWAITING_INPUTS"
    path = f"/api/patients/me/assessments/{maternal['id']}/pe"
    response = client.post(path, json=PE_VALUES)
    assert response.status_code == 200, response.text
    result = response.json()
    pe = result["pe_screening"]
    observations = {name: maternal["observations"][name] for name in BASE_FIELDS} | PE_VALUES
    expected = pe_model.get_pe_model().infer(observations)
    assert pe["observations"] == observations
    assert pe["risk"] == expected["risk"]
    assert pe["class_scores"] == expected["class_scores"]
    assert pe["model"]["artifact_sha256"] == pe_model.ARTIFACT_SHA256
    assert result["pe_status"] == "COMPLETED"
    for name in ["id", "observations", "maternal_risk", "explanation", "class_scores", "model"]:
        assert result[name] == maternal[name]
    assert client.post(path, json=PE_VALUES).json() == result
    assert client.post(path).json() == result
    assert client.post(path, json={**PE_VALUES, "bmi": 25.0}).status_code == 409
    assert client.get(f"/api/patients/me/assessments/{maternal['id']}").json() == result
    assert client.get(f"/api/patients/me/health-records/{record['id']}/assessments").json() == [
        result
    ]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(PEScreening)) == 1


def test_low_gate_ownership_and_roles(client, accounts, available, pe_examples):
    sign_in(client)
    _, low = create_assessment(client, pe_examples, "LOW")
    _, medium = create_assessment(client, pe_examples)
    assert (
        client.post(f"/api/patients/me/assessments/{low['id']}/pe", json=PE_VALUES).status_code
        == 400
    )
    path = f"/api/patients/me/assessments/{medium['id']}/pe"
    sign_in(client, "patient2")
    assert client.post(path, json=PE_VALUES).status_code == 404
    for account in ["doctor1", "admin"]:
        sign_in(client, account)
        assert client.post(path, json=PE_VALUES).status_code == 403
    client.post("/api/auth/logout")
    assert client.post(path, json=PE_VALUES).status_code == 401


@pytest.mark.parametrize(
    "patch",
    [
        {"age_years": 25},
        {"systolic_mmhg": 120},
        {"risk": "LOW"},
        {"uterine_artery_ri": 0.5},
        {"diabetes": "false"},
        {"protein_uria": 0},
        {"bmi": 50},
        {"hb": 7},
        {"parity": 2},
        {"gravida": 1.5},
    ],
)
def test_clients_cannot_override_base_fields_or_submit_invalid_measurements(
    client, accounts, available, pe_examples, patch
):
    sign_in(client)
    _, maternal = create_assessment(client, pe_examples)
    response = client.post(
        f"/api/patients/me/assessments/{maternal['id']}/pe", json=PE_VALUES | patch
    )
    assert response.status_code == 422
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(PEScreening)) == 0


def test_actual_saved_out_of_range_base_values_are_not_clamped(
    client, accounts, available, pe_examples
):
    sign_in(client)
    record = saved_record(client, pe_examples["MEDIUM"] | {"gestational_weeks": 10})
    result = run_assessment(client, record).json()
    response = client.post(f"/api/patients/me/assessments/{result['id']}/pe", json=PE_VALUES)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "PE_INPUT_OUTSIDE_RANGE"
    assert detail["fields"][0]["feature"] == "gestational_weeks"
    assert client.get(f"/api/patients/me/assessments/{result['id']}").json()["pe_screening"] is None
    with SessionLocal() as db:
        assert db.get(Assessment, result["id"]).observations_snapshot["gestational_weeks"] == 10


def test_model_failure_never_generates_a_rule_based_result(
    client, accounts, available, pe_examples, monkeypatch
):
    sign_in(client)
    _, maternal = create_assessment(client, pe_examples)

    def unavailable(_directory):
        raise pe_model.PEModelUnavailable("Test missing PE artifact")

    pe_model.get_pe_model.cache_clear()
    monkeypatch.setattr(pe_model, "load_pe_model", unavailable)
    try:
        assert client.get("/api/capabilities").json()["pe_model_ready"] is False
        response = client.post(f"/api/patients/me/assessments/{maternal['id']}/pe", json=PE_VALUES)
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "PE_MODEL_UNAVAILABLE"
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(PEScreening)) == 0
    finally:
        pe_model.get_pe_model.cache_clear()


def test_saved_pe_result_remains_readable_and_doctor_access_follows_shared_record(
    client, accounts, available, pe_examples, monkeypatch
):
    sign_in(client)
    record, maternal = create_assessment(client, pe_examples)
    result = client.post(f"/api/patients/me/assessments/{maternal['id']}/pe", json=PE_VALUES).json()
    scheduled = (datetime.now(timezone.utc) + timedelta(days=2)).replace(
        minute=0, second=0, microsecond=0
    )
    booking = client.post(
        "/api/patients/me/appointments",
        json={
            "doctor_id": accounts["doctor1"],
            "scheduled_at": scheduled.isoformat(),
            "reason": "Review PE screening",
            "share_profile": True,
            "health_record_ids": [record["id"]],
        },
    ).json()
    base = f"/api/doctors/me/appointments/{booking['id']}"
    path = f"{base}/records/{record['id']}/assessments"
    sign_in(client, "doctor1")
    assert client.get(path).status_code == 403
    assert client.post(base + "/decision", json={"action": "ACCEPT"}).status_code == 200
    assert client.get(path).json() == [result]
    pe_model.get_pe_model.cache_clear()
    monkeypatch.setattr(pe_model, "MODEL_DIR", pe_model.MODEL_DIR / "missing")
    try:
        assert client.get(path).json() == [result]
        sign_in(client, "patient2")
        assert client.get(f"/api/patients/me/assessments/{maternal['id']}").status_code == 404
        sign_in(client)
        assert client.get(f"/api/patients/me/assessments/{maternal['id']}").json() == result
        client.post(f"/api/patients/me/appointments/{booking['id']}/cancel")
        sign_in(client, "doctor1")
        assert client.get(path).status_code == 403
    finally:
        pe_model.get_pe_model.cache_clear()


def test_capabilities_match_real_inputs_without_unused_doppler_columns(client, accounts):
    sign_in(client)
    capabilities = client.get("/api/capabilities").json()
    assert capabilities["pe_model_ready"] is True
    assert capabilities["pe_input_fields"] == input_contract()
    assert len(capabilities["pe_input_fields"]) == 13
    assert all("uterine" not in item["name"] for item in capabilities["pe_input_fields"])


@pytest.mark.parametrize(
    ("weeks", "risk", "warning", "expected"),
    [
        (12, "LOW", False, "NOT_INDICATED"),
        (12, "LOW", True, "OUTSIDE_COVERAGE"),
        (12, "MEDIUM", False, "OUTSIDE_COVERAGE"),
        (12, "HIGH", False, "OUTSIDE_COVERAGE"),
        (14, "HIGH", False, "COMPLETED"),
        (40, "HIGH", False, "COMPLETED"),
        (45, "HIGH", False, "OUTSIDE_COVERAGE"),
    ],
)
def test_pregnancy_duration_preserves_measurements_and_never_forces_a_pe_category(
    client, accounts, available, pe_examples, weeks, risk, warning, expected
):
    sign_in(client)
    observations = {**pe_examples[risk], "gestational_weeks": weeks}
    body = {
        **observations,
        "clinical_indicators": {**PE_VALUES, "history_of_hypertension": warning},
    }
    response = client.post("/api/patients/me/complete-assessment", json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["observations"] == observations
    assert result["maternal_risk"] == risk
    assert result["pe_status"] == expected
    assert result["class_scores"] == available[0].infer(pe_examples[risk])["class_scores"]
    source = client.get(f"/api/patients/me/health-records/{result['health_record_id']}")
    assert source.json()["observations"]["gestational_weeks"] == weeks
    if expected == "OUTSIDE_COVERAGE":
        assert result["pe_screening"] is None
        assert "14–40-week" in result["pe_reason"]
        assert any(
            field["name"] == "gestational_weeks" and field["value"] == weeks
            for field in result["pe_input_issues"]
        )
        attempted = client.post(
            f"/api/patients/me/assessments/{result['id']}/pe", json=PE_VALUES
        )
        assert attempted.status_code == 422
        assert attempted.json()["detail"]["code"] == "PE_INPUT_OUTSIDE_RANGE"
    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(PEScreening))
        assert count == (1 if expected == "COMPLETED" else 0)


@pytest.mark.parametrize("filename", ["forest.json", "manifest.json"])
def test_tampered_pe_json_is_rejected_before_parsing(tmp_path, monkeypatch, filename):
    directory = tmp_path / "model"
    shutil.copytree(pe_model.MODEL_DIR, directory)
    file = directory / filename
    file.write_bytes(file.read_bytes() + b"tampered")
    monkeypatch.setattr(pe_model.json, "loads", lambda *_args: pytest.fail("Untrusted JSON parsed"))
    with pytest.raises(pe_model.PEModelUnavailable):
        pe_model.load_pe_model(directory)
