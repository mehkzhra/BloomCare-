<p align="center">
  <img src="frontend/public/bloomcare-mark.svg" width="80" alt="BloomCare heart and bloom logo">
</p>
<h1 align="center">🌸 BloomCare</h1>
<p align="center"><strong>Connected maternal care, with a workspace for every role.</strong></p>
<p align="center">React · FastAPI · PostgreSQL · Machine learning · English & Urdu</p>

BloomCare brings pregnancy observations, risk screening, clinician review and care coordination into one application. Patients manage their records, doctors review information shared with them, and administrators oversee access and activity.

**[🌐 Hosted address](https://bloomcare.containers.snapdeploy.app)** · [🚀 Setup](#-get-started-on-windows) · [☁️ Deployment](docs/DEPLOYMENT.md) · [🧪 Demo inputs](docs/TEST-SAMPLES.md) · [🏗️ Architecture](docs/ARCHITECTURE.md)

> Final-year project scope: demonstrate the implemented care workflow with labelled synthetic records. Screening is not independently clinically validated. See the [submission and demonstration guide](docs/FINAL-YEAR-SUBMISSION.md). A readiness check returned HTTP 200 on 29 October 2026; this does not establish continuous availability or verify every authenticated workflow.

## ✨ What you can do

| Workspace | Features |
| --- | --- |
| 🩷 **Patient** | Pregnancy profile, health records, maternal and indicated PE screening, assessment history, appointments, reports, care messages, medications, symptoms, family access and a separate assistant. |
| 🩺 **Doctor** | Register for approval, manage availability, review shared records, add clinical reviews and notes, propose follow-ups, message patients and join video consultations. |
| 🛡️ **Administrator** | Approve doctors, manage accounts, inspect operational activity and audit records, and check integration availability. |

- **One assessment flow:** save actual observations, run maternal screening, and complete the separate PE stage when indicated and within coverage.
- **Correct mistakes:** withdraw a health record or assessment with a reason; audit metadata and clinical notes are retained.
- **Share selectively:** grant access to chosen records, revoke sharing and export readable reports or a health passport.
- **Talk and coordinate:** appointment-linked video, care messages and consent-based Groq assistance.
- **Stay organised:** care timelines, medication notifications and compact, on-demand history.
- **Use your language:** English/Urdu text, right-to-left support and responsive role-specific pages.

Manual WhatsApp sharing does not require Twilio. Automatic WhatsApp alerts are not enabled by this setup; optional provider-driven alerts require configuration, consent and a submitted action. Medication reminders are processed while the backend is running, including after it resumes from sleep.

## 🧭 How the care flow works

1. A patient registers, verifies their email and records health observations.
2. The maternal model returns a screening category for supported measurements.
3. Where indicated, the separate PE stage checks additional observations and its coverage.
4. The patient shares selected information and books a consultation.
5. An approved doctor reviews the information and records clinical guidance.

The assistant answers questions separately from the screening models. It does not decide either classifier's category.

## 🧰 Technology

| Layer | Implementation |
| --- | --- |
| Interface | React 19, Vite, React Router, Tailwind CSS |
| API | Python 3.12, FastAPI, Pydantic |
| Data | PostgreSQL, SQLAlchemy, Alembic migrations |
| Screening | Trained maternal Random Forest with SHAP explanations; pinned original PE forest |
| Integrations | Brevo or TLS SMTP, Groq, WebRTC |
| Quality checks | pytest, Vitest, Testing Library, Ruff, ESLint |
| Delivery | Windows helpers, Docker images and Docker Compose |

**Neon is hosted PostgreSQL.** Local Docker PostgreSQL and Neon are different instances of the same database technology. Database models, migrations and backup tooling remain required. Accounts do not transfer automatically between instances.

## 🚀 Get started on Windows

### Prerequisites

- Python **3.12**, Node.js **24+**, Git; Docker Desktop for the local PostgreSQL setup.
- Maintainer-approved model assets for the complete screening workflow.
- Private provider credentials for email and assistant features.

The public repository intentionally excludes secrets, database dumps and private runtime models. A clean clone alone does not include accounts or an activated assessment model.

### Existing working installation

From the project root in CMD:

```bat
.\scripts\update-ui.cmd
.\scripts\start-local.cmd
```

Open **http://127.0.0.1:8000**. This serves the built UI and API together. Keep the configured database available. For a full older-installation schema update, back up first and use `scripts\update-final.cmd`; read [deployment and recovery](docs/DEPLOYMENT.md).

<details>
<summary><strong>First-time source installation</strong></summary>

```bat
git clone https://github.com/mehkzhra/BloomCare-.git BloomCare
cd BloomCare
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r backend\research-requirements.txt
backend\.venv\Scripts\python.exe scripts\setup.py
docker compose up -d --wait db
npm.cmd --prefix frontend ci
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
cd ..
```

Supply the approved maternal artifact and matching `backend/model-trust.json`, plus the pinned PE files under `ml/artifacts`. Follow [model setup](docs/MODEL-TRAINING.md) and the [PE contract](docs/PE-MODEL.md). Training candidates does not automatically activate them.

Create the first local administrator using a reachable email:

```bat
.\scripts\create-admin.cmd --email your-real-email@example.com --name "BloomCare Administrator"
```

The helper securely prompts for a password. Then build and start using the existing-installation commands above.

For development with hot reload, run `scripts\start-backend.cmd` and `scripts\start-frontend.cmd` in separate terminals; the frontend is at **http://127.0.0.1:5173**.

</details>

Patients and doctors register through the website. Doctors require approval. Public registration cannot create an administrator. Cloud first-admin setup uses mailbox password recovery rather than a shared default password.

## 🔐 Configuration and privacy

| Configuration | Purpose |
| --- | --- |
| Root `.env` | Local Docker PostgreSQL credentials |
| `backend/.env` | Local API settings and integrations |
| Hosting environment variables | Cloud database, secure sessions, public origin and service keys |
| `backend/model-trust.json` | Integrity registration for the active maternal model |

Keep `DATABASE_URL`, `JWT_SECRET`, `BREVO_API_KEY`, `GROQ_API_KEY` and any TURN credentials private. Never place them in frontend variables or commit them. `BOOTSTRAP_ADMIN_EMAIL` is the admin login address; `EMAIL_FROM` is the verified sending address.

Password hashes use Argon2. Sessions use HttpOnly cookies; public hosting requires secure cookies and exact HTTPS origins. Backend role, ownership and sharing checks protect records. Password reset revokes earlier sessions, and login throttling persists in PostgreSQL.

See the [deployment guide](docs/DEPLOYMENT.md) for the complete cloud settings table, backup steps and acceptance checks.

## 🧪 Testing and demo records

- [Maternal LOW / MEDIUM / HIGH inputs](docs/examples/BloomCare-Health-Record-Samples.txt)
- [PE LOW / MEDIUM / HIGH inputs](docs/examples/BloomCare-PE-Test-Samples.txt)
- [Coverage and correction checks](docs/TEST-SAMPLES.md)

These are synthetic manual-entry examples, not patient data or clinical targets. Uploading them in Reports does not run an assessment. Results were checked against the available local cloud-build models, not queried from the live site.

With the required private test configuration and approved model assets installed:

```bat
backend\.venv\Scripts\python.exe -m ruff check backend scripts ml deploy --config backend\pyproject.toml
backend\.venv\Scripts\python.exe -m pytest -c backend\pyproject.toml backend\tests
backend\.venv\Scripts\python.exe -m pytest -c ml\pytest.ini ml\tests
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

Historical test evidence and its limitations are in [VERIFICATION.md](docs/VERIFICATION.md). Passing software tests does not establish clinical validity or live provider availability.

## 🧠 Screening scope

The maternal classifier uses six observations; **pregnancy duration is not one of its inputs**. A saved 12-week record remains 12 weeks. The separate PE model supports observed pregnancy durations of **14–40 weeks**, together with its other measurement bounds. Outside coverage produces no PE category; it must not be treated as LOW risk.

The models have not completed independent clinical validation. Original PE outcome definitions and HB units remain unresolved. Screening supports review and is not a diagnosis. Never alter real observations to make them fit the model.

## 📁 Repository map

| Directory | Contents |
| --- | --- |
| `frontend/` | UI, translations, browser-side reports and component tests |
| `backend/` | API, permissions, database models, migrations and tests |
| `ml/` | Reproducible training, contracts and evaluation evidence |
| `deploy/` | Container startup, model preparation and server configuration |
| `scripts/` | Windows startup, setup, backups and maintainer utilities |
| `docs/` | Focused technical guides and synthetic examples |

## 📚 Engineering notes

[Architecture](docs/ARCHITECTURE.md) · [Requirements](docs/REQUIREMENTS.md) · [Deployment](docs/DEPLOYMENT.md) · [Model training](docs/MODEL-TRAINING.md) · [PE model](docs/PE-MODEL.md) · [Verification](docs/VERIFICATION.md) · [Walkthrough](docs/RECRUITER-WALKTHROUGH.md) · [Third-party licences](docs/THIRD-PARTY-ASSETS.md)

Superseded ZIP handover pages have been consolidated into this README and the deployment guide. `docs/history.zip` is retained because the Windows legacy-cleanup utility verifies archived hashes before removing old files. `DELIVERY-MANIFEST.json` protects source integrity during private image packaging.
