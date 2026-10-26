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
