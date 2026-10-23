# BloomCare — final delivery steps

Release **1.3.0**, 21 October 2026. **For the requested free hosting without a domain, follow [FREE-DEPLOYMENT.md](FREE-DEPLOYMENT.md) first.** This older five-priority guide also retains the Windows and optional VPS checks. The agreed product modules are implemented. The included account features are: email verification, password reset and persisted login throttling. The remaining work is configuration and destination acceptance, plus independent clinical validation before medical claims. No public URL or real delivery/camera result has been verified here.

Monitoring, scheduled backups and rollback belong to the operational handover below. This checklist does not certify that no other defect can exist.

## 1. Update Windows and check all three actors

Stop frontend/backend, keep Docker Desktop running, and extract the combined ZIP directly into the existing `D:\Desktop\BloomCare`. In CMD:

```bat
cd /d D:\Desktop\BloomCare
.\scripts\update-final.cmd
```

Wait for the **v1.3.0 complete update passed** message. The updater saves a database backup, tests in a separate PostgreSQL database, then applies additive migration **0013_account_security**. It preserves accounts/password hashes, patient records, reports, local configuration and active model/trust files. Original migrations are retained. The current schema has 31 tables.

Start in separate CMD windows:

```bat
.\scripts\start-backend.cmd
```

```bat
.\scripts\start-frontend.cmd
```

Ctrl+F5; the maintainer can verify server **1.3.0** at `/api/health/live` and the interface version in `frontend/package.json`. Version diagnostics are absent from user pages. Use separate browser profiles:

- Patient: register/sign in, save a record, assess, reload, upload/download a report and withdraw an incorrect record with a reason.
- Doctor: website registration, admin approval, accept an appointment with selected shared records, review/note/follow-up and message. Unselected/revoked/removed records must be inaccessible.
- Admin: doctor approval, accounts/activity, model evidence and connected-service status. Configuration labels do not prove delivery.

Use [TEST-SAMPLES.md](TEST-SAMPLES.md). Include a 12-week MEDIUM/HIGH case: duration stays 12; maternal screening still uses its other six inputs; PE explains its 14–40-week coverage and produces no category. Confirm that the history no longer displays a withdrawn incorrect record.

## 2. Configure and test account email/security

Use an SMTP service/account you control. Obtain its SMTP host, TLS mode/port, approved sender, username and app credential from the provider. Do not put SMTP credentials in chat, Git or a frontend file. In CMD:

```bat
.\scripts\configure-integrations.cmd email
```

For a first local test, choose application origin `http://127.0.0.1:5173`, the provider's STARTTLS/SSL settings, and **N** for requiring verification until the inbox test is complete. Credentials are hidden at entry. Restart the backend and check Admin → Connected services.

1. Register a patient using an inbox you control. Open the email link and press **Verify email address**. Visiting the link alone does not consume it.
2. Request **Forgot password?** from sign-in. Open the latest email link, enter/confirm a 12–128-character password, then sign in again. Old passwords and previous sessions on other devices must stop working.
3. A reused/expired link must fail and offer a new request. Reset links last 30 minutes; verification links last 24 hours. A new request supersedes the earlier link.
4. Use reachable emails for all public accounts, including the admin. Placeholder addresses such as `doctor1@example.com` cannot receive verification. If the existing admin uses a placeholder, create a separate controlled-email admin with `scripts\create-admin.cmd --email "YOUR_REAL_EMAIL" --name "BloomCare Admin"`, replacing `YOUR_REAL_EMAIL` first. The script prompts privately for its password. Confirm that admin's email through the website too.
5. Once delivery works, require verification for public sign-in. The included public Compose template enforces this automatically. A local installation can set it through the same wizard. Email verification and doctor approval are separate checks.

Login is limited to **10 attempts per email and 50 per connection peer per 15 minutes**. Recovery/verification requests share **3 per email and 20 per peer per hour**; confirmations allow **30 per peer per 15 minutes**. These counters survive API restarts. A 429 response supplies `Retry-After`. Test limits with a disposable account, so the demonstration accounts remain usable.

Accepted email requests give the same response for eligible and unknown addresses. SMTP submission runs after that response; acceptance is not an inbox-delivery receipt. If the process stops before delivery or the service fails, request a fresh link. Delivery failures are metadata events; passwords and link secrets are not logged. A durable email job queue/retry service would be a further reliability improvement for a larger service, not something claimed by this release.

## 3. Test backup restoration and live providers

Create a named backup, choosing a new filename if this already exists:

```bat
.\scripts\database-backup.cmd backup --file "backups\before-public-1.3.0.dump"
.\scripts\database-backup.cmd restore-test --file "backups\before-public-1.3.0.dump"
```

`restore-test` creates a random **separate** database, restores the custom dump with errors treated as failures, reads core tables, checks report byte lengths and removes only that newly created database. It does not restore over the application database. A successful message verifies those checks; a full recovery rehearsal also needs a separate application instance reading a restored database and its matching model/trust files.

```bat
.\scripts\check-groq.cmd
.\scripts\check-services.cmd
```

Keep the already working Groq configuration. Ask one consented question in Assistant and generate/reopen one consented care guide. Check errors when the provider is unavailable; no invented response should replace a failure.

For video, use an approved doctor and patient on **two devices and the intended networks**, with an accepted appointment in its access window. The doctor starts the call. Allow camera/microphone and verify two-way audio/video, denied-permission handling and hang-up. Configure provider ICE/TURN settings if needed:

```bat
.\scripts\configure-integrations.cmd webrtc
```

Restart after changes. TURN settings being saved is not proof of a relayed call. Public preflight requires a configured TURN relay for the intended cross-network deployment.

For WhatsApp, download/share a PDF to your own test contact and confirm the attachment arrives. Manual sharing is a handoff. If automatic alerts are enabled:

```bat
.\scripts\configure-whatsapp.cmd
```

Use the approved sender, recipient opt-in and provider-required sandbox/template setup. Send one explicitly consented test and check actual delivery status. `QUEUED` does not mean `DELIVERED`; an uncertain result must not be blindly sent again.

## 4. Host the existing application with HTTPS

This Python/PostgreSQL application needs a host supporting Docker, persistent storage and the required ML dependencies. A static-only host cannot run its backend. Choose the server/domain/account; no hosting purchase or public deployment was made here.

On the server, install Docker Engine and the Compose plugin using the [official installation instructions](https://docs.docker.com/engine/install/). Copy the source privately to a directory such as `/opt/bloomcare`. Transfer the required existing root/backend configuration, database backup, trained maternal directory and model-trust file separately over your authenticated server connection. They are intentionally excluded from the public source ZIP. Preserve their confidentiality and take a pre-deployment backup.

Set the domain's DNS A record to the server address (AAAA only if working IPv6 is configured), and allow inbound 80/443. This template assumes a direct connection to Caddy, not another CDN/proxy in front. Set this **non-secret** value in the server's root `.env`, using your actual domain:

```text
BLOOMCARE_DOMAIN=bloomcare.your-domain.example
```

The SMTP credentials from step 2 must be present in `backend/.env`. Public Compose overrides the app link origin and allowed origins to `https://YOUR_DOMAIN`, turns secure cookies on, and requires verified emails. Keep the existing generated JWT secret private and ensure assessments are enabled with the trusted local artifact.

Server commands, from the project root:

```bash
docker compose up -d --wait
```

If this is a **new empty server database**, import the verified backup before starting the public API. The following restore is for that new destination, never an existing populated service:

```bash
docker compose exec -T db sh -c 'pg_restore --exit-on-error --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < backups/before-public-1.3.0.dump
```

Start the public stack:

```bash
docker compose -f compose.public.yaml up -d --build
docker compose -f compose.public.yaml exec api python -m app.deployment_checks
```

The API applies the additive migration on startup. Caddy serves the built frontend, forwards API requests internally, provisions/renews public certificates and redirects HTTP to HTTPS when DNS/reachability prerequisites are satisfied. TLS state has persistent volumes. PostgreSQL remains on loopback and the API has no published port. Caddy overwrites forwarded client addresses; that private API/proxy boundary is part of the rate-limit configuration.

If the optional local port-8080 release stack is running, stop it with `docker compose -f compose.deploy.yaml down` before starting the public variant. Do not remove database volumes. Do not expose the private API or add another proxy without reviewing trusted forwarding settings.

At your actual HTTPS URL, check both endpoints and all three verified-email roles:

```bash
curl --fail https://YOUR_DOMAIN/api/health/live
curl --fail https://YOUR_DOMAIN/api/health/ready
```

Replace `YOUR_DOMAIN`. Check that the session cookie is HttpOnly/Secure/SameSite and that disallowed origins are rejected. Repeat report/PDF, record correction, mobile/Urdu and two-device video checks at this real origin. Preflight checks configuration, schema and model availability; it does not verify provider delivery, clinical validity or browser behavior. Docker/Caddy startup and a public certificate were not executed in this build environment.

## 5. Model acceptance and final handover

For project demonstration, keep the actual model results and coverage behavior: maternal weeks are not an input; triggered PE cannot classify 12-week data; unsupported clinical readings stay saved for doctor review. Use [MODEL-TRAINING.md](MODEL-TRAINING.md), [PE-MODEL.md](PE-MODEL.md) and the test samples. No training, metric inflation or range removal in this release establishes broader clinical support.

For real clinical deployment, the remaining model work is substantive: document the intended population/use, confirm measurement units and the actual PE outcome definition with clinical/data owners, obtain suitable permitted independent patient-level data, separate fitting/evaluation appropriately, and assess per-class errors and relevant pregnancy-duration/BP subgroups with clinical oversight. Validate prospectively/external to the historical development partitions before making diagnostic claims. This cannot be completed simply by running the updater today. Applicable service/privacy/retention requirements also need review for the actual operation.

For final operational handover:

- Keep a successful restore-test result and a matching source/model/config backup. Put protected backup copies off the server; schedule database backups and monitor failures. On Windows, Task Scheduler can invoke `scripts\database-backup.cmd backup` from the BloomCare directory while Docker is running. On the host, schedule the equivalent verified database backup job and test it. No backup schedule was installed automatically here.
- Add uptime/error monitoring for live/ready endpoints, provider failures and storage/database capacity. Verify that the person responsible can receive and act on an outage alert.
- Retain the last working release and matching database/model/config snapshot. Rehearse restoration in an isolated environment; migrations are forward-only. Never treat a source ZIP alone as a complete database recovery plan.
- Complete desktop/mobile/keyboard/Urdu and role/ownership checks on the deployed stack. Measure the expected deployed load. Earlier SQLite benchmarks do not prove production capacity.
- Record actual date, operator, URL, result and remaining issue for each check. A checkbox is checked only after that destination test passes.

The source package and automated checks are complete. Public deployment acceptance remains open until the actual server, SMTP inbox, restore and live-device results are recorded. Clinical readiness remains a separate unmet requirement.

## Reference guidance used

- [OWASP password-recovery guidance](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html): generic responses, secure single-use expiring tokens, throttling and session handling.
- [Python SMTP TLS](https://docs.python.org/3.12/library/smtplib.html).
- [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https) and [reverse-proxy headers](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
- [Uvicorn proxy trust configuration](https://uvicorn.dev/settings/).
