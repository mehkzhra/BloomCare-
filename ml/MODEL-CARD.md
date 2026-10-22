# Current integration and retraining status

Updated 16 October 2026 for BloomCare v1.0.0. The historical training record below
is preserved. The application now integrates the registered maternal model and
actual SHAP; the earlier statements below about integration/explanation being
pending describe the original training checkpoint.

Executed v1.0.0 comparisons did not pass all non-regression checks; the existing
model is retained. See [the retraining record](../docs/MODEL-TRAINING.md) and
`training_reports` for actual scores, candidate exports and method limits. Neither
software integration nor retraining establishes clinical validity.

---

# Maternal-risk Random Forest v0.2: experimental training record

The model predicts the UCI dataset's LOW, MEDIUM, and HIGH risk categories.
It is a research checkpoint for BloomCare, with application activation disabled.
It does not predict a diagnosis, a probability of complications, or a
pre-eclampsia outcome. No code, model, dataset copy, or secrets from the old
17-module BloomCare project were used.

## Original source and feature contract

Ahmed, M. (2020). *Maternal Health Risk* [Dataset]. UCI Machine Learning
Repository. https://doi.org/10.24432/C5DP5D, licensed CC BY 4.0.
Source: https://archive.ics.uci.edu/dataset/863/maternal+health+risk.

| Source column | BloomCare feature, in training order | Unit or conversion |
| --- | --- | --- |
| Age | age_years | years |
| SystolicBP | systolic_mmhg | mmHg |
| DiastolicBP | diastolic_mmhg | mmHg |
| BS | glucose_mmol_l | mmol/L |
| BodyTemp | temperature_c | Source Fahrenheit; convert `(F - 32) * 5 / 9` |
| HeartRate | heart_rate_bpm | beats per minute |

`RiskLevel` is the target: `low risk` -> LOW, `mid risk` -> MEDIUM,
`high risk` -> HIGH. Gestational weeks are recorded in the foundation but are
absent from this model. No PE label exists in the source.

## Data audit

The reviewed CSV contains 1,014 rows, although the UCI page lists 1,013
instances. Counts below come from the actual checksum-verified CSV.

| Audit item | Observed count |
| --- | ---: |
| Downloaded rows | 1,014 |
| Exact duplicate feature-and-label rows removed | 562 |
| Unique feature-and-label rows before input bounds | 452 |
| Unique rows excluded by the existing application input bounds | 3 |
| Usable feature-and-label rows | 449 |
| Unique six-feature measurement groups | 413 |
| Measurement groups with conflicting labels, retained | 35 |

Two unique rows exceed the application's age input bound and one has a heart
rate below its input bound. These bounds are an application input contract,
not definitions of normal physiology. The three rows are excluded, not replaced
with invented measurements. Non-finite values and unrecognized labels fail
training. All available reviewed source features are complete; the fitted
median imputer is not used to conceal missing source measurements.

## Evaluation method

A measurement group is the exact six-feature vector, ignoring its risk label.
All rows in that group remain on the same side of the split, including
contradictory labels. The first fold of
`StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261010)` is fixed
as the held-out partition. This is one fixed hold-out evaluation, not a report
of five-fold cross-validation.

| Partition | Rows | Measurement groups | LOW | MEDIUM | HIGH |
| --- | ---: | ---: | ---: | ---: | ---: |
| Training | 359 | 330 | 184 | 85 | 90 |
| Held out | 90 | 83 | 47 | 21 | 22 |

There are zero shared measurement groups. No patient identifiers are available,
so this cannot establish separation of actual patients. Removing duplicates
and grouping identical measurements reduces a specific form of leakage; it
does not prove the absence of other leakage.

The pipeline fits a median imputer and a Random Forest on training rows only.
Forest parameters are fixed: 400 trees, maximum depth 12, minimum leaf size 2,
`max_features="sqrt"`, `class_weight="balanced_subsample"`, seed 20261010,
and one worker. No hyperparameter search was run, the held-out data were not
used for fitting, and the saved model was not refitted using those rows.

## Observed held-out results

| Model | Accuracy | Macro F1 |
| --- | ---: | ---: |
| Random Forest | 71.11% | 0.6671 |
| Always predict training's most frequent class (LOW) | 52.22% | 0.2287 |

| Class | Precision | Recall | F1 | Held-out rows |
| --- | ---: | ---: | ---: | ---: |
| LOW | 70.69% | 87.23% | 0.7810 | 47 |
| MEDIUM | 43.75% | 33.33% | 0.3784 | 21 |
| HIGH | 100.00% | 72.73% | 0.8421 | 22 |

Confusion matrix, with actual labels in rows and predicted labels in columns:

| Actual / predicted | LOW | MEDIUM | HIGH |
| --- | ---: | ---: | ---: |
| LOW | 41 | 6 | 0 |
| MEDIUM | 14 | 7 | 0 |
| HIGH | 3 | 3 | 16 |

Fourteen of 21 medium-risk examples were predicted LOW. Six of 22 high-risk
examples were not predicted HIGH. High precision is measured on a small
held-out sample and does not imply perfect clinical performance.
The included `reference-results/evaluation.json` contains the full unrounded
results; the verifier reloads the locally trained model and replays the
held-out evaluation.

## Limits and activation status

The data contain contradictory labels for identical measurements, no patient
identifiers, and no prospectively observed complication labels. Values below
6 mmol/L glucose are absent from the dataset. No independent external or
clinical validation, probability calibration, or patient-specific SHAP
explanation has been completed. Global impurity feature importance in the
manifest is not a patient-specific explanation.

The weaker medium-class recall matters for the locked MEDIUM/HIGH-to-PE
workflow. Current performance does not justify presenting the app as a validated
clinical screening system. This checkpoint therefore supplies a reproducible
experimental artifact and transparent evaluation; app predictions remain
disabled pending a separate reviewed integration checkpoint.

Any PE model must use a separate verified source with an actual PE outcome,
documented units, valid licensing, and evaluation. Maternal-risk class labels
must not be converted into invented PE outcomes.

Technical method reference:
https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html.
Artifact trust and version compatibility reference:
https://scikit-learn.org/stable/model_persistence.html.
