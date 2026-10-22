// Synthetic component-test responses; not imported by the application.
export function emptyPatientWorkspace() {
  return { counts: { records: 0, assessments: 0, reports: 0, medications: 0, unread_notifications: 0 }, records: [], care_team: [], appointments: [], urgent_reviews: [], latest_assessment: null, pregnancy: { estimated_weeks: null, trimester: null } };
}
export function emptyDoctorWorkspace() {
  return { counts: { requests: 0, confirmed: 0, patients: 0, awaiting_review: 0, urgent: 0 }, profile: { approved: true, full_name: 'Dr Example', specialty: 'Obstetrics', registration_number: 'EXAMPLE-1' }, appointments: [], priority_cases: [], analytics: { risk_categories: {}, review_statuses: {} } };
}
export function emptyAdminWorkspace() {
  return { counts: { active_accounts: 0, patients: 0, doctors: 0, pending_doctors: 0, assessments: 0, awaiting_review: 0, urgent: 0 }, pending_doctors: [], recent_activity: [], risk_categories: {}, review_statuses: {}, integrations: { database: 'CONNECTED', groq: 'NOT_CONFIGURED', whatsapp: 'NOT_CONFIGURED', video: 'DIRECT_ONLY' } };
}
