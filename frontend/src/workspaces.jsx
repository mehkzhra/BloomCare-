import { ServiceOverview } from './service-configuration.jsx';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { t } from './i18n.js';
import { ResourceStatus, useResource } from './resources.jsx';
import { Icon, activityLabel } from './ui.jsx';
import { CategoryChart, DoctorCaseWorkspace } from './analytics-ui.jsx';

const initials = name => String(name || '').trim().split(/\s+/).slice(0, 2).map(n => n[0]).join('');
const day = value => new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
const time = value => new Date(value).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
const number = value => Number.isFinite(value) ? value.toLocaleString() : '—';
const validWorkspace = data => data && typeof data === 'object' && !Array.isArray(data) && data.counts && typeof data.counts === 'object' && Object.values(data.counts).every(n => Number.isFinite(n) && n >= 0);
const arrays = (data, keys) => keys.every(key => Array.isArray(data[key]));
const validPatientWorkspace = data => validWorkspace(data) && arrays(data, ['records', 'care_team', 'appointments', 'urgent_reviews']) && data.pregnancy && typeof data.pregnancy === 'object';
const validDoctorWorkspace = data => validWorkspace(data) && arrays(data, ['appointments', 'priority_cases']) && typeof data.profile?.approved === 'boolean' && (!data.profile.approved || data.analytics?.risk_categories && data.analytics?.review_statuses);
const validAdminWorkspace = data => validWorkspace(data) && arrays(data, ['pending_doctors', 'recent_activity']) && data.integrations && data.review_statuses && data.risk_categories;
const reviewName = status => ({ PENDING: 'Awaiting review', REVIEWED: 'Reviewed', URGENT_FOLLOW_UP: 'Urgent follow-up' })[status] || status;

function PageHeading({ eyebrow, title, children, action, emoji }) {
  return <header className="workspace-heading"><div><span className="eyebrow">{t(eyebrow)}</span><h1>{t(title)}{emoji && <span className="heading-emoji" aria-hidden="true">{emoji}</span>}</h1><p>{children}</p></div><div className="heading-actions">{action}</div></header>;
}
function Metric({ label, value, unit, detail, icon, tone = 'teal' }) {
  return <article className={'workspace-metric metric-' + tone}><div className="metric-top"><span>{t(label)}</span><span className="metric-icon"><Icon name={icon} size={19} /></span></div><strong>{value ?? '—'}{unit && <small>{t(unit)}</small>}</strong><span className="metric-detail">{t(detail)}</span></article>;
}
function PanelHeading({ title, eyebrow, to, action = 'View all' }) {
  return <div className="panel-heading"><div>{eyebrow && <span className="eyebrow">{t(eyebrow)}</span>}<h2>{t(title)}</h2></div>{to && <Link className="text-link" to={to}>{t(action)}<Icon name="arrow" size={15} /></Link>}</div>;
}
function Empty({ icon = 'calendar', title, children, to, action }) {
  return <div className="workspace-empty"><span><Icon name={icon} size={23} /></span><h3>{t(title)}</h3><p>{t(children)}</p>{to && <Link className="button secondary" to={to}>{t(action)}<Icon name="arrow" size={15} /></Link>}</div>;
}
function WorkspaceStatus({ resource }) {
  if (resource.loading) return <div className="workspace-skeleton" role="status"><span className="sr-only">{t('Loading your workspace…')}</span><i /><i /><i /></div>;
  return <ResourceStatus resource={resource} />;
}
function StepLink({ icon, title, description, to, tone = '' }) {
  return <Link className={'step-link ' + tone} to={to}><span className="step-icon"><Icon name={icon} /></span><span><strong>{t(title)}</strong><small>{t(description)}</small></span><Icon name="arrow" size={16} /></Link>;
}
function QuickActions({ role }) {
  const actions = role === 'patient' ? [
    ['heart', 'Save your measurements', 'Keep your health record up to date', '/patient/health'],
    ['calendar', 'Book a doctor', 'Choose a time and what to share', '/patient/appointments'],
    ['chat', 'Ask a question', 'Find clarity with your assistant', '/patient/assistant'],
  ] : role === 'doctor' ? [
    ['calendar', 'Manage your schedule', 'Respond to requests and view visits', '/doctor/appointments'],
    ['assessment', 'Review shared records', 'Read results and leave care instructions', '/doctor/cases'],
    ['video', 'Meet your patient', 'Open an accepted video appointment', '/doctor/consultations'],
  ] : [
    ['shield', 'Review doctor applications', 'Check registration and approve access', '/admin/accounts?role=doctor&approval=pending&active=true'],
    ['users', 'Manage people', 'Find patient and doctor accounts', '/admin/accounts'],
    ['overview', 'Follow care activity', 'View appointments and review progress', '/admin/oversight'],
  ];
  return <nav className="quick-actions" aria-label={t('Quick actions').trim()}>{actions.map(([icon, title, text, to]) =>
    <Link to={to} className="quick-action" key={to}><span className="quick-action-icon"><Icon name={icon} size={22} /></span><span><strong>{t(title)}</strong><small>{t(text)}</small></span><Icon name="arrow" size={16} /></Link>
  )}</nav>;
}

function PregnancyProgress({ pregnancy }) {
  const weeks = pregnancy?.estimated_weeks;
  const known = Number.isFinite(weeks);
  const progress = known ? Math.min(Math.max(weeks / 40, 0), 1) : 0;
  return <section className="pregnancy-summary"><div className="progress-ring"><svg viewBox="0 0 120 120" aria-hidden="true"><circle cx="60" cy="60" r="49" /><circle cx="60" cy="60" r="49" strokeDasharray={`${progress * 308} 308`} /></svg><span><strong>{known ? weeks : '—'}</strong><small>{t('weeks')}</small></span></div><div><span className="eyebrow">{t('YOUR PREGNANCY')}</span><h2>{known ? `${t('Trimester')} ${pregnancy.trimester}` : t('Make this space yours')}</h2><p>{t(known ? 'Estimated from your saved pregnancy dates.' : 'Add your due date to follow your pregnancy progress.')}</p><Link className="text-link" to={known ? '/patient/timeline' : '/patient/profile'}>{t(known ? 'Open pregnancy timeline' : 'Add your due date')}<Icon name="arrow" size={15} /></Link></div></section>;
}
function NextAppointment({ appointment }) {
  return <section className="workspace-panel next-appointment-panel"><PanelHeading title="Your next appointment" to="/patient/appointments" />{appointment ? <><div className="next-appointment-date"><span>{day(appointment.scheduled_at)}</span><strong>{time(appointment.scheduled_at)}</strong><small>{t(appointment.status === 'ACCEPTED' ? 'Confirmed' : 'Awaiting confirmation')}</small></div><div className="person-line"><span className="person-avatar" aria-hidden="true">{initials(appointment.doctor_name)}</span><div><strong>{appointment.doctor_name}</strong><small>{t('Your care team')}</small></div></div><Link className="button" to={appointment.status === 'ACCEPTED' && appointment.record_access_available ? `/patient/appointments/${appointment.id}/consultation` : '/patient/appointments'}><Icon name={appointment.record_access_available ? 'video' : 'calendar'} size={17} />{t(appointment.status === 'ACCEPTED' && appointment.record_access_available ? 'Open consultation' : 'View appointments')}</Link></> : <Empty title="A conversation can help" to="/patient/appointments" action="Book an appointment">Request a time with an approved doctor and choose what to share.</Empty>}</section>;
}

export function PatientWorkspace({ user }) {
  const resource = useResource('/patients/me/workspace', { validate: validPatientWorkspace });
  const data = resource.data, counts = data?.counts;
  const records = data?.records || [], latest = records[0], observations = latest?.observations;
  const assessment = data?.latest_assessment;
  const urgent = data?.urgent_reviews || [];
  const team = data?.care_team || [];
  return <div className="role-workspace patient-workspace stack">
    <PageHeading emoji="🌷" eyebrow="YOUR PERSONAL CARE SPACE" title="Your health, at a glance." action={<Link className="button" to="/patient/health"><Icon name="plus" size={17} />{t('Add health record')}</Link>}>{t('Welcome back,')}{user?.full_name?.trim().split(/\s+/)[0] || t('welcome')}. {t('Your records, your appointments, your next step.')}</PageHeading>
    <WorkspaceStatus resource={resource} />
    {data && <>
      {urgent.length > 0 && <section className="review-attention" aria-label={t('Care team follow-up')}><Icon name="shield" size={22} /><div><strong>{t('Your doctor requested a follow-up')}</strong><p>{urgent[0].clinical_review.reason}</p></div><Link className="button secondary" to={'/patient/assessments/' + urgent[0].health_record_id}>{t('Read review')}<Icon name="arrow" size={16} /></Link></section>}
      <QuickActions role="patient" /><div className="care-highlights"><PregnancyProgress pregnancy={data.pregnancy} /><NextAppointment appointment={data.appointments[0]} /></div>
      <div className="workspace-metrics three"><Metric label="Last blood pressure" value={observations ? `${observations.systolic_mmhg}/${observations.diastolic_mmhg}` : '—'} unit="mmHg" detail={latest ? `${t('Recorded')} ${day(latest.created_at)}` : 'No observations saved yet'} icon="heart" /><Metric label="Last blood glucose" value={observations ? Number((observations.glucose_mmol_l * 18).toFixed(1)) : '—'} unit="mg/dL" detail="From your latest health record" icon="assessment" tone="blue" /><Metric label="Your health records" value={number(counts.records)} detail="Saved securely in your account" icon="report" tone="coral" /></div>
      <div className="workspace-layout patient-layout"><div className="workspace-primary stack">
        <section className="workspace-panel"><PanelHeading title="Your latest assessment" eyebrow="KNOW YOUR NEXT STEP" to="/patient/assessments" />{assessment ? <><div className="assessment-overview"><div><span className={`risk-badge risk-${assessment.maternal_risk.toLowerCase()}`}>{t(assessment.maternal_risk)}</span><p>{t('Maternal screening category')} · {day(assessment.created_at)}</p></div><span className="subtle-tag">{t(reviewName(assessment.clinical_review?.status || 'PENDING'))}</span></div><div className="assessment-step-line"><span className="step-icon"><Icon name="assessment" /></span><div><strong>{t(assessment.pe_status === 'COMPLETED' ? 'PE screening saved' : assessment.pe_status === 'AWAITING_INPUTS' ? 'Complete your PE measurements' : assessment.pe_status === 'OUTSIDE_COVERAGE' ? 'Some readings need clinician review' : 'Your assessment is saved')}</strong><p>{t(assessment.pe_status === 'COMPLETED' ? 'Open the assessment to view both screening stages and your care guide.' : assessment.pe_status === 'OUTSIDE_COVERAGE' ? 'Your readings are saved. Open the assessment to arrange a doctor review.' : 'Open your saved assessment for the result, care guide and next steps.')}</p></div></div><div className="panel-footer"><Link className="text-link" to={'/patient/assessments/' + assessment.health_record_id}>{t('Open assessment')}<Icon name="arrow" size={16} /></Link><small>{t('Screening supports a conversation with your clinician.')}</small></div></> : <Empty icon="assessment" title="Start with one clear record" to="/patient/health" action="Add health observations">Save your measurements, see your screening result and choose your next care step.</Empty>}</section>
        <section className="workspace-panel"><PanelHeading title="Recent observations" to="/patient/history" action="View your history" />{records.length ? <div className="workspace-table-wrap"><table className="workspace-table"><thead><tr><th>{t('Recorded')}</th><th>{t('Blood pressure')}</th><th>{t('Blood glucose')}</th><th><span className="sr-only">{t('Open record')}</span></th></tr></thead><tbody>{records.slice(0, 4).map(r => <tr key={r.id}><td><strong>{day(r.created_at)}</strong><small>{time(r.created_at)}</small></td><td>{r.observations.systolic_mmhg}/{r.observations.diastolic_mmhg}<small>mmHg</small></td><td>{Number((r.observations.glucose_mmol_l * 18).toFixed(1))}<small>mg/dL</small></td><td><Link className="table-action" aria-label={t('Open record') + ' ' + day(r.created_at)} to={'/patient/assessments/' + r.id}><Icon name="arrow" size={17} /></Link></td></tr>)}</tbody></table></div> : <p className="empty-inline">{t('Your saved observations will appear here.')}</p>}</section>
      </div><aside className="workspace-secondary stack">
        <section className="workspace-panel assistant-prompt"><span className="assistant-symbol"><Icon name="chat" size={25} /></span><h2>{t('Questions about your care?')}</h2><p>{t('Ask a question or talk through selected records with your assistant.')}</p><Link className="text-link" to="/patient/assistant">{t('Open assistant')}<Icon name="arrow" size={16} /></Link><small>{t('A separate space for questions, with your permission.')}</small></section>
        <section className="workspace-panel"><PanelHeading title="Your care team" to="/patient/appointments" action="Find a doctor" />{team.length ? team.map(doctor => <div className="person-line" key={doctor.id}><span className="person-avatar" aria-hidden="true">{initials(doctor.full_name)}</span><div><strong>{doctor.full_name}</strong><small>{doctor.specialty}</small></div><Link className="table-action" aria-label={t('Request an appointment') + ' ' + doctor.full_name} to={'/patient/appointments?doctor=' + doctor.id}><Icon name="arrow" size={16} /></Link></div>) : <p className="empty-inline">{t('No approved doctors have been added yet.')}</p>}</section>
      </aside></div>
      <details className="workspace-panel care-extras"><summary><Icon name="plus" size={18} />{t('More for your care')}<span>{t('Reports, reminders and family access')}</span></summary><section className="workspace-shortcuts"><StepLink icon="report" title="Medical reports" description={`${number(counts.reports)} ${t('saved documents')}`} to="/patient/reports" /><StepLink icon="clock" title="Medications & reminders" description="Keep your prescribed routine together" to="/patient/reminders" /><StepLink icon="users" title="Family access" description="Choose who can follow your care" to="/patient/family" /></section></details>
    </>}
  </div>;
}

export function DoctorWorkspace() {
  const resource = useResource('/doctors/me/workspace', { validate: validDoctorWorkspace });
  const [casesOpen, setCasesOpen] = useState(false);
  const data = resource.data, profile = data?.profile, counts = data?.counts;
  return <div className="role-workspace doctor-workspace stack"><PageHeading emoji="☀️" eyebrow="YOUR PRACTICE" title="Your practice, in focus." action={<Link className="button" to="/doctor/appointments"><Icon name="calendar" size={17} />{t('Manage appointments')}</Link>}>{profile ? `${profile.full_name} · ${profile.specialty}` : t('A clear view of your appointments, shared records and follow-ups.')}</PageHeading><WorkspaceStatus resource={resource} />
    {data && <>{!profile.approved ? <section className="workspace-panel approval-pending"><Icon name="shield" size={30} /><h2>{t('Your registration is being reviewed')}</h2><p>{t('Awaiting admin approval. Patient access and appointment handling are unavailable until approval.')}</p><span className="subtle-tag">{t('Registration:')}{profile.registration_number}</span></section> : <>
      <QuickActions role="doctor" /><section className="workspace-focus"><span className="focus-symbol"><Icon name="video" size={28} /></span><div><span className="eyebrow">{t("CARE IN FOCUS")}</span><h2>{t("Care priorities, made clear.")}</h2><p>{counts.requests > 0 ? <>{number(counts.requests)} {t('appointment requests are waiting for your response.')}</> : counts.awaiting_review > 0 ? <>{number(counts.awaiting_review)} {t('shared assessments are waiting for your review.')}</> : t('Open your schedule to prepare for the next patient conversation.')}</p></div><Link className="button secondary" to={counts.requests > 0 ? '/doctor/appointments' : counts.awaiting_review > 0 ? '/doctor/cases' : '/doctor/consultations'}>{t(counts.requests > 0 ? 'Review requests' : counts.awaiting_review > 0 ? 'Review assessments' : 'Open video workspace')}<Icon name="arrow" size={16} /></Link></section>
      <div className="workspace-metrics four"><Metric label="Appointment requests" value={number(counts.requests)} detail="Waiting for your response" icon="calendar" tone="coral" /><Metric label="Confirmed consultations" value={number(counts.confirmed)} detail="Upcoming accepted appointments" icon="video" tone="blue" /><Metric label="Patients sharing records" value={number(counts.patients)} detail="People with active record sharing" icon="users" /><Metric label="Assessments to review" value={number(counts.awaiting_review)} detail="Among currently shared records" icon="assessment" tone="violet" /></div>
      <div className="workspace-layout clinician-layout"><section className="workspace-panel"><PanelHeading title="Upcoming consultations" to="/doctor/appointments" action="View appointments" />{data.appointments.length ? data.appointments.map(a => <article className="consultation-row" key={a.id}><div className="schedule-time"><strong>{time(a.scheduled_at)}</strong><span>{day(a.scheduled_at)}</span></div><div className="person-line"><span className="person-avatar" aria-hidden="true">{initials(a.patient_name)}</span><div><strong>{a.patient_name}</strong><small>{a.reason}</small></div></div><span className={'status-pill status-' + a.status.toLowerCase()}>{t(a.status === 'ACCEPTED' ? 'Confirmed' : 'Requested')}</span><Link className="table-action" aria-label={t(a.record_access_available ? 'Open patient review' : a.status === 'PENDING' ? 'Manage request' : 'Manage appointment') + ' ' + a.patient_name} to={a.record_access_available ? '/doctor/appointments/' + a.id : '/doctor/appointments'}><Icon name="arrow" size={17} /></Link></article>) : <Empty title="Your schedule is clear">Upcoming appointment requests and accepted consultations will appear here.</Empty>}</section>
        <section className="workspace-panel"><PanelHeading title="Reviews that need attention" eyebrow="CARE PRIORITIES" />{data.priority_cases.length ? data.priority_cases.map(row => <Link className="priority-case" to={'/doctor/appointments/' + row.appointment_id} key={row.assessment.id}><span className={'priority-marker ' + (row.assessment.clinical_review?.status === 'URGENT_FOLLOW_UP' ? 'is-urgent' : '')} /><span><strong>{row.patient_name}</strong><small>{t(reviewName(row.assessment.clinical_review?.status || 'PENDING'))} · {day(row.assessment.created_at)}</small></span><span className={`risk-badge risk-${row.assessment.maternal_risk.toLowerCase()}`}>{t(row.assessment.maternal_risk)}</span><Icon name="arrow" size={15} /></Link>) : <Empty icon="shield" title="No outstanding review in this view">Only records shared through active accepted appointments are included.</Empty>}<p className="scope-note"><Icon name="shield" size={14} />{t('Your access follows each patient’s sharing choices.')}</p></section>
      </div><div className="workspace-chart-grid"><section className="workspace-panel"><CategoryChart data={data.analytics.risk_categories} title="Maternal screening categories" /><p className="scope-note">{t('From active, patient-selected assessment records.')}</p></section><section className="workspace-panel"><CategoryChart data={data.analytics.review_statuses} title="Review progress" /><p className="scope-note">{t('Review status reflects saved clinician decisions.')}</p></section></div>
      <details className="workspace-panel workspace-disclosure" onToggle={e => setCasesOpen(e.currentTarget.open)}><summary><span><strong>{t('Find a patient assessment')}</strong><small>{t('Search and filter your currently shared cases')}</small></span><Icon name="plus" size={20} /></summary>{casesOpen && <DoctorCaseWorkspace />}</details>
    </>}</>}
  </div>;
}

export function AdminWorkspace() {
  const resource = useResource('/admin/workspace', { validate: validAdminWorkspace });
  const data = resource.data, counts = data?.counts;
  return <div className="role-workspace admin-workspace stack"><PageHeading emoji="🌿" eyebrow="PEOPLE & CARE" title="BloomCare administration" action={<Link className="button" to="/admin/accounts"><Icon name="users" size={17} />{t('Manage accounts')}</Link>}>{t('People, care activity and the services that keep them connected.')}</PageHeading><WorkspaceStatus resource={resource} />
    {data && <><QuickActions role="admin" /><section className="workspace-focus"><span className="focus-symbol"><Icon name="users" size={28} /></span><div><span className="eyebrow">{t("PEOPLE & CARE")}</span><h2>{t(counts.pending_doctors > 0 ? 'New doctors are waiting to join.' : 'Your care community, at a glance.')}</h2><p>{counts.pending_doctors > 0 ? <>{number(counts.pending_doctors)} {t('applications need your approval before doctors can see patients.')}</> : t('Follow account activity, appointment requests and saved reviews.')}</p></div><Link className="button secondary" to="/admin/oversight">{t("View care activity")}<Icon name="arrow" size={16} /></Link></section><div className="workspace-metrics four"><Metric label="Active accounts" value={number(counts.active_accounts)} detail={`${number(counts.patients)} ${t('patients')} · ${number(counts.doctors)} ${t('doctors')}`} icon="users" tone="violet" /><Metric label="Doctor approvals" value={number(counts.pending_doctors)} detail="Applications waiting for review" icon="shield" tone="coral" /><Metric label="Saved assessments" value={number(counts.assessments)} detail={`${number(counts.awaiting_review)} ${t('awaiting clinician review')}`} icon="assessment" tone="blue" /><Metric label="Urgent follow-ups" value={number(counts.urgent)} detail="Flagged by a reviewing clinician" icon="heart" tone={counts.urgent > 0 ? 'urgent' : 'teal'} /></div>
      <div className="workspace-layout admin-layout"><section className="workspace-panel"><PanelHeading title="Doctor applications" eyebrow="ACCESS & APPROVALS" to="/admin/accounts?role=doctor&approval=pending&active=true" action="Review applications" />{data.pending_doctors.length ? data.pending_doctors.map(doctor => <article className="application-row" key={doctor.id}><span className="person-avatar avatar-violet" aria-hidden="true">{initials(doctor.full_name)}</span><div><strong>{doctor.full_name}</strong><small>{doctor.specialty} · {doctor.registration_number}</small><span>{doctor.email}</span></div><Link className="button secondary small-button" to={'/admin/accounts?q=' + encodeURIComponent(doctor.email) + '&role=doctor'}>{t('Review')}</Link></article>) : <Empty icon="shield" title="Applications are up to date">New active doctor applications appear here for your review.</Empty>}</section>
        <section className="workspace-panel"><PanelHeading title="Service availability" eyebrow="CONNECTED SERVICES" /><ServiceOverview data={data} /></section>
      </div><div className="workspace-chart-grid"><section className="workspace-panel"><CategoryChart data={data.risk_categories} title="Maternal screening categories" /><p className="scope-note">{t('All saved assessments; counts are not unique patients.')}</p></section><section className="workspace-panel"><CategoryChart data={data.review_statuses} title="Assessment review progress" /><p className="scope-note">{t('Includes assessments waiting for their first clinician review.')}</p></section></div>
      <section className="workspace-panel"><PanelHeading title="Recent account activity" to="/admin/oversight" action="View all activity" />{data.recent_activity.length ? data.recent_activity.map(event => <article className="activity-row" key={event.id}><span className="activity-marker" /><div><strong>{event.actor}</strong><span>{t(activityLabel(event.action))}</span></div><time dateTime={event.created_at}>{day(event.created_at)} · {time(event.created_at)}</time></article>) : <p className="empty-inline">{t('Account activity will appear here as people use BloomCare.')}</p>}</section>
    </>}
  </div>;
}
