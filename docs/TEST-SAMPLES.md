# BloomCare software test samples

Synthetic demonstration inputs, not treatment targets or medical advice. Use separate records and the existing registered maternal model. Supported ranges describe training coverage, not clinical normality.

## Maternal categories

Leave optional antenatal values unknown. Pregnancy duration **24 weeks**, temperature **98°F**, heart rate **76** except HIGH **86**.

| Field | Expected LOW | Expected MEDIUM | Expected HIGH |
| --- | --- | --- | --- |
| Age | 23 | 35 | 25 |
| Systolic / diastolic BP | 90 / 60 | 120 / 60 | 130 / 80 |
| Glucose in mg/dL | 126.18 | 109.8 | 270 |
| Equivalent glucose in mmol/L | 7.01 | 6.1 | 15 |

These were verified against the unchanged registered configuration in the earlier demonstration run; fresh training reproduced its fixed evaluation. They are not a claim about diagnosis.

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

HB's clinical unit was not documented in the original source. Do not infer a unit or use this table to choose real clinical inputs. The active imported PE forest is unchanged by retraining.

## Duration and correction checks

1. Use a supported maternal sample and change only pregnancy duration to **12**. The saved value must stay 12 and the maternal category/scores must stay the same. For MEDIUM/HIGH, PE shows its **14–40-week** coverage and no PE category.
2. A LOW record without recorded PE triggers remains `NOT_INDICATED`; LOW with a recorded hypertension/proteinuria trigger still opens PE and cannot generate a category at 12 weeks.
3. **14** and **40** are inclusive PE duration bounds when every other value is supported; **45** can be saved but is outside PE coverage. The automated duration tests exercised these paths with real fitted/imported models.
4. In Health history, delete an incorrect record with a reason. It and linked assessments disappear from active views; original audit information/notes remain. Add a corrected record.
5. Use separate patient/doctor accounts to check that unselected, expired, revoked and removed records cannot be read through a consultation.

For uploads, use a small valid PDF, PNG or JPEG. Maximum is 5 MB per file, 50 MB total and 100 reports per patient. An uploaded report's successful download and sharing still need a destination browser check.
