# Model source review and fresh training

Reviewed and trained **21 October 2026** using the [selected original repository](https://github.com/mehkzhra/BloomCare/tree/e7bce42d00a7c5813964a6b2d6f1cd5142cab518/ml). Repository files were read through the connected GitHub app. Data blob identities and SHA-256 checks are recorded in `ml/training_reports/source-review-2026-10-21.json`.

## Source findings

- `Maternal Health Risk Data Set.csv`: 1,014 rows, parsed data identical to the reviewed UCI CSV; LF versus CRLF line endings only. The six features do not include pregnancy duration. The repository copy's SHA-256 is `e9518da2d936be5a5b9b458fa5794113b9d7c888c743b01c8c58e625235b1255`; the reviewed UCI CRLF bytes have SHA-256 `a1f7025719f84715096e0d1f95ae2e56b57809b9b15449e1836c96a7d976ae9b`.
- `pregnancy_risk_dataset.csv`: only 15 rows, no documented independent outcome provenance or pregnancy-duration input. It was inspected and not used to claim improved clinical coverage.
- PE training/test workbooks: 162/41 raw rows, exact matches to the previously pinned source hashes. The combined data has only 90 distinct rows after removing 113 exact duplicates. Used features remain complete; two unused all-missing Doppler columns are omitted from retraining.

The source target names describe LOW/MID/HIGH categories. They do not establish confirmed PE diagnoses. HB units and the outcome definition are still undocumented. No third-party pickle was loaded for this review.

## Executed results

| Experiment | Fitting/test rows | Accuracy | Macro-F1 | Main limit |
| --- | --- | --- | --- | --- |
| Current maternal configuration, fresh grouped reproduction | 359 / 90 | 71.11% | 0.6671 | MEDIUM recall 33.33%; historical test, no external validation. |
| Original repository maternal row-split recipe, freshly fitted | 811 / 203 | 86.21% | See JSON | 160 test rows exactly match measurements in fitting data. |
| PE categories, fresh grouped reproduction | 72 / 18 | 72.22% | 0.6619 | Very small historical test; units/outcomes and coverage remain unresolved. |

The maternal cleaning audit retains contradictory labels in the same group. It produces 449 usable rows and 35 conflicting measurement groups. Identical six-feature groups do not cross the current fitting/test boundary. Fresh fitting used the current fixed Random Forest parameters; the historical test was not used to tune this run. The old row-split result is shown to explain a score difference, not as evidence of superior generalization.

The prior 85 evaluations across Random Forest, Extra Trees and Gradient Boosting also remain documented in `ml/training_reports/v1.0.0/comparison.json`. None passed all non-regression checks. The two reports read by the admin workspace remain in their established locations. Detailed progress, inactive fitted candidate trees and older notes are available inside `docs/history.zip`.

**No active model, trust registration, original clinical observation or target label was replaced.** Fitted copies from this review were kept outside the application runtime. Reusing the same historical partitions is reproducibility, not a newly untouched test or clinical validation.

## Reproducing training on Windows

Keep the working model and registry backed up. For a new local installation, `ml\check-and-train.cmd` trains/validates the fixed UCI model; for an existing completed installation it verifies rather than overwrites its artifact. To compare alternatives without activating them:

```bat
.\scripts\retrain-models.cmd
.\scripts\retrain-pe.cmd --source "D:\path\to\original-BloomCare"
```

Use a checked-out original repository whose workbooks match the pinned hashes. These runners write timestamped evidence and do not promote candidates. Dependencies are pinned in the existing requirements. The source-review JSON records the source hashes, full evaluation reports, observed PE ranges and activation decision from this run.

## Pregnancy duration

A saved 12-week value remains 12. The maternal forest ignores pregnancy duration because the training feature schema omits it; its output must not be presented as a validated 12-week prediction. The PE data covers **14–40 weeks** and cannot support a 12-week category. The runtime retains `OUTSIDE_COVERAGE` and doctor review. Removing a bound or adding fabricated early-pregnancy rows would not provide valid coverage.

For an improved medical model, obtain representative, permitted data with documented units, patient/time identifiers for appropriate separation, a verified outcome and suitable independent evaluation. Assess per-class errors and intended-use performance before promotion. This review did not make a clinical validation claim.

UCI attribution: Ahmed, M. (2020), *Maternal Health Risk*, DOI [10.24432/C5DP5D](https://doi.org/10.24432/C5DP5D), CC BY 4.0. Source values are converted from Fahrenheit to Celsius, mapped to the application labels, deduplicated and checked against the existing input contract; the full audit is retained.
