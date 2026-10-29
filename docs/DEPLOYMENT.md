# BloomCare deployment and recovery

This is the single current operations guide. Local Windows and cloud deployments share the same application but have separate configuration and, unless explicitly pointed to the same instance, separate databases.

## Current hosted address

https://bloomcare.containers.snapdeploy.app

As of 26 October 2026, the address and port 10000 are assigned. Supplied logs show Uvicorn starting successfully on 0.0.0.0:10000 and later receiving a graceful shutdown. Readiness following the latest start remains unconfirmed. Earlier account registration and administrator password recovery were reported working on the previous cloud address. Do not infer that every feature has passed on the new address.

## Local Windows

For the working installation, run `scripts\update-ui.cmd`, then `scripts\start-local.cmd`; open http://127.0.0.1:8000. The helper uses local HTTP only for that process. Docker Desktop is needed when the configured database is the local Compose PostgreSQL service.

For older schemas, first back up and then run `scripts\update-final.cmd`. It checks dependencies, makes a local database backup, applies migrations, runs checks and performs hash-protected legacy cleanup. Do not point local-only setup/backup helpers at Neon and assume they manage its hosted database.

For a local release stack:

```bat
docker compose up -d --wait db
docker compose -f compose.deploy.yaml up -d --build
```

Open http://127.0.0.1:8080. The Compose stack requires the working private configuration, model artifacts and `bloomcare-fresh_default` network. A tunnel to this stack depends on the PC remaining on; cloud hosting does not.

## Private cloud image

Use the existing approved private Docker image when available. A source clone does not include private PE assets. To prepare a source build with those assets, from the clean checkout run with the working installation's Python:

```bat
D:\Desktop\BloomCare\backend\.venv\Scripts\python.exe scripts\prepare_cloud_upload.py --model-dir "D:\Desktop\BloomCare\ml\artifacts\legacy_pe_v0.7.1"
```

Extract the resulting private ZIP into a separate build directory. Its root Dockerfile builds the UI and verifies models; it is not the generic Python upload route. From that extracted directory:

```bat
docker buildx build --platform linux/arm64 --provenance=false --load --progress=plain -t bloomcare-cloud:latest .
docker image save -o D:\Desktop\BloomCare-Cloud-Image.tar bloomcare-cloud:latest
```

Upload the image privately. Do not publish runtime PE models, private archives, settings or data to a public repository/registry. For the SnapDeploy signed PUT route, this session succeeded with `Content-Type: application/x-tar`; `application/octet-stream` returned SignatureDoesNotMatch. A successful upload is HTTP 200, not merely curl exit code 0. Request container name `bloomcare` where available, and confirm the assigned URL rather than guessing it.

## Cloud environment

Copy working credentials privately. When replacing a container, preserve the same database and JWT secret. Values in the Windows `.env` do not automatically become hosting variables.

| Variable | Value / meaning |
| --- | --- |
| `DATABASE_URL` | Existing Neon PostgreSQL connection URL, with required SSL settings |
| `JWT_SECRET` | Existing strong private session secret |
| `PUBLIC_APP_URL` | `https://bloomcare.containers.snapdeploy.app` for this assigned deployment |
| `ALLOWED_ORIGINS` | Exactly the same origin, without a trailing slash or extra origins |
| `COOKIE_SECURE` | `true` |
| `AUTH_REQUIRE_EMAIL_VERIFICATION` | `true` |
| `AUTH_PROXY_HEADER` | `none` for this host; do not enable Render-specific trust |
| `BLOOMCARE_RESEARCH_ASSESSMENTS` | `true`, with matching approved artifacts |
| `BOOTSTRAP_ADMIN_EMAIL` | Existing cloud administrator's login email, or the first owner's reachable email on an empty database |
| `BOOTSTRAP_ADMIN_NAME` | Administrator name |
| `EMAIL_PROVIDER` | `brevo` |
| `EMAIL_FROM` | Brevo verified sender address |
| `BREVO_API_KEY` | Private working Brevo key |
| `GROQ_API_KEY` | Private working Groq key |
| `GROQ_MODEL` | Exact working model ID from the existing configuration |
| `PORT` | `10000`; hosting target/listening port must match |
| `WEBRTC_ICE_SERVERS` | Optional working ICE JSON; absent defaults to `[]`, which is not a promise of cross-network connectivity |

No Twilio credentials are required for manual WhatsApp sharing. Save all variables before starting. Preserve quotes inside JSON; do not surround plain dashboard values with extra quotes.

The initial administrator receives a random unknown password. Use Forgot Password with `BOOTSTRAP_ADMIN_EMAIL` to set it via the inbox. Changing this variable does not rename or promote an existing account. On an existing database, supplying a different bootstrap email may stop startup. Patient and doctor accounts created only on local PostgreSQL do not automatically exist on Neon.

## Health and troubleshooting

- `/api/health/live`: API process responds.
- `/api/health/ready`: required database tables are accessible; this does not test providers or clinical model validity.
- If assessments are unavailable, check the saved `BLOOMCARE_RESEARCH_ASSESSMENTS=true` setting and refresh after the container restarts. In an authenticated browser, `/api/capabilities` exposes `pregnancy_model_ready` and `pe_model_ready`. A healthy database alone does not enable either model. If the switch is already enabled and readiness is false, inspect model loading logs; do not retrain or bypass artifact verification.
- A generic port warning is not proof of a port mismatch. Compare the configured target port, `PORT`, complete application logs and hosting stop reason.
- `Cloud startup stopped (ValueError)` can mean environment, bootstrap or model validation failed. Do not delete models or the database based on this generic message.
- `Application startup complete` and `Uvicorn running on http://0.0.0.0:10000` confirm startup, but not external routing or ongoing availability.
- If server startup succeeds and the host then terminates it, inspect the deployment health/stop reason before repeating deployments.

Check the provider's current dashboard quotas. Free sleeping hosts cannot process reminders while stopped; HTTP video signalling also consumes request quota. See [SnapDeploy limits](https://snapdeploy.dev/docs/free-tier) and [API reference](https://snapdeploy.dev/api). This project does not promise a free always-on service.

## Backup and restore

For the local Docker database:

```bat
.\scripts\database-backup.cmd backup
.\scripts\database-backup.cmd restore-test --file "backups\YOUR_BACKUP_FILENAME.dump"
```

The restore test uses a temporary database. Hosted Neon backups require an export/restore workflow for the actual Neon database; test restoration in a separate database/branch rather than overwriting live data. Report bytes live in PostgreSQL, so complete data backups include them. Preserve configuration and approved model artifacts separately and privately.

## Acceptance before sharing

1. Verify readiness and page access from another device with the Windows PC off.
2. Test patient registration/verification, approved doctor access and administrator login.
3. Request and complete password recovery using a real inbox; confirm the link uses the new origin.
4. Run the [maternal and PE examples](TEST-SAMPLES.md), then check coverage rejection and record withdrawal.
5. Upload/download a report; verify selected sharing, revocation and access denial from another account.
6. Test Groq, a real two-device video call on different networks and the mobile layout.
7. Confirm backup restore and monitor hosting limits. Keep old deployment rollback options until checks pass.

Vercel compatibility was reviewed, not implemented: the current 5 MB report limit exceeds its documented 4.5 MB Function payload limit, and the 30-second reminder loop needs a different scheduling design. No all-features Vercel deployment is claimed.

## Performance update (27 October 2026)

Readiness now checks its 25 required tables in one SQL statement. Dashboard totals and notification assessment references are batched; notification polling no longer loads full assessment relationships for each row. Access auditing remains enabled, with its PostgreSQL timeouts set together.

Background refresh retains visible records, runs sequentially, and pauses polling while the tab is hidden. Consultation signal reads retry bounded temporary failures without closing the video immediately; permission failures and ended consultations still stop. Mutating requests are never automatically replayed. Default signalling interval is three seconds. Public frontend files support gzip compression. Only fingerprinted public JS/CSS/font assets receive immutable browser caching; HTML and authenticated API responses remain no-store.

These are source changes: a GitHub push does not replace an image already uploaded to SnapDeploy. Pull the commit, run `python scripts/prepare_cloud_upload.py`, extract the newly generated private ZIP into a fresh build directory, and rebuild the ARM64 image before uploading it. Keep existing environment values and the live database. Never upload the old TAR expecting new code. Retest readiness, notification refresh and a two-device consultation after deployment. Free-host sleep/wake delays and database/network latency require live measurements; the code changes do not guarantee removal of every 503.

## GitHub builds on the existing SnapDeploy container

The root `Dockerfile` builds the frontend and the verified maternal model. PE artifacts remain outside public Git: `scripts/provision_cloud_models.py` uploads the three checksum-pinned JSON files once to a separate `bloomcare_runtime_assets` table in the **existing live PostgreSQL database**. No patient tables are modified. The ordinary database backup includes this table; restrict database credentials as usual. No API exposes these assets.

Run the provisioning script from the latest source, optionally passing `--model-dir` for the original Windows PE directory. Paste the current live Neon URL into its hidden prompt, not into chat or a command argument. A `READY` result means the transaction committed. Startup fetches missing PE files into the writable container filesystem, verifies all pinned SHA-256 values before writing, and runs the existing model verification before migrations and serving requests. Existing images with all valid PE files bundled still work without this table. A new model checksum requires provisioning that version before deployment; older versions remain available for rollback.

Only after provisioning succeeds, connect GitHub to SnapDeploy and link `mehkzhra/BloomCare-`, branch `main`, to the **existing** `bloomcare` container ID. The documented endpoint is `POST /api/mobile/github/link` with `containerId`, `repoFullName`, and `deployBranch`. Linking itself starts the first build: do not trigger a second deploy. Do not use the new-container deploy endpoint, delete the container, change its name, or replace its environment map. Retain the current database, JWT secret, public URL, origins, provider keys and port 10000. Verify auto-deploy is enabled for main after linking.

The root Dockerfile is intended for a fresh Git checkout. Local unit/integration checks do not substitute for the first provider build: verify its logs, readiness, both model flags, sign-in, password recovery and two-device consultation before declaring the update live.

## Care-plan HTTP 503 hosting diagnosis — 29 October 2026

A public request to the live readiness URL returned HTTP 503 with SnapDeploy's HTML “Waking up your container” page. This confirms a hosting-level failure at that check; it does not prove that every previous care-plan error had the same cause. The patient-specific care-plan POST requires an authenticated session and was not live-tested here.

The frontend now distinguishes hosting HTML from API JSON (including HTML returned as HTTP 200), gives an actionable message, and offers opening the app in a new tab. It never automatically replays a care-plan write or claims a plan was saved. Provider JSON error details remain intact.

Start/resume the existing bloomcare container, wait for readiness JSON and the normal login page, then refresh the assessment and check for an already-saved guide before generating again. If the host repeatedly sleeps during use, inspect provider activity/sleep settings; UI changes cannot provide always-on hosting. Retain container name, port, database and environment settings. If a care-plan POST still fails while readiness is healthy, inspect its JSON error code and provider logs without exposing keys or patient payloads.
