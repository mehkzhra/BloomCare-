"""Blood-pressure escalation guidance, explicitly separate from PE model predictions.

Reference: NICE NG133 recommendations and antenatal gestational-hypertension
visual summary (140/90 and 160/110 thresholds, either component). Same-day
contact wording is this application's conservative routing policy, not a diagnosis.
"""

import math


def blood_pressure_guidance(observations):
    systolic = observations.get("systolic_mmhg")
    diastolic = observations.get("diastolic_mmhg")
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        for value in (systolic, diastolic)
    ) or not (60 <= systolic <= 260 and 30 <= diastolic <= 180 and systolic > diastolic):
        return None
    if systolic >= 160 or diastolic >= 110:
        action = "IMMEDIATE_MATERNITY_REVIEW"
    elif systolic >= 140 or diastolic >= 90:
        action = "SAME_DAY_MATERNITY_CONTACT"
    else:
        return None  # Absence of a BP alert is not absence of PE.
    return {
        "action": action,
        "basis": "BLOOD_PRESSURE_GUIDANCE",
        "version": "bp-guidance-v1",
        "diagnosis": False,
        "source": "https://www.nice.org.uk/guidance/ng133/chapter/recommendations",
    }
