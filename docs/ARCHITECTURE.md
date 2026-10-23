# BloomCare current architecture

Release 1.3.0. The earlier incremental architecture plan is retained in `history.zip`; this page describes the implemented system.

## Runtime and source layout

| Location | Responsibility |
| --- | --- |
| `frontend/src` | React role routes/workspaces, forms, API resources, care/review, communication, PDF, translation and tests. |
| `backend/app` | FastAPI routes, validated contracts, authorization, transactions, model adapters and provider services. |
| `backend/migrations` | Forward Alembic history through `0013_account_security`; do not delete old migrations. |
| `backend/tests` | Isolated API/model/access/migration regression tests; tests never target the application database. |
| `ml` | Reproducible data contracts/trainers/verifiers, reference results, original PE JSON and current training reports. |
| `scripts` | One cumulative updater, startup/setup/diagnostics, backup, training and exact archived-file cleanup. |
| `deploy` | Optional local container images and same-origin nginx proxy; public infrastructure is separately configured. |
| `docs` | Current handover, requirements, model/verification guides and one historical archive. |

Runtime: Python 3.12, Node 24, React/Vite and PostgreSQL. Exact dependency requirements and frontend lockfile are retained. SQLite is used for isolated local verification, not presented as a production load result.

## Data and authorization

The current relational model has **31 tables**, including users/profiles, observations/model versions/assessments/PE results, appointments/selected-record links/events, notes/amendments, reports/shares, messages/consultations/signals, symptoms/medications, notifications/family grants, audit events, care guides, clinical reviews/history, follow-up proposals and WhatsApp alerts. Check `backend/app/models.py` and migrations for authoritative columns and constraints.

Patient self-service obtains ownership from the authenticated session. Website registration supports patient and doctor accounts; an admin approves doctors before clinical access. Admin account/activity permissions are separate from patient-selected clinical care grants.

An accepted, unexpired appointment grants its approved doctor access only to explicitly selected records. Cancellation, expiry, completion, rescheduling or revocation ends the relevant access. Clinical services reuse that centralized relationship policy. Family grants are separately consented, scoped, expiring and revocable.

Health observations and assessment snapshots remain immutable. A correction creates a new record; removal marks the mistaken source/results inactive with an audit reason. All active projections exclude withdrawn measurements/results, including future assistant context. Original observations, existing clinician notes and audit data remain; previously downloaded/sent external copies cannot be recalled. The original author may amend an authorized note without restoring withdrawn record access.

Reports are database-backed byte content with ownership, signature/size/quota checks and attachment downloads. A database backup therefore includes uploaded report bytes. No public upload directory is used.

## Models and provider boundaries

The registered maternal pipeline is locally trained from pinned UCI data. It has six ordered inputs, unit conversion, range checks, model/trust integrity checks and actual feature explanations. Pregnancy duration is stored but absent from the maternal feature vector.

PE is a separate, owner-authorized original forest exported into pinned non-executable JSON, with parity checks and independent extra measurements. MEDIUM/HIGH or recorded BP/history/proteinuria triggers the stage. Missing inputs, unsupported values and unavailable artifacts have distinct responses. At 12 weeks, triggered PE has no category because duration coverage is 14–40 weeks. No fallback, clipping or synthesized laboratory measurements are used.

Groq assistant and saved care guides require their respective consent and bounded context. Provider errors are explicit. WhatsApp manual sharing is a device handoff; optional Twilio alerts keep request identity and delivery state. WebRTC signaling is appointment-scoped; camera/microphone and cross-network media require real device/ICE/TURN checks.

## Reliability and operations

Writes use ownership checks, database constraints, transaction boundaries and retry identifiers where applicable. Clinical review/follow-up changes use versions; note amendments and review events preserve history. Removal atomically withdraws linked active assessments and pending proposals. Provider uncertainty is not silently retried as a new delivery.

Session cookies are HttpOnly/SameSite; public hosting requires HTTPS, secure cookies and exact origins. Access auditing records route templates rather than clinical bodies or query strings. API/web URL access logs are disabled in supplied startup/proxy configuration.

The current reminder worker is process local. Begin with one API process and review shared scheduling/locking before scaling workers. The optional container stack reuses the existing persistent PostgreSQL network and read-only model/trust mounts. Database recovery, live providers, browser behavior, public HTTPS and deployed load remain destination checks.

See [DEPLOYMENT.md](DEPLOYMENT.md), [REQUIREMENTS.md](REQUIREMENTS.md) and [VERIFICATION.md](VERIFICATION.md).


## Account lifecycle and public variant

`account_security.py` serves generic recovery/verification requests and one-use actions. Only SHA-256 token digests are persisted; action purpose, expiry, use and session version are checked. User row locks precede token locks. `auth_limits.py` uses atomic PostgreSQL/SQLite upserts with HMAC-keyed identities and persists rejected attempts. Password resets increment the user session version; existing version-zero sessions remain valid until revoked or expired.

TLS SMTP delivery uses a configured application origin, never an incoming Host header. Public link tokens use fragments, are captured into page memory then removed from the address/history, and require explicit POST confirmation. Request-time account lookup/delivery runs in background after a generic response; it is not a durable delivery queue. The public Caddy stack controls forwarded addresses and exposes no API port. A non-secret preflight checks deployment prerequisites; actual TLS/provider/media/recovery acceptance remains external.


## Free-hosting adapter (1.2.0)

Render runs one Python worker serving `/api/*` plus the built Vite SPA at the same origin. Unknown API and asset paths stay errors. Native Windows two-process startup and the optional Caddy/VPS route remain available. The Render build trains/verifies the pinned bundled maternal source and creates a local trust registry inside the image; only the original PE JSON forest is copied from source. No external pickle is accepted. PostgreSQL account/clinical/report bytes live in Neon, outside the ephemeral web-service disk.

Cloud startup derives an exact origin from Render's injected HTTPS URL, migrates schema head and optionally bootstraps an administrator only on an empty database. The owner requests a reset link to establish a password. A generated 256-bit seed derives a stable domain-separated session key. Only this public Render adapter enables the edge-overwritten CF-Connecting-IP header for auth limits; raw X-Forwarded-For is ignored. The launcher disables generic Uvicorn proxy-header trust.

Email delivery selects TLS SMTP or a fixed HTTPS Brevo endpoint. Both reuse the same one-use hashed token and session-revocation contract. Keys remain server-side. Email submission continues as an in-process background task, not a durable job queue; request a fresh link after interrupted delivery. One process hosts the reminder loop, which pauses when a free web host sleeps.

## Interface boundaries (1.3.0)

Role workspaces expose tasks, actual counts, screening categories/readings and clinician actions. Evaluation metrics, SHAP, training comparisons and setup command names are not rendered in the application. The original evidence and snapshot generation remain in developer modules/documents. Administrator oversight renders care areas and friendly outcomes; access history loads only when opened. It does not broaden clinical authorization.
