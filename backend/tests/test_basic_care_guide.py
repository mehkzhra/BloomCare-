import pytest

from app.basic_care_guide import basic_care_guide


@pytest.mark.parametrize(
    "systolic,diastolic,expected",
    [
        (160, 80, "immediately"),
        (120, 110, "immediately"),
        (140, 80, "today"),
        (120, 90, "today"),
        (120, 80, "does not rule out"),
    ],
)
def test_saved_bp_guidance_survives_low_or_unavailable_model(systolic, diastolic, expected):
    content = basic_care_guide(
        {
            "observations": {"systolic_mmhg": systolic, "diastolic_mmhg": diastolic},
            "maternal_category": "LOW",
            "pe_status": "UNSUPPORTED",
        },
        "en",
    )
    assert expected in content
    assert "not a negative result" in content
    assert "AI personalization unavailable" in content


def test_urdu_and_missing_measurements_do_not_fabricate_diagnosis():
    content = basic_care_guide({}, "ur")
    assert "تشخیص یا نسخہ نہیں" in content
    assert "NICE NG133" in content
    assert "شدید حد میں تھا" not in content
