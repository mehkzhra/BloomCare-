# BloomCare review walkthrough

Use separate browser profiles for patient, doctor and admin so each session retains
its own role. Use existing private credentials or create named demonstration
accounts locally; passwords and real patient records are not supplied in this ZIP.

## A five-to-ten-minute product tour

1. **Start as a patient.** Show the overview's useful empty state, profile/due date,
   one health-record form, unit conversion and faint coverage hints. Once records
   exist, show real totals and the latest measurements rather than fixed demo
   numbers. Unknown measurements and dates remain blank.
2. **Complete a care episode.** Request an approved doctor, explicitly choose the
   records to share and confirm consent. Switch to doctor, accept and review the
   selected assessment. The doctor overview shows only active shared records.
3. **Review and follow up.** Save a review status/reason, add a patient-visible note,
   append an amendment and propose a follow-up time. Show the patient notification,
   immutable history and patient acceptance before another booking is made.
4. **Use the report.** Open the saved care guide with consent, download its PDF and
   use the external share action. Explain delivery honestly: a share handoff is not
   a WhatsApp delivery receipt. Show a completed supported PE result or the exact
   unsupported-field table; actual measurements are not edited to fit the model.
5. **Manage the service.** Switch to admin. Review pending doctor applications,
   the People/Appointments/Activity tabs, access-change confirmation, current
   configuration and corrected review counts. Configuration flags are distinct
   from a successful live provider call.
6. **Inspect the engineering evidence.** Open model evaluation and executed
   retraining. Explain why the tested weaker candidates were not promoted. Review
   the tests, source manifest and bounded performance report. Walk through role
   denial and grant revocation using separate accounts.

Optional modules remain reachable: English/Urdu and RTL, report upload, appointment
messages, symptoms, medications/reminders, timeline, family invitations, passport
and video. Check video with two actual devices; signaling tests are not a media
delivery demonstration.

## What the project demonstrates

| Software quality | Concrete evidence |
| --- | --- |
| Functional completeness | Three role workspaces and the full care-record/appointment/review/report flow. |
| Usability | Clear primary actions, actionable empty/error states, compact role-specific information, contextual PE coverage errors and keyboard-operable administration. |
| Privacy and access | Server-side ownership, approved doctor access, patient-selected grants, expiry/revocation, protected admin metrics and route-template auditing. |
| Reliability | Idempotent writes/provider requests, version checks, immutable review/note history, explicit delivery uncertainty and read-only training evidence. |
| Performance | Aggregate dashboard projections, feature code splitting, cached model loading, bounded provider timeouts and an executed synthetic authenticated benchmark. |
| Accessibility | Native controls/labels, focus restoration for access confirmation, keyboard tabs/navigation, reduced motion, Urdu/RTL and checked representative colour pairs. Full browser/assistive-technology certification is not claimed. |
| Maintainability | Separated API/services/UI modules, reproducible ML contracts, explicit model provenance, migrations, a cumulative updater and regression tests. |
| Portability | Windows CMD scripts and optional container templates; local fonts/PDF runtime and archived portable inactive forest evidence. |

The model's data/accuracy limits remain a material limitation. Demonstrate the
application as connected screening and care-workflow software, with its measured
evidence; do not describe it as a clinically certified diagnostic system or claim
that every SRS performance target has been proven.


Current delivery: **1.0.3**. Add a 12-week demonstration: the source duration stays 12, maternal scores do not depend on it, and a triggered PE stage displays its unsupported duration without creating a category. Demonstrate health-record deletion with linked-result withdrawal, retained notes and on-demand metadata. Current verification and deployment gaps are in [VERIFICATION.md](VERIFICATION.md) and [DELIVERY-STATUS.md](DELIVERY-STATUS.md).
