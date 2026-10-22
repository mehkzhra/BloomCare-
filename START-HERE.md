# BloomCare 1.2.0 — current Windows handover

This combined update contains every delivered module. Version 1.2.0 adds a maternal-embrace logo/favicon, a colorful coordinated interface for the public site and all three roles, HTTPS Brevo recovery emails, and a full-app free Render + Neon deployment path. The previous email verification, password reset, authentication limits and restore-test workflow remain included.

**Without a domain:** follow [FREE-DEPLOYMENT.md](docs/FREE-DEPLOYMENT.md). It explains each account, field and paste location in Roman Urdu, including how to initialize the first cloud administrator without a shared password.

1. Stop the backend and frontend servers. Keep Docker Desktop running.
2. Extract this ZIP directly into `D:\Desktop\BloomCare`, replacing included files.
3. Run in CMD:

```bat
cd /d D:\Desktop\BloomCare
.\scripts\update-final.cmd
```

The updater checks dependencies and models, saves a PostgreSQL backup, runs frontend and disposable PostgreSQL checks, and verifies schema head `0013_account_security`. This additive migration preserves prior rows, adds two user fields and two security tables (31 total). At the end it removes only unchanged obsolete files whose original content is verified in `docs\history.zip`. Locally edited legacy files are kept. Configuration, credentials, accounts, patient records, reports, model trust and active trained models are preserved.

Start these in separate CMD windows, then refresh with **Ctrl+F5**:

```bat
.\scripts\start-backend.cmd
```

```bat
.\scripts\start-frontend.cmd
```

The footer should show **v1.2.0**. In **Help & support → Application version**, check that the server also reports **1.2.0**.

Check a **12-week** record: the entered duration stays 12. Maternal screening uses the other six model inputs. If PE is triggered, its stage explains **14–40 weeks**, generates no PE category and offers doctor review. This is not a LOW PE result. Use [tested samples](docs/TEST-SAMPLES.md) for the supported demonstration paths.

Follow [the five final delivery steps](docs/FINALIZE-TODAY.md). Local email enforcement remains off until configured; public hosting requires verified emails and a configured email provider (Brevo HTTPS or TLS SMTP). No real email/provider/camera/hosting test is claimed by this package.

Read [completed work and remaining delivery checks](docs/DELIVERY-STATUS.md), [deployment steps](docs/DEPLOYMENT.md) and [verification](docs/VERIFICATION.md). The ZIP updates an existing working installation; it does not deploy a public service or regenerate private setup.
