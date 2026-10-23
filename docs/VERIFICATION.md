# BloomCare 1.3.0 executed verification

22 October 2026. Current checks use isolated synthetic test data, mocked providers and the bundled model fixtures. These results do not represent live hosting, actual inbox delivery, native Windows acceptance or clinical validation.

| Check | Executed result |
| --- | --- |
| Backend regression | **311 passed; 1 PostgreSQL-only check skipped** on isolated SQLite. Includes the earlier Windows path-separator fix, safe administrator retirement, account recovery, consent and access enforcement. |
| Frontend regression | **143 passed** across 17 suites. Includes the assessment and PE flows, deletion, sharing, role-specific help, absence of developer panels, on-demand history and readable access outcomes. |
| ML regression | **11 passed**. No model or clinical input contract changed. |
| Python and frontend lint | Passed. |
| Production frontend build | Passed, version **1.3.0**. |
| Original PE integrity | Forest, feature mapping and reference-score checks passed. |
| PDF exports | Three synthetic English/Urdu/unsupported-reading reports generated. All nine rendered pages inspected; no body-margin overflow detected. Actual readings, care guides and patient-visible notes retained; model versions, raw scores, SHAP and provider-model metadata absent. |
| Schema | Unchanged at **0013_account_security**, 31 tables. No migration required from the working 1.2.0 installation. |
| Archive | Full cumulative source, per-file checksums, prior-version overlay and protected runtime-file checks. See DELIVERY-MANIFEST.json. |

## Current interface review limits

The current cloud browser refused the local preview under its session security policy. No alternate browser surface or policy workaround was used. **A current desktop/mobile visual acceptance review is still required on the user's Windows installation.** The supervised Chrome review described by the prior 1.2.0 release applies only to that older interface.

Current 1.3.0 validation includes component-level role/navigation/form checks, responsive CSS/build inspection, readable real-data category bars, plain-language copy and native SVG validation. It is not a claim that this version was visually inspected in a running browser. Temporary fixture preview entries are removed from the delivery. PDF rendering was reviewed independently with the actual export implementation.

## Destination checks that remain

Native Windows/PostgreSQL full updater, actual backup restore, real Brevo/SMTP inbox, Groq/Twilio delivery, real two-device video and restrictive-network connectivity, public HTTPS/cookies/origins, hosting resources and clinical/external validation still need the destination environment. No public host or provider account was created by this interface update.

For this already-working local installation, use `scripts\update-ui.cmd`, then `scripts\start-local.cmd` and open `http://127.0.0.1:8000`. The interface updater does not change the database or saved environment. Keep the existing local PostgreSQL container running when that is your configured database.
