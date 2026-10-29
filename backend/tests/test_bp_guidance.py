import pytest
from conftest import sign_in
from test_appointments import HEALTH

from app.bp_guidance import blood_pressure_guidance


@pytest.mark.parametrize("systolic,diastolic,action", [
    (139, 89, None), (140, 80, "SAME_DAY_MATERNITY_CONTACT"),
    (120, 90, "SAME_DAY_MATERNITY_CONTACT"), (140, 100, "SAME_DAY_MATERNITY_CONTACT"),
    (159, 109, "SAME_DAY_MATERNITY_CONTACT"), (160, 80, "IMMEDIATE_MATERNITY_REVIEW"),
    (150, 110, "IMMEDIATE_MATERNITY_REVIEW"), (260, 180, "IMMEDIATE_MATERNITY_REVIEW"),
])
def test_either_bp_component_triggers_guidance_without_pe_diagnosis(systolic, diastolic, action):
    values = {"systolic_mmhg": systolic, "diastolic_mmhg": diastolic, "gestational_weeks": 12}
    result = blood_pressure_guidance(values)
    assert (result["action"] if result else None) == action
    if result:
        assert result["diagnosis"] is False
        assert "risk" not in result
    assert values["systolic_mmhg"] == systolic


@pytest.mark.parametrize("value", [None, True, float("nan"), float("inf"), "160", 261])
def test_invalid_values_do_not_generate_guidance(value):
    assert blood_pressure_guidance({"systolic_mmhg": value, "diastolic_mmhg": 80}) is None


def test_high_bp_stays_saved_with_guidance_even_when_model_unavailable(client, accounts):
    # The test environment disables experimental inference by default.
    sign_in(client)
    response = client.post("/api/patients/me/complete-assessment", json={
        **HEALTH, "systolic_mmhg": 170, "diastolic_mmhg": 110, "gestational_weeks": 12,
    })
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["blood_pressure_guidance"]["action"] == "IMMEDIATE_MATERNITY_REVIEW"
    saved = client.get("/api/patients/me/health-records/" + detail["health_record_id"])
    assert saved.status_code == 200
    assert saved.json()["observations"]["systolic_mmhg"] == 170
    assert saved.json()["observations"]["diastolic_mmhg"] == 110
