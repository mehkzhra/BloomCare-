import { useEffect, useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from './api.js';
import { t } from './i18n.js';
import { ResourceStatus, useResource } from './resources.jsx';

const copies = {
  assessment: {
    resource: 'assessments', removedResource: 'removed-assessments',
    action: 'Delete assessment', question: 'Delete this assessment?',
    effect: 'It will leave active history, shared assessment views and totals. An audit copy and clinician notes are retained.',
    note: 'Saved measurements stay in Health history. Add a corrected health record for a new assessment. Previously sent copies cannot be recalled.',
    success: 'Assessment deleted from active history.', log: 'Deleted assessment log',
    empty: 'No deleted assessments on this page.', original: 'Original assessment',
  },
  record: {
    resource: 'health-records', removedResource: 'removed-health-records',
    action: 'Delete health record', question: 'Delete this health record?',
    effect: 'The measurements and all linked assessments will leave active history, sharing, charts and future assistant context. Existing clinician notes and a dated audit copy remain.',
    note: 'Add a new health record for corrected measurements. Previously downloaded reports and messages cannot be recalled.',
    success: 'Health record and linked assessments deleted from active care.', log: 'Deleted health record log',
    empty: 'No deleted health records on this page.', original: 'Original health record',
  },
};

function RemovalConfirmation({ entryId, kind, onCancel, onRemoved }) {
  const copy = copies[kind];
  const heading = useId(), reason = useRef(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  useEffect(() => { const previous = document.activeElement; reason.current?.focus(); return () => previous?.focus(); }, []);
  async function remove(event) {
    event.preventDefault();
    if (!event.currentTarget.checkValidity()) { event.currentTarget.reportValidity(); return; }
    const text = new FormData(event.currentTarget).get('reason').trim();
    if (text.length < 5) { setError(t('Add a short reason of at least 5 characters.')); return; }
    setBusy(true); setError('');
    try {
      await api(`/patients/me/${copy.resource}/${entryId}`, { method: 'DELETE', body: { reason: text } });
      onRemoved();
    } catch (err) { setError(err.message); setBusy(false); }
  }
  return <form className="removal-confirmation stack" role="alertdialog" aria-labelledby={heading} onSubmit={remove} onKeyDown={event => { if (event.key === 'Escape' && !busy) onCancel(); }}>
    <div><h3 id={heading}>{t(copy.question)}</h3><p>{t(copy.effect)}</p><p>{t(copy.note)}</p></div>
    <label>{t('Reason for deletion')}<textarea ref={reason} name="reason" required minLength={5} maxLength={500} disabled={busy} placeholder={t('For example: blood pressure was entered incorrectly.')} /></label>
    {error && <p role="alert" className="error">{error}</p>}
    <div className="action-row"><button type="submit" className="danger-button" disabled={busy}>{t(busy ? 'Deleting…' : 'Confirm deletion')}</button><button type="button" className="secondary" disabled={busy} onClick={onCancel}>{t(kind === 'record' ? 'Keep health record' : 'Keep assessment')}</button></div>
  </form>;
}
function EntryRemoval({ entryId, kind, onRemoved }) {
  const copy = copies[kind];
  const [confirming, setConfirming] = useState(false), [removed, setRemoved] = useState(false);
  if (removed) return <p className="success" role="status">{t(copy.success)}</p>;
  return <div className="assessment-removal"><button hidden={confirming} className="text-button danger-text" onClick={() => setConfirming(true)}>{t(copy.action)}</button>{confirming && <RemovalConfirmation entryId={entryId} kind={kind} onCancel={() => setConfirming(false)} onRemoved={() => { setRemoved(true); onRemoved?.(); }} />}</div>;
}
export function AssessmentRemoval({ assessmentId, onRemoved }) { return <EntryRemoval entryId={assessmentId} kind="assessment" onRemoved={onRemoved} />; }
export function HealthRecordRemoval({ recordId, onRemoved }) { return <EntryRemoval entryId={recordId} kind="record" onRemoved={onRemoved} />; }
function RemovedHistory({ kind }) {
  const copy = copies[kind];
  const [offset, setOffset] = useState(0);
  const resource = useResource('/patients/me/' + copy.removedResource + '?offset=' + offset);
  return <div className="stack"><p className="muted">{t('Only deletion details are shown here. Removed results are excluded from active care views and totals.')}</p><ResourceStatus resource={resource} />{resource.data?.length === 0 && <p>{t(copy.empty)}</p>}{resource.data?.map(row => <article className="removed-history-row" key={row.id}><strong>{t('Deleted')} · {new Date(row.removed_at).toLocaleString()}</strong><p>{row.reason}</p><small>{t(copy.original)} · {new Date(row.created_at).toLocaleString()}</small></article>)}<div className="action-row"><button className="secondary" disabled={offset === 0 || resource.loading} onClick={() => setOffset(n => n - 50)}>{t('Newer results')}</button><button className="secondary" disabled={resource.data?.length !== 50 || resource.loading} onClick={() => setOffset(n => n + 50)}>{t('Older results')}</button></div><Link to="/patient/health">{t('Add a corrected health record')} →</Link></div>;
}
function RemovedEntries({ version, kind }) {
  const [open, setOpen] = useState(false);
  return <details className="card explanation removed-assessments" onToggle={event => setOpen(event.currentTarget.open)}><summary>{t(copies[kind].log)}</summary>{open && <RemovedHistory kind={kind} key={version} />}</details>;
}
export function RemovedAssessments({ version }) { return <RemovedEntries version={version} kind="assessment" />; }
export function RemovedHealthRecords({ version }) { return <RemovedEntries version={version} kind="record" />; }
