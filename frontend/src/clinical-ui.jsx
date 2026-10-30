import { useRef, useState } from 'react';
import { api } from './api.js';
import { t, useLanguage } from './i18n.js';
import { ResourceStatus, useResource } from './resources.jsx';
import { Icon } from './ui.jsx';
import { assessmentPDF, savePDF } from './pdf-export.js';
import { WHATSAPP_URL } from './report-share.jsx';

export const reviewLabel = value => t(({ PENDING: 'Awaiting review', REVIEWED: 'Reviewed', URGENT_FOLLOW_UP: 'Urgent follow-up' })[value] || value);
const date = value => new Date(value).toLocaleString();
const localTime = value => { const d = new Date(value); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };

export function CarePlanPanel({ assessment, onChanged, viewerRole }) {
  const language = useLanguage();
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [hostUnavailable, setHostUnavailable] = useState(false);
  const plan = assessment.care_plan;
  const basicGuide = plan?.provider_model === 'local-basic-guide-v1';
  async function generate(event) {
    event.preventDefault(); setBusy(true); setError(''); setHostUnavailable(false);
    try {
      const result = await api(`/patients/me/assessments/${assessment.id}/care-plan`, {
        method: 'POST', timeoutMs: 60000, body: { consent: true, language, ...(basicGuide ? { retry_personalization: true } : {}) },
      });
      onChanged(result);
      if (basicGuide && result.care_plan?.provider_model === 'local-basic-guide-v1') setError(t('AI personalization is still unavailable. Your basic guide has been kept. Ask the administrator to test the AI connection.'));
    } catch (err) { setError(t(err.message)); setHostUnavailable(err.code === 'HOST_UNAVAILABLE'); }
    finally { setBusy(false); }
  }
  return <details className="explanation care-plan-panel" open={Boolean(plan)}><summary><Icon name="leaf" size={17} />{t('Personalized care plan')}{plan && <span className="subtle-tag">{t('Saved')}</span>}</summary>
    {plan ? <div className="stack"><p className="muted text-sm">{t('Saved')}{date(plan.created_at)} · {plan.language.toUpperCase()}</p>
      {!plan.current && <p className="banner">{t('The PE stage changed after this plan was prepared. Generate an updated guide.')}</p>}
      <p className="note-body">{plan.content}</p></div> : <p className="muted">{t('A care guide can be prepared from this saved assessment.')}</p>}
    {viewerRole === 'patient' && (basicGuide || !plan?.current || plan.language !== language) && <form className="stack" onSubmit={generate}>
      <label className="check-label"><input type="checkbox" required disabled={busy} />{t('I agree to send this assessment and its measurements to Groq to prepare my care guide.')}</label>
      <p className="muted text-sm">{t('Your name and email are excluded. This educational guide does not prescribe or change treatment.')}</p>
      <div><button disabled={busy}>{busy ? t('Preparing care plan…') : t(basicGuide ? 'Retry AI personalization' : 'Generate and save care plan')}</button></div>
    </form>}
    {error && <p className="error" role="alert">{error}</p>}
    {hostUnavailable && <a href="/" target="_blank" rel="noopener noreferrer">{t("Open BloomCare in a new tab")}</a>}
  </details>;
}

function ReviewHistory({ path }) {
  const resource = useResource(path);
  return <><ResourceStatus resource={resource} />{resource.data?.length === 0 && <p>{t('No review changes yet.')}</p>}
    {resource.data?.map(row => <div className="record" key={row.id}><strong>{reviewLabel(row.snapshot.status)}</strong><p className="muted text-sm">{row.doctor_name} · {date(row.created_at)}</p><p>{row.snapshot.reason}</p></div>)}</>;
}

export function ClinicalReviewPanel({ assessment, appointmentId, viewerRole, onChanged }) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const current = assessment.clinical_review;
  const path = viewerRole === 'doctor' && appointmentId
    ? `/doctors/me/appointments/${appointmentId}/assessments/${assessment.id}/reviews`
    : `/patients/me/assessments/${assessment.id}/reviews`;
  return <section className={'clinical-review stack ' + (current?.status === 'URGENT_FOLLOW_UP' ? 'clinical-urgent' : '')}>
    <div className="section-heading"><h3>{t('Clinician review')}</h3><span className="subtle-tag">{reviewLabel(current?.status || 'PENDING')}</span></div>
    {current?.reason && <p className="note-body m-0">{current.reason}</p>}
    {current?.follow_up_at && <p className="m-0">{t('Follow-up requested:')}{date(current.follow_up_at)}</p>}
    {viewerRole === 'doctor' && appointmentId && <>
      <ReviewForm key={current?.version || 0} assessment={assessment} appointmentId={appointmentId} onChanged={onChanged} />
      <FollowUpForm assessmentId={assessment.id} appointmentId={appointmentId} />
    </>}
    <details className="explanation" onToggle={event => setHistoryOpen(event.currentTarget.open)}><summary>{t('Review history')}</summary>{historyOpen && <ReviewHistory path={path} />}</details>
  </section>;
}

function ReviewForm({ assessment, appointmentId, onChanged }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const current = assessment.clinical_review;
  async function save(event) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    setBusy(true); setError('');
    try {
      const result = await api(`/doctors/me/appointments/${appointmentId}/assessments/${assessment.id}/review`, {
        method: 'PUT', body: { status: data.get('status'), reason: data.get('reason'),
          follow_up_at: data.get('follow_up_at') ? new Date(data.get('follow_up_at')).toISOString() : null,
          expected_version: current?.version || 0 },
      });
      onChanged(result);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <form className="stack" onSubmit={save} aria-label={t('Save assessment review')}>
    <div className="grid-form"><label>{t('Review status')}<select name="status" defaultValue={current?.status || 'PENDING'} disabled={busy}>
      {['PENDING', 'REVIEWED', 'URGENT_FOLLOW_UP'].map(value => <option key={value} value={value}>{reviewLabel(value)}</option>)}</select></label>
      <label>{t('Follow-up by (optional)')}<input type="datetime-local" name="follow_up_at" defaultValue={current?.follow_up_at ? localTime(current.follow_up_at) : ''} disabled={busy} /></label></div>
    <label>{t('Review reason / follow-up instructions')}<textarea name="reason" maxLength={1000} defaultValue={current?.reason || ''} disabled={busy} rows={3} /></label>
    <p className="muted text-sm">{t('The patient can see this review and its instructions. Add private observations as a private clinician note.')}</p>
    <div><button disabled={busy}>{busy ? t('Saving…') : t('Save review status')}</button></div>
    {error && <p className="error" role="alert">{error}</p>}
  </form>;
}

export function FollowUpForm({ assessmentId, appointmentId }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [saved, setSaved] = useState(false);
  const attempt = useRef({});
  async function submit(event) {
    event.preventDefault(); const form = event.currentTarget, data = new FormData(form);
    setBusy(true); setError(''); setSaved(false);
    try {
      const values = { assessment_id: assessmentId, scheduled_at: new Date(data.get('scheduled_at')).toISOString(), reason: data.get('reason') };
      const key = JSON.stringify(values);
      if (attempt.current.key !== key) attempt.current = { key, id: crypto.randomUUID() };
      await api(`/doctors/me/appointments/${appointmentId}/follow-ups`, { method: 'POST', body: { ...values, request_id: attempt.current.id } });
      setSaved(true); form.reset(); attempt.current = {};
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <details className="explanation"><summary>{t('Propose a follow-up appointment')}</summary>
    <form className="stack" onSubmit={submit}><label>{t('Proposed start time')}<input type="datetime-local" name="scheduled_at" step="1800" required /></label>
      <label>{t('Follow-up reason')}<textarea name="reason" minLength={3} maxLength={1000} required rows={2} /></label>
      <p className="muted text-sm">{t('The patient chooses whether to request this slot and share the linked record. Availability is checked when they accept.')}</p>
      <div><button disabled={busy}>{busy ? t('Saving…') : t('Send follow-up proposal')}</button></div>
    </form>{saved && <p className="success" role="status">{t('Follow-up proposal saved and the patient was notified.')}</p>}
    {error && <p className="error" role="alert">{error}</p>}
  </details>;
}

export function AmendNoteForm({ note, appointmentId, onSaved }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function amend(event) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError('');
    try {
      await api(`/doctors/me/appointments/${appointmentId}/notes/${note.id}/amend`, { method: 'POST', body: {
        body: data.get('body'), patient_visible: data.get('patient_visible') === 'on', assessment_id: note.assessment_id || null,
      } }); onSaved();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <details className="explanation" onToggle={e => setOpen(e.currentTarget.open)}><summary>{t('Add an amendment')}</summary>{open && <form className="stack" onSubmit={amend}>
    <label>{t('Amended note')}<textarea name="body" required maxLength={4000} defaultValue={note.body} rows={3} /></label>
    <label className="check-label"><input type="checkbox" name="patient_visible" defaultChecked={note.patient_visible} />{t('Share this note with the patient')}</label>
    <p className="muted text-sm">{t('The original note and its author remain in the history.')}</p>
    <div><button disabled={busy}>{t('Save amendment')}</button></div></form>}{error && <p role="alert" className="error">{error}</p>}
  </details>;
}

export function FollowUpInbox({ onChanged }) {
  const [open, setOpen] = useState(false);
  return <details id="follow-ups" className="card explanation" onToggle={e => setOpen(e.currentTarget.open)}><summary>{t('Doctor follow-up proposals')}</summary>{open && <FollowUpList onChanged={onChanged} />}</details>;
}
function FollowUpList({ onChanged }) {
  const resource = useResource('/patients/me/follow-ups');
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  async function act(row, action) {
    setBusy(true); setError(''); setNotice('');
    try {
      await api(`/patients/me/follow-ups/${row.id}/${action}`, { method: 'POST', body: action === 'accept' ? {
        share_profile: true, health_record_ids: row.health_record_id ? [row.health_record_id] : [],
      } : undefined });
      setNotice(action === 'accept' ? 'Follow-up requested. Waiting for doctor confirmation.' : 'Proposal declined.');
      resource.retry(); onChanged();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <div className="stack"><ResourceStatus resource={resource} />{error && <p role="alert" className="error">{error}</p>}{notice && <p role="status" className="success">{t(notice)}</p>}
    {resource.data?.length === 0 && <p>{t('No follow-up proposals yet.')}</p>}
    {resource.data?.map(row => <article key={row.id} className="record stack"><h3>{row.doctor_name}</h3><p>{date(row.scheduled_at)} · {row.reason}</p>
      {row.accepted_appointment_id || row.assessment_removed || row.declined || row.expired ? <p className="muted">{t(row.accepted_appointment_id ? 'Appointment requested' : row.assessment_removed ? 'Withdrawn because the linked assessment was deleted' : row.declined ? 'Declined' : 'Expired')}</p> : <form onSubmit={e => { e.preventDefault(); act(row, 'accept'); }} className="stack">
        <label className="check-label"><input type="checkbox" required disabled={busy} />{t('I agree to share my profile and the linked assessment record for this requested follow-up.')}</label>
        <div className="action-row"><button disabled={busy}>{t('Request this follow-up')}</button><button type="button" className="secondary" disabled={busy} onClick={() => act(row, 'decline')}>{t('Decline')}</button></div>
      </form>}</article>)}
  </div>;
}

export function RescheduleForm({ appointment, onChanged }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function save(event) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError('');
    try {
      await api(`/patients/me/appointments/${appointment.id}/reschedule`, { method: 'PATCH', body: {
        scheduled_at: new Date(data.get('scheduled_at')).toISOString(), reason: data.get('reason'), share_profile: true,
        expected_updated_at: appointment.updated_at || appointment.created_at,
      } }); onChanged();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <details className="explanation"><summary>{t('Reschedule appointment')}</summary><form className="stack" onSubmit={save}>
    <label>{t('New start time')}<input name="scheduled_at" type="datetime-local" step="1800" required /></label>
    <label>{t('Reason for revised appointment')}<textarea name="reason" required minLength={3} maxLength={1000} defaultValue={appointment.reason} /></label>
    <label className="check-label"><input type="checkbox" required />{t('I confirm sharing my profile and selected records for the revised appointment.')}</label>
    <p className="muted text-sm">{t('The new time needs doctor confirmation. Current record access and video calls close; reports must be shared again.')}</p>
    <div><button disabled={busy}>{t('Save new appointment time')}</button></div></form>{error && <p role="alert" className="error">{error}</p>}
  </details>;
}

export function AssessmentReportActions({ assessment, viewerRole, appointmentId }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [prepared, setPrepared] = useState(null), [showShare, setShowShare] = useState(false), [consent, setConsent] = useState(false), [notice, setNotice] = useState('');
  const path = viewerRole === 'doctor'
    ? `/doctors/me/appointments/${appointmentId}/assessments/${assessment.id}/report-data`
    : `/patients/me/assessments/${assessment.id}/report-data`;
  async function prepare(share) {
    setBusy(true); setError(''); setNotice(''); setPrepared(null);
    try {
      const report = await api(path);
      const blob = await assessmentPDF(report);
      if (share) { setPrepared(new File([blob], 'BloomCare-Assessment.pdf', { type: 'application/pdf' })); setShowShare(true); setConsent(false); }
      else { savePDF(blob); setNotice('Assessment PDF downloaded.'); }
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  let native = false;
  try { native = Boolean(prepared && navigator.share && navigator.canShare?.({ files: [prepared] })); } catch { /* download remains available */ }
  async function share() {
    if (!consent || !prepared) return;
    setError('');
    try {
      if (native) { await navigator.share({ files: [prepared], title: 'BloomCare assessment' }); setNotice('Your report is ready in the selected app. Choose the recipient and press Send there. BloomCare has no delivery confirmation.'); }
      else { savePDF(prepared); window.open(WHATSAPP_URL, '_blank', 'noopener,noreferrer'); setNotice('Report downloaded. Attach it in WhatsApp before sending.'); }
    } catch (err) { if (err.name !== 'AbortError') setError('Sharing could not open. Download the PDF and attach it manually.'); }
  }
  return <div className="stack report-actions"><div className="action-row"><button className="secondary" disabled={busy} onClick={() => prepare(false)}><Icon name="report" size={16} />{busy ? t('Preparing PDF…') : t('Download assessment PDF')}</button>
    {viewerRole === 'patient' && <button className="secondary" disabled={busy} onClick={() => prepare(true)}>{t('Share assessment PDF')}</button>}</div>
    {showShare && prepared && <section className="share-prepared stack"><h4>{t('Share via WhatsApp')}</h4><label className="check-label"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />{t('I choose to share a copy of this assessment outside BloomCare.')}</label>
      <p className="muted text-sm">{t('Confirm the recipient in your sharing app. Copies sent outside BloomCare cannot be recalled here.')}</p>
      <div className="action-row"><button disabled={!consent} onClick={share}>{t(native ? 'Choose sharing app' : 'Download & open WhatsApp')}</button><button className="secondary" onClick={() => { setShowShare(false); setPrepared(null); }}>{t('Close')}</button></div>
    </section>}{error && <p role="alert" className="error">{error}</p>}{notice && <p role="status" className="success">{t(notice)}</p>}
  </div>;
}

export function WhatsAppAssessmentAlert({ assessmentId }) {
  const [open, setOpen] = useState(false);
  return <details className="explanation" onToggle={e => setOpen(e.currentTarget.open)}><summary>{t('WhatsApp care alert')}</summary>{open && <AlertForm assessmentId={assessmentId} />}</details>;
}
function AlertForm({ assessmentId }) {
  const status = useResource('/patients/me/whatsapp/status');
  const history = useResource(`/patients/me/assessments/${assessmentId}/alerts`);
  const attempt = useRef({});
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [submitted, setSubmitted] = useState(false), [draft, setDraft] = useState(0);
  async function send(event) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError('');
    const recipient = data.get('recipient').trim();
    if (attempt.current.recipient !== recipient) attempt.current = { recipient, id: crypto.randomUUID() };
    try { await api(`/patients/me/assessments/${assessmentId}/alerts`, { method: 'POST', body: { recipient, request_id: attempt.current.id, consent: true } }); setSubmitted(true); history.retry(); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  async function refresh(row) { try { await api(`/patients/me/alerts/${row.id}`); history.retry(); } catch (err) { setError(err.message); } }
  return <div className="stack"><ResourceStatus resource={status} />{status.data?.configured === false && <p className="service-note">{t('Automatic WhatsApp alerts need care-team setup. You can still use Share assessment PDF above to send a copy yourself.')}</p>}
    {status.data?.configured && !submitted && <form key={draft} className="stack" onSubmit={send}><label>{t('Approved care contact')}<input name="recipient" type="tel" required pattern="\+[1-9][0-9]{7,14}" placeholder="+923001234567" /></label>
      <label className="check-label"><input type="checkbox" required />{t('I have permission from this contact and agree to send my assessment categories through WhatsApp.')}</label>
      <p className="muted text-sm">{t('This sends a brief category alert, not your full report. Provider acceptance does not confirm delivery.')}</p>
      <div><button disabled={busy}>{t('Send care alert')}</button></div></form>}
    {submitted && <div className="stack"><p role="status">{t('Alert request saved. Check its delivery status before creating another.')}</p><div><button className="secondary" onClick={() => { attempt.current = {}; setSubmitted(false); setDraft(n => n + 1); }}>{t('Prepare another alert')}</button></div></div>}
    {error && <p className="error" role="alert">{error}</p>}<ResourceStatus resource={history} />
    {history.data?.map(row => <div className="record" key={row.id}><strong>{row.recipient} · {t(row.status)}</strong><p>{row.detail || t('Delivery status is reported by the messaging provider.')}</p><button className="secondary" onClick={() => refresh(row)}>{t('Refresh delivery status')}</button></div>)}
  </div>;
}
