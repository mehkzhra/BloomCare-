# BloomCare final-year submission

## Scope agreed for this submission

BloomCare is an academic maternal-care software project with patient, doctor and
administrator workspaces, saved observations, model-based screening, sharing,
consultations, reports and educational care guidance. Demonstrations use explicitly
synthetic records. Dataset-author clarification and independent hospital validation
are future work, not completed deliverables or prerequisites for showing the software.

The active legacy PE model remains range-guarded. The new CBC logistic candidate is
offline and inactive. Its 34/39 detected PE cases and 35/44 correctly classified controls
are internal held-out results, not production or clinical approval. Do not describe
the historical 90.24% score as independent accuracy: its evaluation contained overlap.

## Before the demonstration

- Keep the existing working Windows installation, private model files and database.
  Do not replace them with a clean public clone: private runtime assets are excluded.
- Back up the database using the existing backup procedure. Keep dumps and credentials
  outside GitHub and outside the submission's public materials.
- Use distinct synthetic patient, approved doctor and server-created administrator
  accounts. Never include passwords in screenshots or the project report.
- Confirm the hosted container is running, then check `/api/health/live` and
  `/api/health/ready`. Open the actual dashboard; health checks alone are insufficient.
- Keep the tested local installation ready if the external hosting/network fails.
  Local demonstration does not prove public-network availability.

## Suggested 10-minute walkthrough

| Time | Demonstration | Expected evidence |
| --- | --- | --- |
| 0–1 min | Explain problem, roles and intended academic use | Patient/doctor/admin separation |
| 1–3 min | Patient enters a labelled synthetic PE example | Saved measurements, maternal result and completed PE stage |
| 3–4 min | Open the other prepared PE sample records | Separate LOW/MEDIUM/HIGH categories from the active PE model |
| 4–5 min | Show one 12-week or out-of-coverage example | Actual values preserved, no fabricated PE result, review guidance |
| 5–6 min | Generate/open care guide and PDF report | Saved plan and readable exported report |
| 6–8 min | Share selected records and open approved doctor view | Consent-bound access, clinical review and appointment workflow |
| 8–9 min | Demonstrate a previously tested video consultation | Two participant sessions with audio/video; state the tested network setup |
| 9–10 min | Show admin approval/audit and conclude with limitations | Role control, traceability and future validation plan |

Use [the existing exact sample inputs](TEST-SAMPLES.md) and
[full PE records](examples/BloomCare-PE-Test-Samples.txt). Supported training bounds
are not healthy reference ranges. Do not alter real patient measurements to force
a result. One deliberately unsupported example demonstrates error handling rather
than concealing coverage limitations.

## Care-plan behavior in this revision

With a working provider, the application saves an AI-generated educational guide.
If the key is missing or the provider fails, it saves a labelled basic guide in
English or Urdu with `local-basic-guide-v1` provenance. Saved BP escalation remains
included. It does not invent PE results, prescribe treatment, or claim clinician approval.
Repeated requests for the same saved context return the existing plan. Hosting sleep
can still prevent the request from reaching the application.

On the admin service-status page, **Test AI connection** explicitly sends a short
non-patient test prompt and displays a safe provider result/error code. Viewing or
refreshing the page does not call Groq. The endpoint is admin-only and limited to
three attempts per minute per administrator. A successful test is a point-in-time
provider check, not proof that every care-plan request succeeds.

Patients with a saved basic guide can select **Retry AI personalization** after
renewing consent. A 30-second cooldown and in-progress guard prevent rapid repeats.
Success replaces that basic guide with the personalized text for the same saved
assessment context; provider failure keeps a basic guide. Already personalized plans
remain idempotent. This action does not modify the assessment measurements or PE result.

## Final acceptance on the deployment

Local submission verification on 29 October 2026:

| Check | Result |
| --- | --- |
| Backend pytest suite | 358 passed, 1 PostgreSQL-specific test skipped |
| Frontend Vitest suite | 166 passed across 20 files |
| ML test suite | 16 passed |
| Backend/scripts Ruff and frontend ESLint | Passed; existing import ordering corrected |
| Frontend production build | Passed |
| Three documented PE synthetic samples | Rechecked against pinned local forest: LOW, MEDIUM, HIGH as expected |

Backend tests used the isolated SQLite test database. One existing Starlette/httpx
deprecation warning remains. These results do not certify the deployment's PostgreSQL
schema, email provider or cross-network media connectivity.

These checks require the destination deployment and are not implied by local tests:

- Patient login, password-reset email delivery and expired/used link behavior.
- Doctor registration/approval and rejection of unauthorized administrator creation.
- Complete assessment with all supported PE inputs, plus one unsupported case.
- Saved care guide after provider failure; report download and WhatsApp share.
- Selected-record sharing and revocation, assessment/record correction workflow.
- Doctor review, notifications and two-session video. For a cross-network claim,
  verify TURN allocation and actual audio/video between different networks.
- Phone layout, restart persistence and an isolated backup/restore rehearsal.

## Submission contents

Use the README for setup, ARCHITECTURE.md for design, REQUIREMENTS.md for features,
TEST-SAMPLES.md for synthetic inputs, PE-MODEL.md for model evidence and limitations,
and DEPLOYMENT.md for hosting. Record test results and manual acceptance outcomes
separately; never mark a destination-browser check passed solely because unit tests pass.

## Future work

Confirm source units and measurement timing; obtain appropriately approved independent
patient data; evaluate a frozen candidate with uncertainty and calibration; conduct
clinician-supervised evaluation before any clinical-use claim. These activities are
deferred for this academic submission, not waived for later clinical deployment.
