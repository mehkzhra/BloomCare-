# BloomCare deployment handover — v1.2.0

**No purchased domain:** start with [FREE-DEPLOYMENT.md](FREE-DEPLOYMENT.md). The new Render Dockerfile serves Vite and FastAPI at one HTTPS origin with an external Neon database, a build-time locally trained trusted maternal model, the pinned PE forest, Brevo HTTPS email and first-admin mailbox recovery. No live deployment or credentials are bundled.

The Windows application is the working installation. Included container files provide an **optional local release stack**, not an already provisioned public deployment. Native Windows/container execution and hosted HTTPS were not run in this environment. Follow [DELIVERY-STATUS.md](DELIVERY-STATUS.md) for remaining checks.

## Local release stack

1. Complete `scripts\update-final.cmd` and save a database backup. Stop native frontend/backend processes.
2. Keep the existing database/network running:

```bat
docker compose up -d --wait
```

3. Confirm that the locally trained `ml\artifacts\maternal_rf_v0.2` and `backend\model-trust.json` exist if assessments are enabled. They are mounted read-only. The ZIP preserves existing runtime files and does not ship private trust or an executable maternal model.
4. Build/start the release services:

```bat
docker compose -f compose.deploy.yaml up -d --build
curl.exe --fail http://127.0.0.1:8080/api/health/ready
```

Open `http://127.0.0.1:8080`. Check registration, all three role sessions, record entry, assessment, consented care guide, a selected-record consultation episode, upload/download and deletion. Restore a backup into a separate test database and verify its data before relying on recovery.

The stack reuses external network `bloomcare-fresh_default` and database service `db:5432`; web is exposed only at `127.0.0.1:8080`. API/database credentials come from the existing local configuration. Reports are stored in the database as `MedicalReport.content`; their bytes are covered by a complete database backup. A new uploads volume is not needed for this implementation.

## Public HTTPS configuration

For the optional self-managed/VPS route, choose the hosting environment and domain, then configure its TLS reverse proxy to the loopback web port. In `backend\.env`, set `COOKIE_SECURE=true`. Set the **same exact HTTPS origin** for native settings and the release Compose override:

```text
# backend/.env
ALLOWED_ORIGINS=https://your-domain.example
COOKIE_SECURE=true

# root .env, used only as the Compose interpolation override
BLOOMCARE_ALLOWED_ORIGINS=https://your-domain.example
```

Use the actual domain; do not retain the example. Restart/recreate the API after changing configuration. Keep the generated JWT secret private and stable across ordinary restarts; plan deliberate rotation separately. Keep database/API ports private and apply host access rules. The backend enforces origin and session checks independently of navigation. Do not print `docker compose config` into a shared log because resolved configuration can include credentials.

The Compose file now permits the origin override above; without it, its default remains the local port-8080 origins. HTTPS/cookie/origin behavior must be checked at the real URL. Review the outer proxy's forwarding, body-size and timeout settings. Its logs must not capture private query strings or request bodies; the included API/web access logs are disabled.

Configure the actual Groq key/model and run `scripts\check-groq.cmd`. Use `scripts\configure-integrations.cmd webrtc` for the intended ICE/STUN/TURN service and `scripts\check-services.cmd` for non-secret configuration status. A configuration result does not verify connectivity. Test a real two-device call, including network changes and denied permissions.

Email verification, self-service password reset, session revocation after reset and persisted login throttling are now implemented. Configure SMTP using `scripts\configure-integrations.cmd email`, or Brevo HTTPS using `scripts\configure-integrations.cmd email-brevo` and verify real inbox delivery. Use `compose.public.yaml` for the direct Caddy HTTPS variant; it sets the public origin, secure cookies and required email verification automatically from `BLOOMCARE_DOMAIN`. The API stays private. See [FINALIZE-TODAY.md](FINALIZE-TODAY.md) for the complete ordered setup, safe restore test and acceptance steps.

Manual WhatsApp sharing is a browser/device handoff. Automatic alerts additionally require Twilio configuration, recipient consent and the appropriate sender/template setup; use `scripts\configure-whatsapp.cmd`. Verify queued, delivered, failed and uncertain states honestly. Provider credentials and TLS/hosting accounts are not included in the ZIP.

## Operations and recovery

- Schedule database backups outside the application machine and test restoration. Preserve the matching source, schema version, original model manifests/artifacts and private trust registry for recovery; protect their credentials separately.
- Run one API process initially: the current reminder loop is process local. Multiple workers would require an explicit shared job/locking design before claiming exactly-once notification behavior.
- Monitor `/api/health/live`, `/api/health/ready`, application errors, disk/database capacity and provider failures. Configure request/connection limits at the chosen edge and test them with login and upload behavior.
- Keep a rollback package and matching verified database backup. Audit-preserving migrations are forward-only; do not assume a downgrade will undo clinical changes.
- Run expected-load and authorization checks against the deployed stack. The retained 100-account/10-client SQLite benchmark is scoped historical evidence, not production capacity proof.

Stop only the local release services with:

```bat
docker compose -f compose.deploy.yaml down
```

Do not add a volume-deletion option to database teardown unless deliberate data deletion is intended. The deployment status remains **destination verification pending** until the public URL, persistence/recovery and live workflows have been checked.
