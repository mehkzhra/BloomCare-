import { ResourceStatus, useResource } from './resources.jsx';
export { ResourceStatus, useResource } from './resources.jsx';
import { t } from "./i18n.js";
import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { api } from './api.js';
import { Icon } from './ui.jsx';
import { PatientWorkspace, DoctorWorkspace, AdminWorkspace } from './workspaces.jsx';
import { RecordFilters } from './search-ui.jsx';
import { HealthRecordRemoval, RemovedHealthRecords } from './assessment-removal.jsx';
export function PatientPage({ user }) {
  const capabilities = useResource('/capabilities');
  return <div className="stack"><PatientWorkspace user={user} /><ModelAvailability resource={capabilities} /></div>;
}
export function ProfilePage() {
  const resource = useResource('/patients/me/profile');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    setError('');
    const body = Object.fromEntries(new FormData(event.currentTarget));
    for (const key of ['date_of_birth', 'due_date', 'phone']) body[key] = body[key] || null;
    try {
      await api('/patients/me/profile', {
        method: 'PUT',
        body
      });
      setMessage('Your profile has been saved.');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return <div className="card"><span className="eyebrow">{t("Getting to know you")}</span><h1 className="!text-3xl">{t("Your profile")}</h1>
    <ResourceStatus resource={resource} />{resource.data && <form onSubmit={submit} className="stack">
      <div className="grid-form"><label>{t("Date of birth")}<input type="date" name="date_of_birth" defaultValue={resource.data.date_of_birth || ''} /></label>
        <label>{t("Expected due date")}<input type="date" name="due_date" defaultValue={resource.data.due_date || ''} /></label>
        <label>{t("Phone number")}<input type="tel" name="phone" maxLength={32} defaultValue={resource.data.phone || ''} /></label>
        <label>{t("Preferred language")}<select name="preferred_language" defaultValue={resource.data.preferred_language}>
          <option value="en">{t("English")}</option><option value="ur">{t("Urdu")}</option></select></label></div>
      <p className="muted text-sm">{t("Choose English or Urdu from the header. Your profile preference is also saved.")}</p>
      {error && <p className="error" role="alert">{error}</p>}{message && <p className="success" role="status">{message}</p>}
      <div><button disabled={busy}>{busy ? t("Saving…") : t("Save profile")}</button></div></form>}
  </div>;
}
const healthFields = [['age_years', 'Age (years)', 10, 65, 1], ['gestational_weeks', 'Pregnancy duration (weeks)', 0, 45, 0.1], ['systolic_mmhg', 'Systolic blood pressure (mmHg)', 60, 260, 1], ['diastolic_mmhg', 'Diastolic blood pressure (mmHg)', 30, 180, 1], ['glucose_mmol_l', 'Blood glucose (mmol/L)', 1, 40, 'any'], ['temperature_c', 'Body temperature (°C)', 32, 43, 'any'], ['heart_rate_bpm', 'Heart rate (beats/minute)', 30, 220, 1]];
export { HealthPage } from './health-form.jsx';
export function HistoryPage() {
  const location = useLocation();
  const [removed, setRemoved] = useState(location.state?.recordRemoved ? 1 : 0);
  const [offset, setOffset] = useState(0);
  const [filters, setFilters] = useState('');
  const resource = useResource(`/patients/me/health-records?offset=${offset}${filters ? '&' + filters : ''}`);
  return <div className="card"><span className="eyebrow">{t("Your record, over time")}</span><h1 className="!text-3xl">{t("Health history")}</h1>
    <RecordFilters onChange={query => { setFilters(query); setOffset(0); }} />
    {removed > 0 && <p className="success" role="status">{t('Health record and linked assessments deleted from active care.')} <Link to="/patient/health">{t('Add a corrected health record')} →</Link></p>}
    <ResourceStatus resource={resource} />
    {resource.data?.length === 0 && <p className="muted">{t("No health records on this page.")}<Link to="/patient/health">{t("Add a record")}</Link>.</p>}
    {resource.data?.map(record => <article key={record.id} className="record">
      <div className="assessment-record-toolbar"><h2 className="!text-lg">{new Date(record.created_at).toLocaleString()}</h2><HealthRecordRemoval recordId={record.id} onRemoved={() => { setRemoved(n => n + 1); resource.retry(); }} /></div>
      <div className="grid-form">{healthFields.map(([key, label]) => <div key={key}>
        <span className="muted text-sm">{t(label)}</span><p className="mt-1 font-semibold">{record.observations[key]}</p></div>)}</div>
      <div className="flex gap-3 flex-wrap mt-4"><Link className="button" to={'/patient/assessments/' + record.id}>{t("View assessment")}</Link></div></article>)}
    <div className="flex gap-3 mt-6"><button className="secondary" disabled={offset === 0 || resource.loading} onClick={() => setOffset(n => n - 50)}>{t("Newer records")}</button>
      <button className="secondary" disabled={resource.data?.length !== 50 || resource.loading} onClick={() => setOffset(n => n + 50)}>{t("Older records")}</button></div>
    <RemovedHealthRecords version={removed} />
  </div>;
}
export function DoctorPage() { return <DoctorWorkspace />; }
export function AdminPage() { return <AdminWorkspace />; }
export function percent(value) {
  return (Number(value) * 100).toFixed(1) + '%';
}
export function ModelAvailability({
  resource
}) {
  if (resource.loading || resource.error) return <ResourceStatus resource={resource} />;
  if (!resource.data?.pregnancy_model_ready) return <p className="service-note"><Icon name="assessment" size={17} />{t('Health screening is currently unavailable. Your records remain available.')}</p>;
  return <p className="service-note"><span className="status-dot" />{t('Health screening is available for supported measurements.')} <Link to="/patient/assessments">{t('View assessments')} →</Link></p>;
}
