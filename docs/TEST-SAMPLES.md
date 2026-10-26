# BloomCare software test samples

Synthetic demonstration inputs, not treatment targets or medical advice. Use separate records and the existing registered maternal model. Supported ranges describe training coverage, not clinical normality.

## Maternal categories

Use a new health record for each category. Leave optional antenatal values unknown. Select glucose **mg/dL** and temperature **°F**.

| Field | Expected LOW | Expected MEDIUM | Expected HIGH |
| --- | --- | --- | --- |
| Age (years) | 35 | 29 | 30 |
| Pregnancy duration (weeks) | 28 | 28 | 28 |
| Systolic / diastolic BP (mmHg) | 100 / 70 | 130 / 70 | 140 / 100 |
| Glucose (mg/dL) | 138.6 | 142.2 | 270 |
| Alternative glucose (mmol/L) | 7.7 | 7.9 | 15 |
| Temperature (°F) | 98 | 98 | 98 |
| Heart rate (beats/minute) | 66 | 78 | 70 |

Verified on 26 October 2026 against the available local cloud-build `maternal_rf_v0.2` artifact, including its real SHAP inference. The deployed model was not queried. These maternal-only records do not promise completed PE screening.

[Download/read the maternal examples](examples/BloomCare-Health-Record-Samples.txt).

## PE categories

Common core record for all three: age **25**, duration **24 weeks**, BP **120/80**, glucose **162 mg/dL** (9 mmol/L), temperature **98.6°F** (37°C), heart rate **80**. The expected maternal category is HIGH. Enter all additional measurements below to test the separate PE stage.

| Additional field | Expected PE LOW | Expected PE MEDIUM | Expected PE HIGH |
| --- | --- | --- | --- |
| Pregnancies / previous births | 2 / 1 | 2 / 1 | 4 / 2 |
| BMI | 24.5 | 35 | 28 |
| Diagnosed diabetes | No | Yes | Yes |
| History of hypertension | No | Yes | Yes |
| HB on the original source scale | 10.5 | 8.5 | 10 |
| Estimated fetal weight, kg | 1.2 | 1.2 | 1.5 |
| Protein in urine | No | Yes | Yes |
| Amniotic fluid measurement, cm | 12 | 12 | 5 |

[Download/read full PE records](examples/BloomCare-PE-Test-Samples.txt). All three cases were verified on 26 October 2026 with maternal HIGH and PE LOW/MEDIUM/HIGH respectively using the local cloud-build artifacts. PE status is expected to be `COMPLETED` when all inputs are submitted through the full workflow.

HB's clinical unit was not documented in the original source. Do not infer a unit or use this table to choose real clinical inputs. The active imported PE forest is unchanged by retraining.

## Duration and correction checks

1. Use a supported maternal sample and change only pregnancy duration to **12**. The saved value must stay 12 and the maternal category/scores must stay the same. For MEDIUM/HIGH, PE shows its **14–40-week** coverage and no PE category.
2. A LOW record without recorded PE triggers remains `NOT_INDICATED`; LOW with a recorded hypertension/proteinuria trigger still opens PE and cannot generate a category at 12 weeks.
3. **14** and **40** are inclusive PE duration bounds when every other value is supported; **45** can be saved but is outside PE coverage. The automated duration tests exercised these paths with real fitted/imported models.
4. In Health history, delete an incorrect record with a reason. It and linked assessments disappear from active views; original audit information/notes remain. Add a corrected record.
5. Use separate patient/doctor accounts to check that unselected, expired, revoked and removed records cannot be read through a consultation.

For uploads, use a small valid PDF, PNG or JPEG. Maximum is 5 MB per file, 50 MB total and 100 reports per patient. An uploaded report's successful download and sharing still need a destination browser check.
