import { t } from "./i18n.js";
import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from './api.js';
import { ResourceStatus, useResource } from './pages.jsx';
import { PregnancyTracker } from './analytics-ui.jsx';
function Pager({
  offset,
  setOffset,
  resource
}) {
  return <div className="nav"><button onClick={resource.retry}>{t("Refresh")}</button>
    <button disabled={!offset} onClick={() => setOffset(n => n - 50)}>{t("Previous")}</button>
    <button disabled={(resource.data?.length || 0) < 50} onClick={() => setOffset(n => n + 50)}>{t("Next")}</button></div>;
}
export function CarePage({
  kind
}) {
  const [offset, setOffset] = useState(0);
  const resource = useResource(`/patients/me/${kind}?offset=${offset}`);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState('');
  async function save(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = Object.fromEntries(new FormData(form));
    if (kind === 'symptoms') body.occurred_at = new Date(body.occurred_at).toISOString();
    setBusy(true);
    setError('');
    setSaved('');
    try {
      await api(`/patients/me/${kind}`, {
        method: 'POST',
        body
      });
      form.reset();
      resource.retry();
      setSaved('Record saved.');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function toggle(row) {
    setBusy(true);
    setError('');
    try {
      await api(`/patients/me/medications/${row.id}`, {
        method: 'PATCH',
        body: {
          active: !row.active
        }
      });
      resource.retry();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return <div className="stack"><h1>{kind === 'symptoms' ? t("Symptom tracking") : t("Medication tracking")}</h1>
    <p className="banner">{t("Record your observations and prescribed medicines. Reminders must be scheduled separately.")}</p>
    <form className="card stack" onSubmit={save}>
      {kind === 'symptoms' ? <>
        <label>{t("Symptom description")}<textarea name="description" required minLength={2} maxLength={1000} /></label>
        <label>{t("Severity")}<select name="severity"><option value="MILD">{t("MILD")}</option><option value="MODERATE">{t("MODERATE")}</option><option value="SEVERE">{t("SEVERE")}</option></select></label>
        <label>{t("When it occurred")}<input name="occurred_at" type="datetime-local" required /></label>
        <p className="muted">{t("Time uses your device timezone.")}</p>
      </> : <>
        <label>{t("Medicine name")}<input name="name" required minLength={2} maxLength={120} /></label>
        <label>{t("Prescribed dose")}<input name="dose" required maxLength={120} /></label>
        <label>{t("Prescribed schedule")}<input name="schedule" required minLength={2} maxLength={200} /></label>
        <label>{t("Prescriber")}<input name="prescriber" required minLength={2} maxLength={120} /></label>
      </>}
      <button disabled={busy}>{t("Save")}{kind === 'symptoms' ? t("symptom") : t("medication")}</button>
      {saved && <p role="status">{saved}</p>}
    </form>
    {error && <p className="error" role="alert">{error}</p>}
    <ResourceStatus resource={resource} />
    {resource.data?.length === 0 && <p>{t("No records yet.")}</p>}
    {resource.data?.map(row => <section className="card" key={row.id}>
      {kind === 'symptoms' ? <><h2>{row.description}</h2><p>{row.severity} · {new Date(row.occurred_at).toLocaleString()}</p></> : <>
        <h2>{row.name}</h2><p>{row.dose} · {row.schedule}</p><p>{t("Prescriber:")}{row.prescriber}</p>
        <p>{row.active ? t("Listed as active") : t("Listed as inactive")}</p>
        <button disabled={busy} onClick={() => toggle(row)}>{t("Mark")}{row.active ? t("inactive") : t("active")}</button>
        <p className="muted">{t("This changes your record, not your prescription.")}</p>
      </>}
    </section>)}
    <Pager offset={offset} setOffset={setOffset} resource={resource} />
  </div>;
}
function TimelineEntries({
  rows
}) {
  return <ol className="stack">{rows.map(row => <li className="card" key={row.id}>
    <span className="eyebrow">{row.type.replaceAll('_', ' ')}</span><h3>{row.title}</h3>
    <p>{new Date(row.at).toLocaleString()}</p>
    <dl>{Object.entries(row.details).filter(([key]) => !['id', 'created_at', 'updated_at'].includes(key)).map(([key, value]) => <div key={key}>
      <dt>{key.replaceAll('_', ' ')}</dt><dd>{String(value)}</dd></div>)}</dl>
  </li>)}</ol>;
}
export function TimelinePage() {
  const [offset, setOffset] = useState(0);
  const resource = useResource(`/patients/me/timeline?offset=${offset}`);
  return <div className="stack"><h1>{t("Your health timeline")}</h1><PregnancyTracker /><section className="stack" aria-labelledby="recorded-care-events"><h2 id="recorded-care-events">{t('Recorded care events')}</h2><ResourceStatus resource={resource} />
    {resource.data && <TimelineEntries rows={resource.data} />}
    {resource.data?.length === 0 && <p>{t("No timeline entries yet.")}</p>}
    <Pager offset={offset} setOffset={setOffset} resource={resource} /></section>
  </div>;
}
export function PassportPage() {
  const resource = useResource('/patients/me/passport');
  const report = useRef(null);
  function download() {
    const html = '<!doctype html><html><head><meta charset="utf-8"><title>BloomCare Health Passport</title><style>body{font:16px system-ui;max-width:900px;margin:40px auto;padding:20px}li{break-inside:avoid;border-bottom:1px solid #ccc;padding:12px}dt{font-weight:bold}dd{margin-bottom:8px}</style></head><body>' + report.current.innerHTML + '</body></html>';
    const url = URL.createObjectURL(new Blob([html], {
      type: 'text/html;charset=utf-8'
    }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'BloomCare-Health-Passport.html';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const data = resource.data;
  return <div className="stack"><ResourceStatus resource={resource} />{data && <>
    <div className="nav export-actions"><button onClick={download}>{t("Download health passport")}</button>
      <button onClick={() => window.print()}>{t("Print / Save PDF")}</button><button onClick={resource.retry}>{t("Refresh passport")}</button></div>
    <article className="card stack" ref={report}><h1>{t("BloomCare Health Passport")}</h1>
      <p>{t("Generated:")}{new Date(data.generated_at).toLocaleString()}</p>
      <h2>{data.patient.full_name}</h2><p>{data.patient.email}</p>
      <dl>{Object.entries(data.profile).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{value || 'Not recorded'}</dd></div>)}</dl>
      <p>{data.notice}</p><h2>{t("Active medication records")}</h2>
      {data.active_medications.map(r => <p key={r.id}>{r.name} · {r.dose} · {r.schedule} · {r.prescriber}</p>)}
      {!data.active_medications.length && <p>{t("No active medications recorded.")}</p>}
      {data.medications_truncated && <p>{t("Only the latest 100 active medications are included.")}</p>}
      {data.assessments?.length > 0 && <section className="stack"><h2>{t('Recent screening and care plans')}</h2>{data.assessments.map(a => <article className="record" key={a.id}><h3>{new Date(a.created_at).toLocaleString()} · {a.maternal_risk}</h3><p>{t('PE stage:')}{a.pe_status}{a.pe_screening && <> · {a.pe_screening.risk}</>}</p><p>{t('Review status')}: {a.clinical_review?.status || 'PENDING'}</p>{a.care_plan && <><h4>{t('Personalized care plan')}</h4>{!a.care_plan.current && <p>{t('This plan predates the current PE stage.')}</p>}<p className="note-body">{a.care_plan.content}</p></>}<Link className="export-actions" to={'/patient/assessments/' + a.health_record_id}>{t('Open assessment and PDF report')}</Link></article>)}</section>}
      <h2>{t("Recent timeline")}</h2><p>{t("Includes up to")}{data.timeline_limit}{t("recent events; this is a summary.")}</p>
      <TimelineEntries rows={data.recent_timeline} />
    </article>
  </>}</div>;
}
