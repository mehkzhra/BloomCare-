<p align="center">
  <img src="frontend/public/bloomcare-mark.svg" width="72" height="72" alt="BloomCare logo">
</p>

<h1 align="center">BloomCare</h1>

<p align="center">A connected maternal care workspace for patients, doctors and administrators.</p>
<p align="center"><strong>Version 1.3.0 · React · FastAPI · PostgreSQL · English & Urdu</strong></p>

BloomCare connects health observations, maternal risk screening, clinical review, appointments, reports and conversations. Patients manage their care records, doctors review the records shared with them, and administrators manage accounts and operational activity.

[Features](#features) · [Windows setup](#windows-setup) · [Configuration](#configuration) · [Docker and live access](#docker-and-live-access) · [Verification](#verification) · [Developer guides](#developer-guides)

## Features

| Workspace | Main tasks |
| --- | --- |
| **Patient** | Profile and pregnancy details, health records and assessments, appointments, reports and PDFs, assistant, medications and reminders, symptoms and family access. |
| **Doctor** | Website registration and approval, shared patient records, clinical reviews and notes, follow-up proposals, availability, messages and video consultations. |
| **Administrator** | Doctor approvals, account management, operational summaries, activity and audit history, service availability. |

- **Screening and review:** maternal screening, a PE stage when indicated, coverage checks and clinician review.
- **Record correction:** withdraw an incorrect record or assessment with a reason while retaining audit metadata and clinical notes.
- **Connected care:** selected-record sharing, appointments, follow-up, messaging and video calls.
- **Documents:** report uploads, assessment PDFs, a health passport and manual WhatsApp/device sharing.
- **Assistant:** separate, consent-based questions and assessment care guidance through Groq.
- **Continuity:** medication reminders in Notifications while the backend runs, a care timeline and controlled family access.
- **Interface:** English/Urdu, right-to-left support, responsive pages and secondary history shown on demand.

Manual WhatsApp sharing needs no Twilio account. The optional Twilio care alert requires the user to choose a contact, consent and submit it; assessments do not automatically send WhatsApp messages.

## Technology

| Layer | Implementation |
| --- | --- |
| Frontend | React 19, Vite, React Router, Tailwind CSS |
| Backend | Python 3.12, FastAPI, Pydantic |
| Database | PostgreSQL 16, SQLAlchemy, Alembic |
| Screening | Local maternal Random Forest and pinned legacy PE classifier |
| Services | Groq, Brevo or TLS SMTP, WebRTC |
| Checks | pytest, Vitest, Testing Library, Ruff, ESLint |
| Packaging | Windows helpers and Docker Compose |

The chatbot is separate from the screening models. Its source default is `openai/gpt-oss-20b`; `GROQ_MODEL` determines the configured provider model.

## Windows setup

### Requirements

- Git, Python **3.12**, Node.js **24+** and Docker Desktop with Compose.
- Matching, maintainer-approved model artifacts for the complete assessment workflow.
- Email/Groq credentials for the corresponding services.

The public repository excludes private configuration, database backups, runtime model artifacts and the model trust registry. A fresh clone requires these setup steps; it does not contain accounts or shared passwords.

### Run an existing installation

From the working project root, start these in **separate Command Prompt terminals**:

```bat
.\scripts\start-backend.cmd
```

```bat
.\scripts\start-frontend.cmd
```

Open **http://127.0.0.1:5173**. The API runs at **http://127.0.0.1:8000**. Keep Docker Desktop running for local PostgreSQL.

Use [START-HERE.md](START-HERE.md) to select an updater for older installations. Initial setup deliberately refuses to overwrite existing `.env` files.

<details>
<summary><strong>First-time installation from source</strong></summary>

Run from the directory where you want a new checkout:

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

Before enabling assessments, supply the approved maternal artifact directory, matching `backend\model-trust.json` and pinned PE artifact directory under `ml\artifacts`. Follow the [model guide](docs/MODEL-TRAINING.md) and [PE guide](docs/PE-MODEL.md) for training, activation and verification. Candidate training does not automatically replace active models.

Create the first trusted administrator with your own reachable email:

```bat
.\scripts\create-admin.cmd --email your-real-email@example.com --name "BloomCare Administrator"
```

The helper prompts for a password without displaying it. Start both services using the commands above.

</details>

Patients and doctors register on the website. Doctor access requires administrator approval; public registration cannot create an administrator. Configured account email delivery supports verification and one-use password reset links. Resetting a password invalidates earlier sessions.

## Configuration

| Private file | Purpose |
| --- | --- |
| Root `.env` | Local Docker database name, user and password |
| `backend/.env` | Database URL, session secret, origins and integrations |
| `backend/model-trust.json` | Identity and integrity checks for the activated maternal model |

| Settings | Variables |
| --- | --- |
| Database | `DATABASE_URL` |
| Sessions/origins | `JWT_SECRET`, `JWT_MINUTES`, `PUBLIC_APP_URL`, `ALLOWED_ORIGINS`, `COOKIE_SECURE` |
| Email | `EMAIL_PROVIDER`, `EMAIL_FROM`, `BREVO_API_KEY`, or the selected provider's `SMTP_*` settings |
| Verification | `AUTH_REQUIRE_EMAIL_VERIFICATION` |
| Assistant | `GROQ_API_KEY`, `GROQ_MODEL` |
| Video networking | `WEBRTC_ICE_SERVERS` |
| Model activation | `BLOOMCARE_RESEARCH_ASSESSMENTS` and matching registered artifacts |

Use `scripts\configure-integrations.cmd` for supported guided configuration modes. Keep keys on the backend, preserve working secrets and restart after environment changes. User passwords are stored as hashes in PostgreSQL, not in `.env`.

The local database listens on `127.0.0.1:5433`. Neon is optional for an external database and is not required locally.

## Docker and live access

Docker packages and runs BloomCare. Public access also requires a host or tunnel.

### Local Docker release

From the **working installation**, with its configuration and model artifacts available:

```bat
docker compose up -d --wait db
docker compose -f compose.deploy.yaml up -d --build
```

Open **http://127.0.0.1:8080**. Nginx serves the frontend and proxies `/api` to FastAPI. The stack reuses `bloomcare-fresh_default`, mounts local model artifacts read-only and keeps API/database ports private.

### Temporary HTTPS demo

A Cloudflare Quick Tunnel provides a temporary URL without a domain. The computer, Docker, internet connection and tunnel must stay running; restarting the tunnel changes its URL. This is a demonstration route, not permanent managed hosting.

After starting the local database, run this in a dedicated terminal and leave it open:

```bat
docker run --rm --network bloomcare-fresh_default cloudflare/cloudflared:latest tunnel --no-autoupdate --url http://web:80
```

Copy the printed HTTPS `trycloudflare.com` origin. In a second Command Prompt terminal, from the working project root, replace the example with that exact address:

```bat
set "BLOOMCARE_DEMO_ORIGIN=https://your-generated-name.trycloudflare.com"
docker compose -f compose.deploy.yaml -f compose.demo.yaml up -d --build
```

The demo overlay aligns email links and allowed origins, enables secure cookies and requires verified account emails. Configure working email delivery and verify every demo account before login. Authentication requests share a conservative proxy-level limit in this demo mode. Use synthetic records and test login/recovery, assessments, sharing and a real two-device call at the public URL.

Stop the tunnel with Ctrl+C. To restore local HTTP container settings, run this from a new terminal:

```bat
docker compose -f compose.deploy.yaml up -d --force-recreate api
```

Docker builds and public connectivity require verification on the target PC; this README update does not claim they have run.

### Hosted deployment

Current Hugging Face documentation requires a paid plan to create Docker Spaces and allows outbound requests on ports 80, 443 and 8080. Standard PostgreSQL on 5432 therefore needs a verified networking alternative; a normal Neon connection string is not a drop-in solution. Static Spaces cannot run this backend.

### Northflank with Neon

For hosting independent of the Windows PC, the Northflank Sandbox plan currently advertises no card requirement and always-on services within its free resource limits. This is a project/demo deployment; clinical validation and production operations remain separate requirements. Account eligibility and available capacity must be checked in the dashboard. This repository does not claim a completed Northflank deployment or a hosted URL.

1. Sign in at [Northflank](https://app.northflank.com/) and select **Sandbox / Free**. Create a project and a **combined service** named `bloomcare` from this repository's `main` branch.
2. Choose **Dockerfile**, path `/deploy/northflank.Dockerfile`, build context `/`. Expose **HTTP port 10000** publicly and copy the generated HTTPS origin from Networking. Use the free included compute allocation and one instance.
3. In the **working Windows installation**, with the new helper copied into `scripts`, run:

   ```bat
   .\backend\.venv\Scripts\python.exe scripts\prepare_cloud_settings.py
   ```

   Enter the Northflank HTTPS origin, Neon PostgreSQL connection URL with SSL, and the administrator's real email/name. The database URL is hidden while typing. The helper reads the working email, Groq and video settings, generates a new cloud session key, and creates **`backend/.env.northflank`**. It preserves an existing export on reruns. The export is ignored by Git; import it into Northflank's **runtime environment variables**.
4. Add these **runtime secret files**, uploading the existing local files individually. Keep them out of build arguments and public Git/image registries:

   | Local file under `ml/artifacts/legacy_pe_v0.7.1` | Container mount path |
   | --- | --- |
   | `forest.json` | `/app/ml/artifacts/legacy_pe_v0.7.1/forest.json` |
   | `manifest.json` | `/app/ml/artifacts/legacy_pe_v0.7.1/manifest.json` |
   | `explanation-weights.json` | `/app/ml/artifacts/legacy_pe_v0.7.1/explanation-weights.json` |

   The maternal model is trained and verified during the image build from the checksum-pinned public fixture. Private PE assets are excluded from the Dockerfile's source copies and mounted at runtime. Startup verifies both models before migrations and serving; missing or changed assets stop startup. The synthetic parity fixture is not needed in the running service.
5. Deploy/restart after saving the runtime variables and files. Configure an HTTP readiness check on port **10000**, path **`/api/health/ready`**, with startup time allowed for Python imports and migrations. Wait for `{"status":"ready"}`, then open the generated origin.
6. For a new empty Neon database, request **Forgot password** using `BOOTSTRAP_ADMIN_EMAIL` to establish the first administrator's password through that mailbox. Local accounts and records are not copied automatically. Existing database accounts are preserved; bootstrap cannot promote a patient or add a new administrator to an occupied database.

The HTTPS origin and allowed origins must match. Use verified emails, keep API/provider keys in Northflank's runtime variables, and retain the private settings file for recovery. Authentication uses the conservative shared proxy limit (`AUTH_PROXY_HEADER=none`); do not enable Render-specific proxy trust on Northflank. Test login/recovery, both assessments, sharing, Groq and an actual cross-network video call at the hosted origin before sharing it for review. Finally, verify access from another device with the Windows PC off.

Platform references checked **25 October 2026**: [Northflank pricing](https://northflank.com/pricing), [combined service setup](https://northflank.com/docs/v1/application/getting-started/build-and-deploy-your-code), [private runtime files](https://northflank.com/docs/v1/application/secure/upload-secret-files), [Hugging Face Spaces](https://huggingface.co/docs/hub/en/spaces-overview), [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

## Security and recovery

- Backend role, ownership and sharing checks control access to records and actions.
- Passwords use Argon2; sessions use HttpOnly cookies; authentication limits persist in PostgreSQL.
- Uploaded report bytes are stored in PostgreSQL and included in complete database backups.
- Keep configuration, model artifacts and backups outside public source control and maintain an off-machine recovery copy.

Create a local database backup:

```bat
.\scripts\database-backup.cmd backup
```

Use its printed filename for an isolated restore check:

```bat
.\scripts\database-backup.cmd restore-test --file "backups\YOUR_BACKUP_FILENAME.dump"
```

This restores into a temporary database and checks core tables and report lengths. Full recovery also requires matching source, configuration, model files and a separately checked application instance. After a Git history cleanup, use a clean clone for future pushes.

## Verification

With the required private configuration and model assets available:

```bat
backend\.venv\Scripts\python.exe -m ruff check backend scripts ml deploy --config backend\pyproject.toml
backend\.venv\Scripts\python.exe -m pytest -c backend\pyproject.toml backend\tests
backend\.venv\Scripts\python.exe -m pytest -c ml\pytest.ini ml\tests
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

Recorded release checks on **22 October 2026**: backend **311 passed / 1 PostgreSQL-only skip**, frontend **143 passed**, ML **11 passed**, plus lint and the production frontend build. [Verification evidence](docs/VERIFICATION.md) records their scope; these results do not certify live hosting or clinical performance.

## Screening scope

Screening categories support review; they are not a diagnosis. The retained models have not been independently clinically validated. Coverage, measurement definitions and evaluation limits require resolution before clinical use.

The maternal model uses six inputs and does not use pregnancy duration. A saved **12-week** record remains 12 weeks. If PE screening is required, its classifier cannot return a category outside **14–40 weeks**. An unavailable PE result is not LOW risk. Actual observations must not be changed to obtain a prediction.

## Developer guides

| Guide | Contents |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | Components, data flows and boundaries |
| [Requirements](docs/REQUIREMENTS.md) | Implementation traceability |
| [Model training](docs/MODEL-TRAINING.md) | Source review, reproducibility and evaluation limits |
| [PE model](docs/PE-MODEL.md) | Pinned source, feature contract and coverage |
| [Test samples](docs/TEST-SAMPLES.md) | Supported demo inputs and boundary cases |
| [Deployment](docs/DEPLOYMENT.md) | Containers, HTTPS and recovery |
| [Verification](docs/VERIFICATION.md) | Recorded checks and their limits |
| [Recruiter walkthrough](docs/RECRUITER-WALKTHROUGH.md) | Product and engineering walkthrough |
| [Asset licences](docs/THIRD-PARTY-ASSETS.md) | Font/PDF dependencies and redistribution |

Historical notes are consolidated in `docs/history.zip`. Source checksums are recorded in `DELIVERY-MANIFEST.json`.
