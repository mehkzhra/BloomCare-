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

Supported results retain actual feature explanations and selected-record access checks. An unavailable model does not erase previously saved results. Use the [current updater](../README.md), [test samples](TEST-SAMPLES.md) and [verification record](VERIFICATION.md).

## High blood pressure workflow (2026-10-29)

The form, saved record and assessment display independent blood-pressure care guidance even when screening cannot run. Systolic >=140 OR diastolic >=90 triggers same-day maternity contact; systolic >=160 OR diastolic >=110 triggers immediate maternity/emergency care guidance. Severe readings suppress routine appointment links in the assessment/PE stage. Advice distinguishes current from historical readings and remains visible before 20 weeks and alongside LOW model categories. Actual measurements are preserved.

Thresholds follow [NICE NG133](https://www.nice.org.uk/guidance/ng133/chapter/recommendations) and its [gestational hypertension summary](https://www.nice.org.uk/guidance/ng133/resources/gestational-hypertension-pdf-8720711394). Same-day contact wording is a conservative application routing policy. This rule is not a PE diagnosis, classifier output, or substitute for clinical assessment; lower readings do not exclude PE or concerning symptoms.

This change fixes the dead-end workflow, not the model's evidence gap. PE inference still declines unsupported measurements. Wider inference requires appropriately licensed, documented data with confirmed outcomes, adequate coverage, patient-separated evaluation and independent clinical validation. No range widening, clipping, invented training examples or replacement model is included.

## Reproducible PE validation audit — 29 October 2026

Run from the repository root with research dependencies installed:

```powershell
python -m ml.validate_pe --source "PATH-TO-PINNED-LEGACY-REPOSITORY" --output "pe-validation-new-run.json"
```

The command checks workbook hashes, audits the deployed JSON forest on its original test set, and separately retrains five fixed-parameter candidate folds. It never activates a candidate or modifies maternal screening. Report: [PE validation results](../ml/training_reports/pe-v1.0.0/pe-validation-2026-10-29.json).

- Deployed PE forest integrity, feature mapping and reference-score verification passed; 27 PE API/runtime tests passed.
- Original nominal accuracy reproduces at 90.24%, but 25 of 41 test inputs match training inputs. This is not independent accuracy.
- Of 203 source rows, 113 exact labelled duplicates are removed: 90 labelled rows, 89 unique feature groups, one conflicting-label group.
- Two used values are missing (one HB, one amniotic-fluid measurement). The new candidate evaluation fits median imputation within each training fold, unlike the historical workbook-level preprocessing.
- Across five disjoint-feature-group folds, candidate out-of-fold accuracy is 68.89%, macro F1 0.637, HIGH-label recall 50.00%, MEDIUM-label recall 48.28%. The majority-class baseline accuracy is 47.78%.
- These are internal historical-category results, not sensitivity for clinically confirmed PE. Candidate parameters were retained from the earlier experiment; the data have already been examined. No patient IDs or untouched external cohort are available.
- Wider BP coverage, confirmed outcomes, HB units, questionable source measurements and independent clinical validation remain unresolved. The candidate is not promoted, and the deployed model must not be presented as clinically validated.

Delivery classification: software/demo PE workflow verified; standalone clinical PE detection not established. The independent high-BP care guidance remains in place. No maternal model change is included.

## New independent-source CBC candidate — 29 October 2026

A separate logistic-regression candidate was actually trained on [Wassim Almawi, Preeclampsia Hematological Indices, Mendeley Data V1](https://data.mendeley.com/datasets/j7d8cdndpw/1), DOI 10.17632/j7d8cdndpw.1, CC BY 4.0. The source describes a retrospective case-control cohort: 192 PE cases and 219 controls. This is a new dataset relative to the legacy BloomCare data, not external validation of the candidate trained on it.

The downloaded workbook SHA-256 is pinned in `ml/train_pe_cbc.py`. Its columns contain six CBC measurements and PE/control status, but no BP or gestational age. Units, collection timing and diagnostic adjudication details have not been established from the retrieved workbook/metadata. Do not substitute these measurements for existing PE form fields or invent three-class labels.

Fixed-seed grouped split: 328 training rows, 83 held-out rows, no identical measurement-group overlap. Median imputation and scaling fit only training rows; fixed logistic regression and threshold 0.5, without test-set tuning. Fourteen measurements were missing. There are 410 distinct measurement groups. JSON export parity with the trained pipeline passed.

[Report](../ml/training_reports/pe-cbc-2026-10-29/report.json): held-out AUROC 0.9283 (bootstrap interval 0.8711–0.9744), sensitivity 34/39 = 87.18%, specificity 35/44 = 79.55%. Five PE cases were missed and nine controls flagged in this sample. This small internal holdout is not prospective clinical validation. Case-control sampling prevents interpreting scores as population disease probabilities.

[Candidate coefficients](../ml/training_reports/pe-cbc-2026-10-29/candidate.json) are explicitly inactive. They are not loaded by the website and contain no individual records. No maternal model was changed. Before activation: confirm units, assay/timing and diagnosis definitions with the data custodian; evaluate a frozen candidate on a separately collected cohort; obtain clinician review of intended use, thresholds and workflow.

Reproduce with research dependencies from the repository root:

```powershell
python -m ml.train_pe_cbc --source "PE LMR Dataset Almawi.xlsx" --output "private-builds/pe-cbc-new-run"
```

The raw workbook is not redistributed in this repository. Use the original dataset's download and preserve its attribution.

Other reviewed candidates: Dryad 10.5061/dryad.kprr4xhk9 describes a 410-participant intervention trial in high-risk overweight pregnancies; download requests in this environment returned 403/401, so no training claim is made for it. Zenodo 15294686 uses cord-blood measurements and is unsuitable as an early antenatal input replacement.

## Frozen candidate evaluation tool

`ml/evaluate_pe_cbc.py` evaluates the existing JSON coefficients without retraining,
changing the 0.5 threshold, or activating any model. It uses Python's standard library.
This is evaluation tooling, not additional patient validation evidence.

Before running it, the data custodian must resolve the training-unit/timing questions
above and document a separately collected cohort. Do not guess units or populate the
metadata with assumptions. Use one de-identified patient per CSV row, with the header:

```text
patient_id,Status,WBC,RBC,Neutrophils,Lymphocytes,Monocytes,Platelets
```

Status is `Patients` for adjudicated PE and `Controls` for controls. Blank CBC cells
use the frozen training medians; an entirely blank CBC is rejected. Repeated patient
IDs, negative/non-finite measurements and cohorts lacking either class are rejected.
Use a private JSON metadata file containing non-empty evidence for `cohort_name`,
`data_custodian`, `unit_mapping_evidence`, `measurement_timing`, `diagnostic_criteria`,
and `patient_separation_evidence`, plus `units_match_training: true` only after actual
verification. The checker cannot independently verify these declarations or exclude
overlap with unavailable training patient identifiers.

```powershell
python -m ml.evaluate_pe_cbc --candidate ml/training_reports/pe-cbc-2026-10-29/candidate.json --cohort PRIVATE-COHORT.csv --metadata PRIVATE-METADATA.json --output PRIVATE-EVALUATION.json
```

The aggregate report includes input hashes, missing-value count, confusion matrix,
missed cases, sensitivity/specificity and Wilson 95% intervals. It excludes patient
identifiers and individual predictions, refuses to overwrite an existing report,
and always preserves `clinical_use: false`. Clinician review, data provenance and
prospective intended-use validation remain human/evidence requirements.

## Care-guide availability

When Groq is missing, times out or returns a service error, care-plan generation now
saves a clearly labelled English/Urdu basic educational guide with provenance
`local-basic-guide-v1`. It uses the existing saved BP guidance and NICE NG133 symptom
advice, does not invent a PE category, and distinguishes old readings from current or
unreviewed readings. Consent, ownership, immutable saved context and duplicate-request
protection are preserved. It is not an AI-personalized or clinician-approved plan.
An already saved basic guide is returned on repeat requests for the same context.
An explicit consented AI-personalization retry can replace a basic guide after the
provider recovers; it is subject to a cooldown and preserves the assessment context.

This fallback requires a running application/database. It cannot repair a hosting
proxy's 503 response while the container is sleeping. Health readiness alone does
not verify authenticated care-plan generation or cross-network video calls.
