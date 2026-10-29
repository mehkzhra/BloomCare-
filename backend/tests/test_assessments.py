"""Exercise the actual independently trained classifier, never a rule-based substitute."""

import hashlib
import json
import shutil
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest
from conftest import sign_in
from ml.data_contract import load_data
from ml.train_maternal import train
from sqlalchemy import func, select

from app import maternal_model
from app.config import get_settings
from app.database import SessionLocal
from app.models import Assessment, ModelVersion

SOURCE = Path(__file__).parent / "fixtures" / "maternal_risk_uci.csv"


def test_doctor_reads_real_saved_assessment_only_during_shared_episode(
    client, accounts, available, monkeypatch
):
    _, examples = available
    sign_in(client)
    shared = saved_record(client, examples["HIGH"])
    unshared = saved_record(client, examples["LOW"])
    result = run_assessment(client, shared).json()
    requested = (datetime.now(timezone.utc) + timedelta(days=2)).replace(
        minute=0, second=0, microsecond=0
    )
    booking = client.post(
        "/api/patients/me/appointments",
        json={
            "doctor_id": accounts["doctor1"],
            "scheduled_at": requested.isoformat(),
            "reason": "Review actual saved research result",
            "share_profile": True,
            "health_record_ids": [shared["id"]],
        },
    )
    assert booking.status_code == 201
    appointment_id = booking.json()["id"]
    base = f"/api/doctors/me/appointments/{appointment_id}"
    path = f"{base}/records/{shared['id']}/assessments"
    sign_in(client, "doctor1")
    assert client.get(path).status_code == 403
    assert client.post(base + "/decision", json={"action": "ACCEPT"}).status_code == 200
    assert client.get(path).json() == [result]
    assert client.get(f"{base}/records/{unshared['id']}/assessments").status_code == 404
    assert (
        client.post(
            "/api/patients/me/assessments", json={"health_record_id": shared["id"]}
        ).status_code
        == 403
    )
    monkeypatch.setattr(get_settings(), "bloomcare_research_assessments", False)
    assert client.get(path).json() == [result]
    assert result["pe_required"] is True and result["pe_status"] == "AWAITING_INPUTS"
    sign_in(client, "doctor2")
    assert client.get(path).status_code == 404
    sign_in(client)
    assert client.post(f"/api/patients/me/appointments/{appointment_id}/cancel").status_code == 200
    sign_in(client, "doctor1")
    assert client.get(path).status_code == 403


def write_trust(directory, destination):
    manifest = json.loads((directory / "manifest.json").read_text())
    trust = {
        "schema_version": 1,
        "mode": "research_only",
        "model_version": manifest["version"],
        "artifact_sha256": hashlib.sha256((directory / "pipeline.joblib").read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest(),
    }
    destination.write_text(json.dumps(trust), encoding="utf-8")


@pytest.fixture(scope="session")
def trained(tmp_path_factory):
    directory = tmp_path_factory.mktemp("independent-model") / "model"
    train(data_path=SOURCE, output_path=directory)
    trust = directory.parent / "trust.json"
    write_trust(directory, trust)
    model = maternal_model.load_registered_model(directory, trust)
    features, _, _, _ = load_data(SOURCE)
    within = np.ones(len(features), dtype=bool)
    for feature in maternal_model.FEATURES:
        minimum, maximum = model.manifest["observed_training_ranges"][feature]
        within &= features[feature].between(minimum, maximum).to_numpy()
    supported = features.loc[within]
    predictions = model.pipeline.predict(supported)
    examples = {}
    for risk in maternal_model.LABELS:
        matching = supported.loc[predictions == risk]
        assert len(matching), f"No supported public source example predicted {risk}"
        example = matching.iloc[0].to_dict()
        for name in ["age_years", "systolic_mmhg", "diastolic_mmhg", "heart_rate_bpm"]:
            example[name] = int(example[name])
        examples[risk] = {**example, "gestational_weeks": 24.0}
    return directory, trust, model, examples


@pytest.fixture
def available(trained, monkeypatch):
    directory, trust, model, examples = trained
    monkeypatch.setattr(get_settings(), "bloomcare_research_assessments", True)
    monkeypatch.setattr(maternal_model, "MODEL_DIR", directory)
    monkeypatch.setattr(maternal_model, "TRUST_PATH", trust)
    cache = maternal_model._cached_model
    cache.cache_clear()
    yield model, examples
    cache.cache_clear()


def saved_record(client, observations):
    response = client.post("/api/patients/me/health-records", json=observations)
    assert response.status_code == 201
    return response.json()


def run_assessment(client, record):
    return client.post("/api/patients/me/assessments", json={"health_record_id": record["id"]})


@pytest.mark.parametrize("risk", maternal_model.LABELS)
def test_real_model_output_explanation_persistence_and_pe_gate(client, accounts, available, risk):
    model, examples = available
    sign_in(client)
    record = saved_record(client, examples[risk])
    response = run_assessment(client, record)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["maternal_risk"] == risk
    expected = model.infer(examples[risk])
    assert result["class_scores"] == expected["class_scores"]
    assert result["explanation"]["explained_class"] == risk
    explanation = result["explanation"]
    assert explanation["base_score"] + sum(
        item["contribution"] for item in explanation["features"]
    ) == pytest.approx(result["class_scores"][risk], abs=1e-7)
    assert result["observations"] == examples[risk]
    assert result["research_only"] is True
    assert result["model"]["evaluation"]["accuracy"] == pytest.approx(0.7111111111)
    assert result["pe_required"] is (risk != "LOW")
    assert result["pe_status"] == ("NOT_INDICATED" if risk == "LOW" else "AWAITING_INPUTS")
    endpoint = "/api/patients/me/assessments/" + result["id"]
    assert client.get(endpoint).json() == result
    pe_response = client.post(endpoint + "/pe")
    assert pe_response.status_code == (400 if risk == "LOW" else 422)
    if risk != "LOW":
        assert pe_response.json()["detail"]["code"] == "PE_INPUT_REQUIRED"
    assert client.get("/api/patients/me/assessments").json()[0]["id"] == result["id"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Assessment)) == 1
        assert db.scalar(select(func.count()).select_from(ModelVersion)) == 1


def test_duplicate_requests_return_same_saved_assessment(client, accounts, available):
    _, examples = available
    sign_in(client)
    record = saved_record(client, examples["LOW"])
    first = run_assessment(client, record)
    second = run_assessment(client, record)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(client.get("/api/patients/me/assessments").json()) == 1


def test_patient_and_doctor_cannot_access_other_patients_assessments(client, accounts, available):
    _, examples = available
    sign_in(client)
    record = saved_record(client, examples["HIGH"])
    result = run_assessment(client, record).json()
    detail = "/api/patients/me/assessments/" + result["id"]
    linked = "/api/patients/me/health-records/" + record["id"] + "/assessments"
    sign_in(client, "patient2")
    assert client.get(detail).status_code == 404
    assert client.get(linked).status_code == 404
    assert client.post(detail + "/pe").status_code == 404
    assert run_assessment(client, record).status_code == 404
    assert client.get("/api/patients/me/assessments").json() == []
    sign_in(client, "doctor1")
    for path in [detail, linked, "/api/patients/me/assessments"]:
        assert client.get(path).status_code == 403
    assert run_assessment(client, record).status_code == 403
    sign_in(client, "admin")
    assert client.get(detail).status_code == 403
    assert client.get("/api/admin/model-evaluation").status_code == 200


def test_anonymous_assessment_endpoints_are_protected(client):
    assert client.get("/api/patients/me/assessments").status_code == 401
    assert (
        client.post(
            "/api/patients/me/assessments",
            json={
                "health_record_id": "00000000-0000-0000-0000-000000000000",
            },
        ).status_code
        == 401
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"glucose_mmol_l": 5.1},
        {"systolic_mmhg": 160},
        {"temperature_c": 36.0},
    ],
)
def test_unsupported_inputs_preserve_observations_without_saving_results(
    client,
    accounts,
    available,
    patch,
):
    _, examples = available
    sign_in(client)
    record = saved_record(client, {**examples["LOW"], **patch})
    result = run_assessment(client, record)
    assert result.status_code == 422
    assert result.json()["detail"]["code"] == "MODEL_INPUT_OUTSIDE_RANGE"
    assert len(result.json()["detail"]["fields"]) >= 1
    assert client.get("/api/patients/me/assessments").json() == []
    assert client.get("/api/patients/me/health-records/" + record["id"]).json() == record
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ModelVersion)) == 0


def test_client_cannot_select_patient_risk_or_pe_status(client, accounts, available):
    _, examples = available
    sign_in(client)
    record = saved_record(client, examples["LOW"])
    for patch in [
        {"patient_id": accounts["patient2"]},
        {"maternal_risk": "HIGH"},
        {"pe_required": True},
    ]:
        response = client.post(
            "/api/patients/me/assessments",
            json={
                "health_record_id": record["id"],
                **patch,
            },
        )
        assert response.status_code == 422
    assert client.get("/api/patients/me/assessments").json() == []


def test_history_is_readable_after_model_is_disabled(client, accounts, available, monkeypatch):
    _, examples = available
    sign_in(client)
    record = saved_record(client, examples["MEDIUM"])
    result = run_assessment(client, record).json()
    monkeypatch.setattr(get_settings(), "bloomcare_research_assessments", False)
    assert client.get("/api/capabilities").json()["pregnancy_model_ready"] is False
    assert client.get("/api/patients/me/assessments/" + result["id"]).json() == result
    assert run_assessment(client, record).status_code == 503


def test_tampered_artifact_is_rejected_before_deserialization(trained, tmp_path, monkeypatch):
    directory, trust, _, _ = trained
    copy = tmp_path / "model"
    shutil.copytree(directory, copy)
    artifact = copy / "pipeline.joblib"
    artifact.write_bytes(artifact.read_bytes() + b"tampered")
    import joblib

    monkeypatch.setattr(
        joblib, "load", lambda *_args: pytest.fail("Untrusted artifact was deserialized")
    )
    with pytest.raises(maternal_model.ModelUnavailable):
        maternal_model.load_registered_model(copy, trust)


def test_changed_feature_units_are_rejected_even_with_updated_local_hash(trained, tmp_path):
    directory, _, _, _ = trained
    copy = tmp_path / "model"
    shutil.copytree(directory, copy)
    manifest_path = copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["features"][3]["unit"] = "mg/dL"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    trust = tmp_path / "trust.json"
    write_trust(copy, trust)
    with pytest.raises(maternal_model.ModelUnavailable):
        maternal_model.load_registered_model(copy, trust)


def test_invalid_explanation_returns_unavailable_without_saving(
    client, accounts, available, monkeypatch
):
    model, examples = available
    sign_in(client)
    record = saved_record(client, examples["LOW"])

    def wrong_values(values):
        return np.zeros((len(values), 6, 3))

    monkeypatch.setattr(model.explainer, "shap_values", wrong_values)
    monkeypatch.setattr(maternal_model, "_cached_model", lambda: model)
    response = run_assessment(client, record)
    assert response.status_code == 503
    assert client.get("/api/patients/me/assessments").json() == []


def test_dependency_mismatch_disables_model(trained, tmp_path):
    directory, _, _, _ = trained
    copy = tmp_path / "model"
    shutil.copytree(directory, copy)
    manifest_path = copy / "manifest.json"
    manifest = deepcopy(json.loads(manifest_path.read_text()))
    manifest["dependencies"]["scikit-learn"] = "0.0.0"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    trust = tmp_path / "trust.json"
    write_trust(copy, trust)
    with pytest.raises(maternal_model.ModelUnavailable):
        maternal_model.load_registered_model(copy, trust)


def test_activation_preserves_credentials_and_model_files(trained, tmp_path):
    from scripts.enable_research_assessment import activate

    directory, _, _, _ = trained
    backend = tmp_path / "backend"
    backend.mkdir()
    source = tmp_path / "ml" / "data"
    source.mkdir(parents=True)
    shutil.copyfile(SOURCE, source / "maternal_risk_uci.csv")
    artifact = tmp_path / "ml" / "artifacts" / "maternal_rf_v0.2"
    shutil.copytree(directory, artifact)
    original_environment = "DATABASE_URL=unchanged-test-value\nJWT_SECRET=unchanged-test-value\n"
    (backend / ".env").write_text(original_environment, encoding="utf-8")
    original_model_hash = hashlib.sha256((artifact / "pipeline.joblib").read_bytes()).hexdigest()
    registry = activate(tmp_path)
    assert (
        backend / ".env"
    ).read_text() == original_environment + "BLOOMCARE_RESEARCH_ASSESSMENTS=true\n"
    assert registry["mode"] == "research_only"
    assert registry["artifact_sha256"] == original_model_hash
    assert (
        hashlib.sha256((artifact / "pipeline.joblib").read_bytes()).hexdigest()
        == original_model_hash
    )
    activate(tmp_path)
    assert (backend / ".env").read_text().count("BLOOMCARE_RESEARCH_ASSESSMENTS=") == 1


def test_failed_activation_does_not_change_configuration(trained, tmp_path):
    from scripts.enable_research_assessment import activate

    directory, _, _, _ = trained
    backend = tmp_path / "backend"
    backend.mkdir()
    source = tmp_path / "ml" / "data"
    source.mkdir(parents=True)
    shutil.copyfile(SOURCE, source / "maternal_risk_uci.csv")
    artifact = tmp_path / "ml" / "artifacts" / "maternal_rf_v0.2"
    shutil.copytree(directory, artifact)
    environment = "DATABASE_URL=keep\nJWT_SECRET=keep\nBLOOMCARE_RESEARCH_ASSESSMENTS=false\n"
    (backend / ".env").write_text(environment, encoding="utf-8")
    (artifact / "pipeline.joblib").write_bytes(b"corrupted")
    with pytest.raises(ValueError):
        activate(tmp_path)
    assert (backend / ".env").read_text() == environment
    assert not (backend / "model-trust.json").exists()
