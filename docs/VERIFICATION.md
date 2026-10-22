# BloomCare 1.2.0 executed verification

21 October 2026. This records executed local checks separately from destination/provider acceptance. No credentials, patient data, real messages, public deployment or clinical validation are represented by these results.

| Check | Result |
| --- | --- |
| Full backend regression | **294 passed; 1 PostgreSQL-only test skipped**, isolated SQLite. Covers existing authorization/clinical flows and new cloud email, key derivation, proxy identity, bootstrap and SPA behavior. |
| Frontend regression | **139 passed**, including record removal, assessment/PE UI, auth recovery, session retry, role workspaces, compact history and Urdu actions. |
| ML regression | **11 passed**. Reviewed data and split contract preserved. |
| Python / frontend lint | Passed, including new deployment Python scripts. |
| Vite production build | Passed. Version 1.2.0. |
| Original PE integrity | Pinned forest, column mapping and reference scores passed; original forest/weights unchanged. |
| Cloud model build stage | Fresh isolated build from the bundled checksum-pinned UCI fixture. Recorded evaluation replay, non-overlapping split, trust hashes and actual maternal SHAP inference passed. Original PE forest/manifest/explanation weights verified as included. This is Python-stage evidence, not a Docker-host execution. |
| Schema | No new schema change; head remains **0013_account_security**, 31 tables. Populated historical migration and Alembic parity are carried-forward v1.1.0 evidence. |
| Windows ZIP | Cumulative source packaging, per-file SHA-256 and protected-file overlay checks; see DELIVERY-MANIFEST.json. Secrets/runtime/dependencies excluded. |

## UI review

Supervised Chrome preview reviewed the public welcome/sign-in and all three role workspaces using **synthetic test responses**. The temporary review entry points are removed from the delivery. They are not an alternate product login or production API. No provider/account action was performed.

The patient pregnancy summary and next consultation are prominent, doctor/admin focus panels are readable, the same maternal mark is used in brand and favicon, clinical category colors remain separate, and secondary care tools/history stay on demand. A narrow patient care-team heading overflow was found and corrected. Mobile patient, doctor and admin layouts were inspected; patient Urdu/RTL, menu opening and Escape dismissal were also checked. This is visual/interaction evidence, not a complete browser-based clinical workflow or device-media test. Screenshots are internal QA only.

## Limits and remaining acceptance

Native Windows/PostgreSQL updater execution, real backup restore, Render/Docker/Caddy runtime, live Neon credentials, public HTTPS/cookie/proxy acceptance, real Brevo/SMTP inbox, Groq/Twilio delivery and two-device camera/microphone/TURN still require the destination environment and owner-controlled provider accounts. No host URL has been provisioned here. Follow FREE-DEPLOYMENT.md for free provider-subdomain setup and FINALIZE-TODAY.md for the Windows/restore/VPS acceptance steps.

Render Free sleeps when idle and has resource/usage limits; the process-local reminder loop cannot deliver while the app sleeps. Clinical validation, PE outcome/units/coverage and independent external evaluation remain unresolved. UI changes and hosting do not change those model properties.
