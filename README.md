# BloomCare

Connected maternal care for patients, doctors and administrators. Current release: **1.3.0**.

**Run locally on Windows:** follow [START-HERE.md](START-HERE.md) for the PostgreSQL setup and startup commands. An [optional Render + Neon deployment guide](docs/FREE-DEPLOYMENT.md) is included; a public deployment is not provisioned. The interface puts each role’s care tasks first. Model accuracy, training comparisons, class scores, SHAP and setup commands are absent from user pages; developer evidence stays in the source and model guides.

The application connects observations, staged screening, clinical review, appointments, care guides, reports and conversations. All previously delivered modules remain included. This release adds email verification, one-use password recovery, persisted authentication limits, a safe isolated restore test and an optional public HTTPS template. Earlier pregnancy-duration safeguards, developer training evidence and handover tools remain included.

Private configuration, database backups and runtime model artifacts are excluded from this public source. The maintainer must supply the matching maternal and PE model artifacts before running model verification; preserve the working installation's model directories and trust file. See [model training](docs/MODEL-TRAINING.md) and [deployment/recovery](docs/DEPLOYMENT.md). This source push does not publish the PE explanation node weights or synthetic parity fixtures.

## Interface update from the working 1.2.0 installation

Stop the server, extract this combined ZIP into your existing BloomCare folder and replace included source files. Then run `scripts\update-ui.cmd`; it checks and rebuilds the frontend without changing the database or environment. Run `scripts\start-local.cmd`, open `http://127.0.0.1:8000` and Ctrl+F5. The helper serves the built interface and API together on this computer, without editing saved secrets. The complete updater below is available when updating an older database installation.

## Update on Windows

Stop both servers, extract into the existing `D:\Desktop\BloomCare` folder, and keep Docker Desktop running:

```bat
cd /d D:\Desktop\BloomCare
.\scripts\update-final.cmd
```

Restart `scripts\start-backend.cmd` and `scripts\start-frontend.cmd` in separate CMD windows, then Ctrl+F5. The maintainer can confirm server **1.3.0** at `/api/health/live`; release details are intentionally absent from the user interface. Configuration, accounts, reports, database and active model/trust files are preserved. See [START-HERE.md](START-HERE.md).

## Delivered workflows

- Patient: profile, health entry/history, staged screening results and next care actions, care guide, appointments, medications, reminders, symptoms, reports and separate assistant.
- Doctor: website registration/approval, selected active shared records, review history, notes/amendments, follow-up, schedule, messages and video.
- Admin: applications/accounts, operational activity, scoped care insights, approvals and service availability.
- Continuing care: consent/revocation, PDF/passport/timeline, family access, manual WhatsApp sharing, optional patient-triggered Twilio care alerts, English/Urdu and RTL. Assessment results do not automatically send WhatsApp messages.

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
