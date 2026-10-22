import { t } from "./i18n.js";
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from './api.js';
import { ResourceStatus, useResource } from './pages.jsx';
import { download } from './communication.jsx';
import { CategoryChart, ClinicalOversight } from './analytics-ui.jsx';
export { AssistantPage } from './assistant.jsx';
const scopes = ['profile', 'observations', 'assessments', 'symptoms', 'medications', 'reports'];
export function FamilyPage() {
  const grants = useResource('/family/grants', {
    pollMs: 15000
  });
  const [code, setCode] = useState('');
  const [selected, setSelected] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function invite(event) {
    event.preventDefault();
    setError('');
    setBusy(true);
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      const result = await api('/family/invitations', {
        method: 'POST',
        body: {
          recipient_email: data.get('recipient_email'),
          scopes: data.getAll('scope'),
          access_days: Number(data.get('access_days')),
          consent: data.get('consent') === 'on'
        }
      });
      setCode(result.invitation_code);
      grants.retry();
      form.reset();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function accept(event) {
    event.preventDefault();
    setError('');
    setBusy(true);
    const form = event.currentTarget;
    try {
      await api('/family/accept', {
        method: 'POST',
        body: {
          code: new FormData(form).get('code')
        }
      });
      grants.retry();
      form.reset();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function revoke(id) {
    try {
      await api(`/family/grants/${id}`, {
        method: 'DELETE'
      });
      grants.retry();
    } catch (err) {
      setError(err.message);
    }
  }
  return <div className="stack"><h1>{t("Family access")}</h1>
    <form className="card stack" onSubmit={invite}><h2>{t("Invite a family member")}</h2>
      <label>{t("Family member email")}<input type="email" name="recipient_email" required /></label>
      <fieldset><legend>{t("Categories to share")}</legend>{scopes.map(scope => <label key={scope}><input type="checkbox" name="scope" value={scope} />{t(scope)}</label>)}</fieldset>
      <label>{t("Access duration")}<select name="access_days"><option value="7">{t("7 days")}</option><option value="30">{t("30 days")}</option></select></label>
      <label><input type="checkbox" name="consent" required />{t("I consent to read-only access to selected categories, including future records, until expiry or revocation.")}</label>
      <button disabled={busy}>{t("Create invitation")}</button>
      <p className="muted">{t("Share the code privately. The family member must register as Patient using the invited email. Invitations expire after 48 hours. No email is sent automatically.")}</p>
    </form>
    {code && <section className="card"><h2>{t("Invitation code")}</h2><textarea readOnly value={code} aria-label="Invitation code" /></section>}
    <form className="card stack" onSubmit={accept}><h2>{t("Accept an invitation")}</h2><label>{t("Code")}<input name="code" required minLength={30} maxLength={100} /></label><button disabled={busy}>{t("Accept invitation")}</button></form>
    {error && <p role="alert" className="error">{error}</p>}<ResourceStatus resource={grants} />
    <h2>{t("Your shares")}</h2>{grants.data?.owned.map(row => <section className="card" key={row.id}>
      <p>{row.recipient_email} · {row.scopes.join(', ')}</p><p>{row.revoked ? t("Revoked") : row.accepted ? 'Accepted' : 'Pending'} · {new Date(row.access_until).toLocaleString()}</p>
      {!row.revoked && <button onClick={() => revoke(row.id)}>{t("Revoke family access")}</button>}
    </section>)}
    <h2>{t("Shared with you")}</h2>{grants.data?.received.map(row => <section className="card" key={row.id}><p>{row.owner_name}</p>
      <button onClick={() => setSelected(row.id)}>{t("View shared records")}</button></section>)}
    {selected && <FamilyRecords key={selected} id={selected} />}
  </div>;
}
function FamilyRecords({
  id
}) {
  const resource = useResource(`/family/grants/${id}/records`, {
    pollMs: 15000
  });
  const [error, setError] = useState('');
  return <section className="card stack"><h2>{t("Consented family records")}</h2><ResourceStatus resource={resource} />
    {error && <p role="alert" className="error">{error}</p>}
    {resource.data && <><p>{t("Read only. Latest 50 entries per selected category.")}</p>
      {Object.entries(resource.data).filter(([key]) => scopes.includes(key)).map(([key, rows]) => <section key={key}><h3>{t(key)}</h3>
        {key === 'reports' ? rows.map(r => <p key={r.id}>{r.title} <button onClick={() => download(`/family/grants/${id}/reports/${r.id}/download`, r).catch(e => {
            setError(e.message);
            resource.retry();
          })}>{t("Download report")}</button></p>) : <RecordDetails value={rows} />}
      </section>)}</>}
  </section>;
}
export function RemindersPage() {
  const medications = useResource('/patients/me/medications?offset=0');
  const reminders = useResource('/patients/me/reminders', {
    pollMs: 15000
  });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function save(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setError('');
    setBusy(true);
    try {
      await api('/patients/me/reminders', {
        method: 'POST',
        body: {
          medication_id: data.get('medication_id'),
          due_at: new Date(data.get('due_at')).toISOString(),
          period_hours: Number(data.get('period_hours'))
        }
      });
      form.reset();
      reminders.retry();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function cancel(id) {
    try {
      await api(`/patients/me/reminders/${id}`, {
        method: 'DELETE'
      });
      reminders.retry();
    } catch (err) {
      setError(err.message);
    }
  }
  return <div className="stack"><h1>{t("Medication reminders")}</h1><p className="banner">{t("Choose times according to your prescription. Reminders appear in Notifications while the backend is running.")}</p>
    <ResourceStatus resource={medications} /><form className="card stack" onSubmit={save}>
      <label>{t("Medication")}<select name="medication_id" required><option value="">{t("Choose active medication")}</option>{medications.data?.filter(r => r.active).map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
      <label>{t("First reminder time")}<input name="due_at" type="datetime-local" required /></label>
      <label>{t("Repeat")}<select name="period_hours"><option value="0">{t("Once")}</option><option value="12">{t("Every 12 hours")}</option><option value="24">{t("Every 24 hours")}</option></select></label>
      <button disabled={busy}>{t("Schedule reminder")}</button>
    </form>{error && <p className="error" role="alert">{error}</p>}<ResourceStatus resource={reminders} />
    {reminders.data?.map(r => <section className="card" key={r.id}><h2>{r.medicine}</h2><p>{new Date(r.due_at).toLocaleString()} · {r.period_hours ? `${r.period_hours} hours` : t("Once")}</p>
      <p>{r.cancelled ? t("Completed or cancelled") : t("Scheduled")}</p>{!r.cancelled && <button onClick={() => cancel(r.id)}>{t("Cancel reminder")}</button>}
    </section>)}
  </div>;
}
export function OversightPage() {
  const analytics = useResource('/admin/analytics');
  const [offset, setOffset] = useState(0);
  const audit = useResource(`/admin/audit?offset=${offset}`);
  return <div className="stack"><h1>{t("Analytics and access audit")}</h1><ResourceStatus resource={analytics} />
    {analytics.data && Object.entries(analytics.data).filter(([k]) => k !== 'generated_at').map(([key, value]) => <section className="card" key={key}><h2>{key.replaceAll('_', ' ')}</h2>
      {typeof value === 'object' ? <CategoryChart data={value} title={key.replaceAll('_', ' ')} /> : <p className="metric">{value}</p>}
    </section>)}
    <ClinicalOversight />
    <h2>{t("Request audit")}</h2><p>{t("Route templates and response status only; no credentials or medical contents.")}</p><ResourceStatus resource={audit} />
    {audit.data?.map(r => <div className="card" key={r.id}><p>{r.actor} · {r.method} · {r.status_code}</p><p>{r.route}</p><p>{new Date(r.created_at).toLocaleString()}</p></div>)}
    <div className="nav"><button onClick={audit.retry}>{t("Refresh audit")}</button><button disabled={!offset} onClick={() => setOffset(n => n - 50)}>{t("Previous")}</button><button disabled={audit.data?.length !== 50} onClick={() => setOffset(n => n + 50)}>{t("Next")}</button></div>
    <Link to="/admin">{t("Back to administration")}</Link>
  </div>;
}

function RecordDetails({ value }) {
  if (Array.isArray(value)) return <div className="stack">{value.map((row, index) => <div className="card" key={row.id || index}><RecordDetails value={row} /></div>)}</div>;
  if (value && typeof value === 'object') return <dl>{Object.entries(value).filter(([key]) => !['id', 'patient_id', 'user_id'].includes(key)).map(([key, data]) => <div key={key}><dt>{t(key.replaceAll('_', ' '))}</dt><dd><RecordDetails value={data} /></dd></div>)}</dl>;
  return <span>{typeof value === 'boolean' ? t(value ? 'Yes' : 'No') : value == null ? t('Not recorded') : String(value)}</span>;
}
