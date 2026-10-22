"""The original PE forest's exact column order and supported numeric ranges."""

VERSION = "bloomcare_legacy_pe_v0.7.1"
SOURCE_COMMIT = "e7bce42d00a7c5813964a6b2d6f1cd5142cab518"
# name, original column, label, unit, training minimum, training maximum
FEATURES = [
    ("gravida", "gravida", "Number of pregnancies", "", 1, 8),
    ("parity", "parity", "Number of previous births", "", 0, 6),
    ("gestational_weeks", "gestational age (weeks)", "Pregnancy duration", "weeks", 14, 40),
    ("age_years", "Age (yrs)", "Age", "years", 18, 38),
    ("bmi", "BMI  [kg/m²]", "BMI", "kg/m²", 16.4, 43.3),
    ("diabetes", "diabetes", "Diagnosed diabetes", "", 0, 1),
    (
        "history_of_hypertension",
        "History of hypertension (y/n)",
        "History of hypertension",
        "",
        0,
        1,
    ),
    ("systolic_mmhg", "Systolic BP", "Systolic blood pressure", "mmHg", 90, 130),
    ("diastolic_mmhg", "Diastolic BP", "Diastolic blood pressure", "mmHg", 20, 90),
    ("hb", "HB", "Haemoglobin (HB)", "", 8, 11.2),
    ("fetal_weight_kg", "fetal weight(kgs)", "Estimated fetal weight", "kg", 0.0001, 9.55),
    ("protein_uria", "Protien Uria", "Protein in urine", "", 0, 1),
    (
        "uterine_artery_ri",
        "Uterine Artery Doppler Resistance Index (RI)",
        "Uterine artery RI",
        "",
        None,
        None,
    ),
    (
        "uterine_artery_pi",
        " Uterine Artery Doppler Pulsatility Index (PI",
        "Uterine artery PI",
        "",
        None,
        None,
    ),
    (
        "amniotic_fluid_level_cm",
        "amniotic fluid levels(cm)",
        "Amniotic fluid measurement",
        "cm",
        4.79,
        18,
    ),
]
UNUSED_INDICES = {12, 13}
CLASS_ORDER = ["HIGH", "LOW", "MEDIUM"]
BASE_FIELDS = {"age_years", "gestational_weeks", "systolic_mmhg", "diastolic_mmhg"}
BOOLEAN_FIELDS = {"diabetes", "history_of_hypertension", "protein_uria"}


def input_contract():
    return [
        {
            "name": name,
            "label": label,
            "unit": unit,
            "minimum": minimum,
            "maximum": maximum,
            "from_record": name in BASE_FIELDS,
            "kind": "boolean"
            if name in BOOLEAN_FIELDS
            else "integer"
            if name in {"gravida", "parity", "age_years", "systolic_mmhg", "diastolic_mmhg"}
            else "number",
        }
        for index, (name, _column, label, unit, minimum, maximum) in enumerate(FEATURES)
        if index not in UNUSED_INDICES
    ]
