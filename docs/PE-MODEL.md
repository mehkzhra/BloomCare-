# PE model contract and provenance

The active PE component is the owner-authorized original BloomCare forest, converted once to pinned, non-executable JSON. It remains separate from the six-input maternal model. The latest source/training review is in [MODEL-TRAINING.md](MODEL-TRAINING.md).

## Workflow

MEDIUM/HIGH maternal results, systolic BP >=140, diastolic BP >=90, recorded hypertension history or proteinuria trigger the PE stage. A LOW category alone does not rule out PE. Missing measurements request completion; unsupported values retain the original record and return no PE category. Saved results are immutable and linked to their assessment/model snapshot.

Base values come from the saved record: age, duration and blood pressure. Nine additional values are pregnancies, previous births, BMI, diabetes, hypertension history, HB, fetal weight, urine protein and amniotic-fluid measurement. Unknown results are never guessed. Two wholly missing Doppler columns are unused by every original tree and are not requested.

| Field | Original observed coverage |
| --- | --- |
| Pregnancy duration | 14–40 weeks |
| Age | 18–38 years |
| Pregnancies / previous births | 1–8 / 0–6, with parity below gravida |
| BMI | 16.4–43.3 |
| Systolic / diastolic BP | 90–130 / 20–90 mmHg |
| HB | 8–11.2, unit undocumented |
| Estimated fetal weight | 0.0001–9.55 kg |
| Amniotic fluid measurement | 4.79–18 cm |
| Diabetes, hypertension history, urine protein | Explicit yes/no |

These bounds and unusual source values require data/clinical review; they are not clinical normal ranges. **12 weeks is unsupported**, and BP-triggered records above the PE systolic ceiling cannot receive a model category. Preserving this guard is preferable to presenting unsupported inference as reliable. The interface displays exact unsupported values and a doctor-review action.

## Source and numerical compatibility

- [Original repository](https://github.com/mehkzhra/BloomCare/tree/e7bce42d00a7c5813964a6b2d6f1cd5142cab518/ml), immutable commit `e7bce42d00a7c5813964a6b2d6f1cd5142cab518`.
- Original forest SHA-256: `4959ef608bd58ece855566d292c1940be3edf0ddb0e1028ea8923f2c887032bd`.
- Runtime JSON directory: `ml/artifacts/legacy_pe_v0.7.1`; integrity pins are checked before parsing/loading.
- The original 200 trees and class order HIGH/LOW/MEDIUM are retained. No original pickle is loaded by the application.
- Prior conversion comparisons covered 203 source rows, 512 deterministic synthetic vectors and 14,928 split-boundary vectors, including float32 behavior. Maximum class-score difference was approximately `6.66e-16` in that export environment. Numerical parity does not establish clinical validity.

The original 162/41 split has 25 test rows matching fitting inputs, so its 90.24% nominal score is not independent evaluation. Fresh deduplicated/grouped retraining reproduced 72.22% accuracy on 18 historical test rows and was not activated. Source origin/licensing for medical reuse, HB units, confirmed outcomes and independent clinical validation remain unresolved. Scores are uncalibrated category scores, not disease probabilities.

Supported results retain actual feature explanations and selected-record access checks. An unavailable model does not erase previously saved results. Use the [current updater](../START-HERE.md), [test samples](TEST-SAMPLES.md) and [verification record](VERIFICATION.md).
