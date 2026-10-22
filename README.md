# BloomCare

Connected maternal care for patients, doctors and administrators. Current release: **1.2.0**.

**No domain?** Use the included [free Render + Neon deployment guide](docs/FREE-DEPLOYMENT.md), with exact dashboard fields for email recovery, Groq, TURN and optional Twilio alerts. This release adds an original maternal-embrace favicon/logo and a coordinated colorful interface for all three roles.

The application connects observations, staged screening, clinical review, appointments, care guides, reports and conversations. All previously delivered modules remain included. This release adds email verification, one-use password recovery, persisted authentication limits, a safe isolated restore test and an optional public HTTPS template. Earlier pregnancy-duration guidance, training evidence and the simplified handover remain included.

## Update on Windows

Stop both servers, extract into the existing `D:\Desktop\BloomCare` folder, and keep Docker Desktop running:

```bat
cd /d D:\Desktop\BloomCare
.\scripts\update-final.cmd
```

Restart `scripts\start-backend.cmd` and `scripts\start-frontend.cmd` in separate CMD windows, then Ctrl+F5. Confirm interface/server **1.2.0** in Help & support. Configuration, accounts, reports, database and active model/trust files are preserved. See [START-HERE.md](START-HERE.md).

## Delivered workflows

- Patient: profile, health entry/history, staged assessment and explanations, care guide, appointments, medications, reminders, symptoms, reports and separate assistant.
- Doctor: website registration/approval, selected active shared records, review history, notes/amendments, follow-up, schedule, messages and video.
- Admin: applications/accounts, operational activity, scoped analytics, service configuration and honest model evaluation/training evidence.
- Continuing care: consent/revocation, PDF/passport/timeline, family access, manual WhatsApp sharing, optional automatic alerts, English/Urdu and RTL.

Incorrect health records and linked assessments can be withdrawn from active care with a reason. Audit metadata and clinical notes remain. Role, ownership and sharing checks run on the backend.

## Current guides

| Guide | Contents |
| --- | --- |
| [Finalize today](docs/FINALIZE-TODAY.md) | Ordered Windows/email/recovery/provider/hosting checks and final handover. |
| [Delivery status](docs/DELIVERY-STATUS.md) | Completed modules, 12-week behavior and pending deployment checks. |
| [Deployment](docs/DEPLOYMENT.md) | Existing database, optional local containers, HTTPS configuration and recovery. |
| [Model training](docs/MODEL-TRAINING.md) | Source comparison, fresh results, overlap audit and promotion decision. |
| [Test samples](docs/TEST-SAMPLES.md) | Maternal/PE categories, duration boundaries and correction checks. |
| [Verification](docs/VERIFICATION.md) | Executed checks and destination limits. |
| [Architecture](docs/ARCHITECTURE.md) / [Requirements](docs/REQUIREMENTS.md) | Current structure and carried-forward SRS/design traceability. |
| [Recruiter walkthrough](docs/RECRUITER-WALKTHROUGH.md) | Demonstration of product and engineering quality. |
| [Asset licences](docs/THIRD-PARTY-ASSETS.md) | PDF/font provenance and redistribution terms. |

The maternal model does not use pregnancy weeks. A saved **12-week** observation remains 12; a triggered PE stage cannot produce a category outside its **14–40-week** coverage. The interface explains this and offers clinician review. Model coverage is not a clinical normal range, and absence of a PE result is not a LOW prediction.

Fresh grouped training reproduced **71.11% maternal accuracy** and **72.22% PE comparison accuracy**. MEDIUM recall and PE data provenance/coverage remain material limits. Active models were retained; no clinical certification or public deployment is claimed. Historical guides, old updater commands and inactive candidate trees are consolidated in `docs/history.zip`; the updater removes only exact archived obsolete copies.
