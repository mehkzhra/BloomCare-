import { t } from "./i18n.js";
import { useCallback, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from './api.js';
import { ResourceStatus, useResource } from './pages.jsx';
import { Icon } from './ui.jsx';
import { ReportShareDialog } from './report-share.jsx';
export async function download(path, report) {
  const blob = await api(path, {
    responseType: 'blob'
  });
  const extension = {
    'application/pdf': 'pdf',
    'image/png': 'png',
    'image/jpeg': 'jpg'
  }[report.media_type];
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `BloomCare-report-${report.id}.${extension}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function ReportsPage() {
  const [shareReport, setShareReport] = useState(null);
  const closeShare = useCallback(() => setShareReport(null), []);
  const [offset, setOffset] = useState(0);
  const reports = useResource(`/patients/me/reports?offset=${offset}`);
  const appointments = useResource('/patients/me/appointments?offset=0');
  const [appointmentId, setAppointmentId] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState('');
  async function upload(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const file = form.elements.namedItem('report').files[0];
    setBusy(true);
    setError('');
    setSaved('');
    try {
      if (!file) throw new Error('Select a report file.');
      if (file.size > 5 * 1024 * 1024) throw new Error('Maximum 5 MB per report.');
      await api('/patients/me/reports', {
        method: 'POST',
        body: file,
        raw: true,
        headers: {
          'Content-Type': file.type,
          'X-Report-Title': encodeURIComponent(data.get('title'))
        }
      });
      form.reset();
      reports.retry();
      setSaved('Report uploaded.');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function remove(row) {
    if (!window.confirm('Delete this report and revoke its sharing?')) return;
    setBusy(true);
    setError('');
    try {
      await api(`/patients/me/reports/${row.id}`, {
        method: 'DELETE'
      });
      reports.retry();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return <div className="stack"><h1>{t("Medical reports")}</h1>
    <form className="card stack" onSubmit={upload}>
      <label>{t("Report title")}<input name="title" required minLength={2} maxLength={120} /></label>
      <label>{t("Report file")}<input name="report" type="file" accept="application/pdf,image/png,image/jpeg" required /></label>
      <p className="muted">{t("PDF, PNG or JPEG. Maximum 5 MB each, 50 MB total and 100 reports. Files are private until explicitly shared.")}</p>
      <button disabled={busy}>{t("Upload report")}</button>
    </form>
    {error && <p className="error" role="alert">{error}</p>}{saved && <p role="status">{saved}</p>}
    <ResourceStatus resource={reports} />
    {reports.data?.length === 0 && <p>{t("No reports yet.")}</p>}
    {reports.data?.map(row => <section className="card" key={row.id}><div className="report-heading"><span className="feature-icon"><Icon name="report" /></span><div><h2>{row.title}</h2>
      <p className="muted">{new Date(row.created_at).toLocaleString()} · {(row.byte_size / 1024).toFixed(1)}{t("KB")}</p></div></div><div className="report-actions">
      <button className="secondary" aria-label={`${t('Download').trim()} ${row.title}`} onClick={() => download(`/patients/me/reports/${row.id}/download`, row).catch(e => setError(e.message))}>{t("Download")}</button>
      <button className="secondary whatsapp-button" aria-label={`${t('WhatsApp').trim()} ${row.title}`} onClick={() => setShareReport(row)}><Icon name="chat" size={16} />{t('WhatsApp')}</button>
      <button className="secondary delete-report" aria-label={`${t('Delete').trim()} ${row.title}`} disabled={busy} onClick={() => remove(row)}>{t("Delete")}</button>
    </div></section>)}
    {shareReport && <ReportShareDialog key={shareReport.id} report={shareReport} onClose={closeShare} />}
    <div className="nav"><button disabled={!offset} onClick={() => setOffset(n => n - 50)}>{t("Previous reports")}</button>
      <button disabled={reports.data?.length !== 50} onClick={() => setOffset(n => n + 50)}>{t("Next reports")}</button><button onClick={reports.retry}>{t("Refresh reports")}</button></div>
    <section className="card stack"><h2>{t("Share with your doctor")}</h2><ResourceStatus resource={appointments} />
      <label>{t("Accepted appointment")}<select value={appointmentId} onChange={e => setAppointmentId(e.target.value)}>
        <option value="">{t("Choose an appointment")}</option>
        {appointments.data?.filter(a => a.record_access_available).map(a => <option key={a.id} value={a.id}>{a.doctor_name} · {new Date(a.scheduled_at).toLocaleString()}</option>)}
      </select></label>
      <p className="muted">{t("Choose from your latest 50 appointments. Only an accepted, unexpired care episode permits sharing.")}</p>
      {appointmentId && <ReportSharing key={appointmentId} appointmentId={appointmentId} reports={reports.data || []} />}
    </section>
  </div>;
}
function ReportSharing({
  appointmentId,
  reports
}) {
  const shared = useResource(`/patients/me/appointments/${appointmentId}/reports`, {
    pollMs: 15000
  });
  const [error, setError] = useState('');
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  async function change(row, revoke) {
    setBusy(true);
    setError('');
    try {
      const path = `/patients/me/appointments/${appointmentId}/reports`;
      await api(revoke ? `${path}/${row.id}` : path, revoke ? {
        method: 'DELETE'
      } : {
        method: 'POST',
        body: {
          report_id: row.id,
          consent
        }
      });
      shared.retry();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return <div className="stack"><ResourceStatus resource={shared} />
    <label><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />{t("I consent to sharing selected reports with this appointment's doctor.")}</label>
    {error && <p className="error" role="alert">{error}</p>}
    {reports.map(row => {
      const isShared = shared.data?.some(r => r.id === row.id);
      return <div key={row.id}>
      <span>{row.title} · {isShared ? t("Shared") : t("Private")} </span><button disabled={busy || shared.loading || !isShared && !consent} onClick={() => change(row, isShared)}>
        {isShared ? t("Revoke sharing") : t("Share report")}</button></div>;
    })}
  </div>;
}
function DoctorReports({
  appointmentId
}) {
  const resource = useResource(`/doctors/me/appointments/${appointmentId}/reports`, {
    pollMs: 15000
  });
  const [error, setError] = useState('');
  return <section className="card stack"><h2>{t("Shared medical reports")}</h2><ResourceStatus resource={resource} />
    {error && <p className="error" role="alert">{error}</p>}
    {resource.data?.length === 0 && <p>{t("No reports shared.")}</p>}
    {resource.data?.map(row => <div key={row.id}><p>{row.title}</p><button onClick={() => download(`/doctors/me/appointments/${appointmentId}/reports/${row.id}/download`, row).catch(e => {
        setError(e.message);
        resource.retry();
      })}>{t("Download")}{row.title}</button></div>)}
  </section>;
}
export function MessagesPage({
  role
}) {
  const {
    appointmentId
  } = useParams();
  const [offset, setOffset] = useState(0);
  const messages = useResource(`/appointments/${appointmentId}/messages?offset=${offset}`, {
    pollMs: 15000
  });
  const [body, setBody] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const pending = useRef(null);
  async function send(event) {
    event.preventDefault();
    setError('');
    setBusy(true);
    if (!pending.current || pending.current.body !== body) pending.current = {
      body,
      client_message_id: crypto.randomUUID()
    };
    try {
      await api(`/appointments/${appointmentId}/messages`, {
        method: 'POST',
        body: pending.current
      });
      pending.current = null;
      setBody('');
      setOffset(0);
      messages.retry();
    } catch (err) {
      setError(err.message);
      messages.retry();
    } finally {
      setBusy(false);
    }
  }
  return <div className="stack"><h1>{t("Appointment messages")}</h1><Link to={`/${role}/appointments`}>{t("Back to appointments")}</Link>
    <p className="banner">{t("Messaging is for this appointment's participants. New messages require an accepted, unexpired care episode. This inbox is not an emergency service.")}</p>
    <ResourceStatus resource={messages} />
    {error && <p className="error" role="alert">{error}</p>}
    {messages.data && <><form className="card stack" onSubmit={send}>
      <label>{t("Your message")}<textarea value={body} onChange={e => setBody(e.target.value)} required maxLength={4000} /></label>
      <button disabled={busy || !messages.data.can_send || !body.trim()}>{t("Send message")}</button>
      {!messages.data.can_send && <p>{t("This episode is closed or unavailable. Previous messages remain in your history.")}</p>}
    </form>
    {messages.data.messages.length === 0 && <p>{t("No messages yet.")}</p>}
    {messages.data.messages.map(row => <article className="card" key={row.id}><h2>{row.sender_name}</h2><p>{new Date(row.created_at).toLocaleString()}</p><p className="note-body">{row.body}</p></article>)}
    <div className="nav"><button disabled={!offset} onClick={() => setOffset(n => n - 50)}>{t("Newer messages")}</button>
      <button disabled={messages.data.messages.length !== 50} onClick={() => setOffset(n => n + 50)}>{t("Older messages")}</button><button onClick={messages.retry}>{t("Refresh messages")}</button></div>
    {role === 'doctor' && messages.data.can_send && <DoctorReports appointmentId={appointmentId} />}
    </>}
  </div>;
}
export function NotificationBell() {
  const resource = useResource('/notifications?offset=0', {
    pollMs: 15000
  });
  const count = resource.data?.unread_count || 0;
  return <Link className="notification-link" to="/notifications" aria-label={resource.error ? t('Notifications unavailable').trim() : `${t('Notifications').trim()} (${resource.loading ? '…' : count})`}><Icon name="bell" size={20} />{count > 0 && <span className="notification-count">{count > 99 ? '99+' : count}</span>}</Link>;
}
export function NotificationsPage({
  role
}) {
  const [offset, setOffset] = useState(0);
  const resource = useResource(`/notifications?offset=${offset}`, {
    pollMs: 15000
  });
  const [error, setError] = useState('');
  async function mark(row) {
    try {
      await api(`/notifications/${row.id}/read`, {
        method: 'PATCH'
      });
      resource.retry();
    } catch (err) {
      setError(err.message);
    }
  }
  return <div className="stack"><h1>{t("Your notifications")}</h1><ResourceStatus resource={resource} />
    {error && <p className="error" role="alert">{error}</p>}
    {resource.data && <p>{resource.data.unread_count}{t("unread")}</p>}
    {resource.data?.items?.length === 0 && <p>{t("No notifications yet.")}</p>}
    {resource.data?.items?.map(row => <section className="card" key={row.id}>
      <h2>{t(row.kind === 'ASSESSMENT_REMOVED' ? 'A mistaken assessment was deleted' : row.kind === 'HEALTH_RECORD_REMOVED' ? 'A health record and its linked assessments were deleted' : row.kind)}</h2><p>{new Date(row.created_at).toLocaleString()}</p>
      {row.kind === 'MEDICATION_REMINDER' && role === 'patient' && <Link to="/patient/reminders">{t('Reminders')}</Link>}
      {row.health_record_id && role === 'patient' && <Link to={'/patient/assessments/' + row.health_record_id}>{t('Open assessment review')}</Link>}
      {row.kind === 'FOLLOW_UP_PROPOSED' && role === 'patient' && <Link to="/patient/appointments#follow-ups">{t('Doctor follow-up proposals')}</Link>}
      {row.appointment_id && role !== 'admin' && <Link to={`/${role}/appointments/${row.appointment_id}/messages`}>{t("Open appointment messages")}</Link>}
      {!row.read && <button onClick={() => mark(row)}>{t("Mark read")}</button>}
    </section>)}
    <div className="nav"><button onClick={resource.retry}>{t("Refresh notifications")}</button>
      <button disabled={!offset} onClick={() => setOffset(n => n - 50)}>{t("Newer notifications")}</button>
      <button disabled={resource.data?.items?.length !== 50} onClick={() => setOffset(n => n + 50)}>{t("Older notifications")}</button></div>
  </div>;
}
