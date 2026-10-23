export const privacyContent = {
  patient: {
    heading: 'Your records, your choices.',
    description: 'Manage who can see your information and what leaves BloomCare.',
    actions: [['Review appointment sharing', '/patient/appointments'], ['Manage family access', '/patient/family'], ['Manage assessments', '/patient/assessments']],
    sections: [
      ['Choose what your doctor sees', 'Select health records for an appointment. An approved doctor can read them only through an accepted appointment with active access. Closing the appointment or letting access expire ends that access.'],
      ['Reports and copies', 'Manage uploaded reports separately from selected health records. Before sharing a PDF through WhatsApp or another app, check the recipient. Copies already downloaded or sent cannot be recalled by BloomCare.'],
      ['Assistant and care-guide consent', 'The assistant sends your question to Groq after consent. Record context is optional. A care guide sends the selected assessment measurements and results; your name, email and passwords are excluded.'],
      ['Optional care alerts', 'Automatic WhatsApp alerts use Twilio and an approved, opted-in contact. They send a screening category and PE stage. Delivery is confirmed only when the provider reports it. Manual PDF sharing remains a separate choice.'],
      ['Family access you control', 'Choose the record categories a family member can view. While a grant is active, later entries in those categories are included. You can revoke the grant from Family.'],
      ['Correct your records', 'Delete an individual result from Assessment history. To remove wrong measurements and their linked results, open Health history and choose Delete health record. Confirm with a reason. Removed records leave active sharing, charts and future assistant context. Clinician notes and an audit copy remain; previously sent copies cannot be recalled. Add a new record for corrected measurements.'],
    ],
  },
  doctor: {
    heading: 'Patient trust, clear boundaries.',
    description: 'Your practice workspace follows each patient’s active consent.',
    actions: [['Review accepted appointments', '/doctor/appointments'], ['Open shared assessments', '/doctor/cases']],
    sections: [
      ['Access starts with patient consent', 'Your registration must be approved. Read only the records a patient selected for an accepted appointment with active access. Pending appointments do not grant clinical access.'],
      ['Access has an end', 'Clinical access ends when the appointment closes, its grant expires or approval is revoked. Ask the patient for a new care episode when further access is needed.'],
      ['Notes and corrections', 'Choose whether a note is visible to the patient. Amend a saved note with a reasoned correction; the original remains in its audit chain. Private notes are excluded from patient assessment PDF exports.'],
      ['Use shared copies carefully', 'An assessment PDF contains patient information. Obtain permission before sharing it outside the care team. BloomCare cannot recall a downloaded file or a copy sent through WhatsApp.'],
      ['Removed assessments', 'A patient can mark a mistaken assessment for deletion. It leaves active shared cases and cannot receive new reviews, care guides or assessment exports. Existing clinician notes remain and show that their linked result was removed.'],
      ['Consultation privacy', 'Only confirmed participants with active appointment access can join. Camera and microphone permission is requested on the device. BloomCare does not record the call.'],
    ],
  },
  admin: {
    heading: 'Access you can account for.',
    description: 'Oversee accounts, approvals and care activity with clear responsibility.',
    actions: [['Manage account access', '/admin/accounts'], ['Review audit activity', '/admin/oversight'], ['Review connected services', '/admin/services']],
    sections: [
      ['Verify doctors before approval', 'Check registration details before enabling doctor access. Revoking approval or disabling an account blocks its protected workflows. These changes are recorded in account activity.'],
      ['Administrative oversight', 'Review account lists, appointment metadata, clinical review status, aggregate trends and audit events. Detailed clinical records, files and notes use the patient and approved-doctor access routes.'],
      ['Connected care services', 'Check service availability and report any unavailable feature to the person maintaining BloomCare. Confirm an actual email, alert, assistant reply or video call before relying on it.'],
      ['Patient choices stay in force', 'Patients choose appointment records, report grants, family categories and provider consent. Do not treat account administration as permission to send or export their health information.'],
      ['Corrections and retention', 'Deleted assessments are excluded from active results and analytics. A dated reason and the original audit copy remain for accountability. Existing external copies and backups require separate retention handling.'],
      ['Handover responsibility', 'Protect server configuration and backups. Before public deployment, verify HTTPS, account permissions and your organisation’s retention and privacy requirements.'],
    ],
  },
  public: {
    heading: 'Clear choices for connected care.',
    description: 'Sign in to see the privacy controls and responsibilities for your account.',
    actions: [['Sign in to your account', '/login']],
    sections: [
      ['Role-based access', 'Patients manage their records and sharing. Approved doctors access selected records through active accepted appointments. Administrators oversee accounts, approvals, service availability and access activity.'],
      ['Sharing needs a choice', 'Assistant questions, care-guide generation and automatic care alerts ask for consent. A PDF shared outside BloomCare becomes a separate copy that cannot be recalled here.'],
      ['Saved history and corrections', 'Mistaken assessments can be removed from active history with a reason. An audit copy is retained. Ask your BloomCare administrator about the organisation’s privacy and retention policy.'],
    ],
  },
};
