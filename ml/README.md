# BloomCare model tooling

The current application has two separate stages: a locally trained maternal pipeline and the owner-authorized original PE forest exported to pinned JSON. Model data/coverage and validation limits are explained in [MODEL-TRAINING.md](../docs/MODEL-TRAINING.md) and [PE-MODEL.md](../docs/PE-MODEL.md). Current installation instructions are in [START-HERE.md](../README.md).

## Commands

Use the existing Python 3.12 backend environment from Windows CMD at the BloomCare root:

```bat
.\ml\check-and-train.cmd
.\scripts\retrain-models.cmd
.\scripts\retrain-pe.cmd --source "D:\path\to\original-BloomCare"
```

The first command creates the fixed maternal artifact only if absent, otherwise verifies the completed artifact. The comparison commands write timestamped evidence without activating candidates. Back up the current artifact/trust before deliberately changing any registration. Never load arbitrary uploaded/third-party pickle files.

| Path | Purpose |
| --- | --- |
| `data_contract.py`, `fetch_data.py` | Pinned source, units, duplicate/conflicting-label groups and fixed split. |
| `train_maternal.py`, `verify_model.py` | Fixed maternal pipeline and artifact/evaluation replay. |
| `train_comparison.py`, `retrain_legacy_pe.py` | Training-only model comparison and checked legacy-category reproduction. |
| `artifacts/maternal_rf_v0.2` | Locally generated executable maternal artifact; excluded from delivered source ZIP. |
| `artifacts/legacy_pe_v0.7.1` | Original active PE JSON, manifest, parity fixtures and explanation data. |
| `reference-results` | Original fixed maternal evaluation for reproducibility. |
| `training_reports/v1.0.0/comparison.json` | Required admin comparison evidence; 85 evaluations, no candidate promoted. |
| `training_reports/pe-v1.0.0/pe-retraining-report.json` | Required admin grouped PE report. |
| `training_reports/source-review-2026-10-21.json` | Fresh repository/data review, fitting results and overlap audit. |
| `../docs/history.zip` | Detailed historical runs and inactive fitted candidate trees; not used for inference. |

Fresh source review reproduced 71.11% maternal accuracy and 72.22% PE grouped comparison accuracy. Historical partitions were already evaluated; these are not new external tests. No active model or trust file was replaced.

Pregnancy weeks are not a maternal input. PE observed duration is 14–40 weeks; neither the current data nor the 15-row alternative establishes 12-week PE support. Actual observations remain saved and unsupported inference is withheld. See [delivery status](../docs/DEPLOYMENT.md).

UCI source: Ahmed, M. (2020), *Maternal Health Risk*, DOI https://doi.org/10.24432/C5DP5D, CC BY 4.0. Reviewed CSV SHA-256: `a1f7025719f84715096e0d1f95ae2e56b57809b9b15449e1836c96a7d976ae9b`. The source-review report records the repository copy's newline-only difference and exact workbook hashes.
