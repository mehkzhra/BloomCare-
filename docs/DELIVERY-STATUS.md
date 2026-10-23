# BloomCare delivery status

Release **1.3.0**, reviewed **22 October 2026**. This distinguishes implemented source from checks that still require the destination environment.

## v1.3.0 interface delivery

- Patient, doctor and admin pages show their own tasks. Quick actions and real saved counts make each area understandable at a glance; no invented health or reassurance score was added.
- Model accuracy/evaluation, training comparisons, class scores, SHAP and raw setup commands are removed from user screens and assessment PDF content. Source evidence and model guides remain available to maintainers.
- Plain screening notices retain the lack of clinical validation, actual readings, supported ranges, uncertain haemoglobin units and the need for doctor review. No model, clinical contract or prediction was changed.
- Services use operational availability labels, with saved settings distinguished from actual delivery. Access history is loaded on demand and shows care areas/outcomes rather than raw routes and status codes.
- All existing workflows remain accessible, including record deletion, consent, assistant history, WhatsApp sharing, video, reminders and family access. Help/About pages are role specific. Urdu translations accompany the new copy.
- `scripts\update-ui.cmd` rebuilds the current interface without database changes. The complete source also includes the earlier Windows route fix and trusted administrator retirement command.

Current automated checks: **311 backend passed + 1 PostgreSQL-only skip; 143 frontend passed; 11 ML passed**. Current browser preview was blocked by session security policy; the prior v1.2.0 visual review is not current v1.3.0 visual acceptance. See VERIFICATION.md.

## Implemented

| Area | Delivered behavior |
| --- | --- |
| Three actors | Website patient/doctor registration and sign-in; doctor approval; admin user/application/activity oversight; backend role and ownership enforcement. |
| Patient workspace | Overview, profile/due date, health-entry form, history, symptoms, medications/reminders, appointment requests and notifications. |
| Assessment | Registered six-input maternal model and preserved input/model/score/explanation snapshots for developer traceability; user-facing categories, readings and next care actions. Separate PE stage when triggered; completeness and model-range guards. |
| Clinical care | Patient-selected sharing, accepted/time-limited doctor access, review status/history, private or patient-visible notes with amendments, rescheduling and follow-up proposals. |
| Communication | Report uploads/downloads and scoped sharing, messages, WebRTC signaling and local device checks, manual WhatsApp sharing, optional Twilio alerts. |
| AI support | Separate consented Groq assistant with compact history; consented saved care-guide generation; clear timeout/provider failure states. |
| Continuing care | Family invitations/revocation, timeline, care passport/PDF, search, analytics, English/Urdu and RTL. |
| Record correction | Assessment-only withdrawal and full health-record withdrawal with linked results, reasons, audit metadata, active-view filtering and retained clinical notes. |
| Interface | Heart-and-bloom SVG logo/favicon; calm teal, blue and plum role accents; readable task-first workspaces with real care counts, on-demand details and role-specific help/about/privacy text. |
| Engineering | Forward migrations, database backup command, cumulative updater, regression suites, pinned model provenance and recorded training comparisons. |

Implementation does not by itself prove successful calls to external providers or suitability for patient diagnosis. See the executed evidence in [VERIFICATION.md](VERIFICATION.md).

## What 12 weeks means

| Step | Actual behavior |
| --- | --- |
| Save observations | `gestational_weeks=12` is accepted by the 0–45-week record contract. It is never changed to fit a model. |
| Maternal screening | Uses age, systolic/diastolic BP, glucose, temperature and heart rate. Pregnancy weeks are absent from its feature vector, so changing weeks alone does not change its category or scores. The dataset does not establish a validated prediction specifically at 12 weeks. Other measurements must still meet maternal model coverage. |
| PE with no trigger | LOW with no recorded workflow trigger leaves PE `NOT_INDICATED`; this does not rule out PE. |
| Triggered PE | MEDIUM/HIGH or recorded BP/history/proteinuria triggers open PE. At 12 weeks the stage returns `OUTSIDE_COVERAGE`: its observed duration range is 14–40 weeks. No PE category is produced, even with complete extra measurements. |
| Next step | Preserve observations and arrange clinician review. Unknown laboratory/antenatal measurements stay unknown. No inferred LOW result, clipping or invented measurements. |

Both entry and result pages now explain the distinction. Tests exercise 12-week LOW, MEDIUM, HIGH and a LOW-plus-warning case, plus inclusive 14/40-week and unsupported 45-week cases. Coverage describes this dataset, not clinical normality or diagnostic eligibility.

## Training review

The linked repository at commit `e7bce42d00a7c5813964a6b2d6f1cd5142cab518` contains the same data previously examined. Its 1,014-row maternal CSV differs from the reviewed UCI bytes only by LF/CRLF line endings. PE workbooks are exact hash matches. A second 15-row CSV supplies no documented wider coverage or independent outcome provenance.

Fresh training reproduced **71.11% maternal accuracy**, **0.6671 macro-F1** and **33.33% MEDIUM recall**, using 359 fitting/90 historical test rows and no exact measurement-group overlap. PE retraining reproduced **72.22% accuracy** on only 18 historical grouped-test rows. The original maternal row-split recipe scored **86.21%**, but **160 of its 203 test rows** matched fitting measurements. That score cannot establish independent generalization.

Active model files and trust registration were not replaced. The PE source still lacks 12-week support, systolic BP above 130, documented HB units and confirmed PE outcome definitions. Retraining the same rows cannot fix these gaps. These are reproduction results on previously evaluated partitions, not fresh external or clinical validation. Details: [MODEL-TRAINING.md](MODEL-TRAINING.md).

## Remaining before a public demonstration

| Priority | Remaining destination work | Evidence to retain |
| --- | --- | --- |
| 1 | Run the cumulative updater on Windows/PostgreSQL and check all three roles with separate accounts. | Successful updater output; matching interface/server version. |
| 2 | Choose host/domain; configure HTTPS, secure cookies, exact allowed origins and private PostgreSQL/API access. | Login/logout and protected requests over the actual HTTPS URL. |
| 3 | Back up and restore into a separate database; verify reports, notes, accounts and model/trust files after recovery. | Successful restore and application smoke test; off-host backup location/retention. |
| 4 | Check Groq with configured credentials; exercise messaging, PDF and WhatsApp handoff. Test Twilio only if automatic alerts are enabled. | Real provider success/error behavior; correct consent and delivery labels. |
| 5 | Test video on two devices/networks and configure TURN where needed. | Actual bidirectional media; device-denial and disconnection behavior. Signaling tests alone are insufficient. |
| 6 | Run mobile/desktop, keyboard and Urdu/RTL checks in browsers; verify record correction and sharing revocation. | Completed destination checklist, including downloads/native sharing. |
| 7 | Add and exercise host monitoring, backup scheduling, deployment rollback and expected-load/access checks. | Recovery/runbook and measurements on the deployed stack. |

## Account security implementation and live setup

Email verification, self-service password reset and database-backed authentication limits were implemented in v1.1.0 and are retained in v1.2.0. One-use hashed links expire, a new request supersedes the prior link, password reset revokes prior sessions, and email requests do not disclose whether an account exists. Website flows support English/Urdu. SMTP credentials are configured locally with `scripts\configure-integrations.cmd email`; actual inbox delivery still needs a live check. Local enforcement defaults off to preserve the working demonstration; the public template requires verified email and refuses a missing selected email provider.

The account feature is not an email delivery receipt. Background SMTP submission can fail or be interrupted; request a fresh link if needed. A durable mail job queue would be an improvement for a larger service, and is not claimed in this build. See [the ordered final checklist](FINALIZE-TODAY.md).

## Additional requirements for real patient use

Independent clinically defined outcome data, documented units and intended-use review are still required for a defensible medical model. Wider gestational/BP coverage requires representative data, not removed guards. Medium-class performance, prospective/external evaluation and clinical oversight need resolution. Patient information/consent, retention/erasure policies and the applicable operating requirements must be reviewed for the actual service and location. No clinical certification or legal compliance determination was made in this source review.

## Folder cleanup

The working tree now has one `START-HERE.md`, one current delivery guide, and one cumulative updater. **66 unchanged obsolete files** were removed from their former locations after their content was checked in `history.zip`: historical setup/release notes, nine superseded update commands, inactive fitted candidate JSON and detailed old comparison logs. Original architecture/verification documents were also retained inside the archive before being replaced by current guides.

The live admin evidence still reads the two required training reports; original PE JSON, maternal reference results, all tests, migrations, feature modules, dependencies and licences remain. The updater applies the same exact-hash cleanup to an existing Windows installation. It does not sweep unknown files, caches, private runtime state or locally modified legacy documents.


## v1.2.0 deployment support

`compose.public.yaml` adds a direct Caddy HTTPS frontend/private API stack, persistent TLS state and exact same-origin settings. `python -m app.deployment_checks` verifies non-secret public configuration/schema/model prerequisites without sending messages. `database-backup.cmd restore-test --file ...` restores into a generated separate database and removes it afterwards; actual PostgreSQL execution is a destination check. Monitoring, scheduled/off-host backups, rollback rehearsal and deployed load remain operational acceptance work. These templates were not built or hosted here.


## v1.2.0 free-hosting and interface delivery

- Original maternal-embrace mark shared by favicon and navigation. Original SVG maternal illustration, warm neutral background, clear role accents, and coral/blue/violet metric highlights. Clinical LOW/MEDIUM/HIGH colors retain their separate meaning.
- Patient pregnancy progress and next appointment appear together above measurements. Doctor consultation and admin activity routes get clear focus panels. Main menus remain compact, question history remains on demand, and video remains in the top bar.
- Brevo HTTPS email is available alongside existing TLS SMTP. Render Free blocks common SMTP ports; the free-hosting path explicitly chooses HTTPS. Password-reset/verification security and generic responses are preserved. Provider submission is not inbox-delivery proof.
- One-service Render Dockerfile/Blueprint builds the React frontend and reviewed maternal artifact, preserves pinned PE source/weights, migrates PostgreSQL and serves a same-origin SPA/API. No data is kept in ephemeral SQLite on the cloud path.
- An empty cloud database can bootstrap one admin with an unknown random password. Its owner explicitly requests Forgot password to establish their own password and verify the mailbox. Bootstrap cannot promote existing patient accounts.
- Render generates a 256-bit seed; the launcher derives a stable namespaced SHA-512 session key without weakening the app key policy. Render auth throttles use edge-overwritten CF-Connecting-IP; local mode ignores caller proxy headers.
- [Roman Urdu deployment steps](FREE-DEPLOYMENT.md) name every private dashboard field and explain optional versus required providers. Render/Neon limits and sleeping reminder processing are documented.

No paid resource, live URL, third-party account, real message delivery, production capacity or clinical validation is claimed. The free route is a demo/portfolio host; complete destination acceptance and separate-database restore verification before handover.
