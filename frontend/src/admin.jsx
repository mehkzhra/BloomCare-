import { t } from "./i18n.js";
import { activityLabel } from './ui.jsx';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api.js';
import { useLocation } from 'react-router-dom';
function AccessConfirmation({ onConfirm, onCancel }) {
  const panel = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    panel.current?.focus();
    return () => previous?.focus();
  }, []);
  return <div ref={panel} tabIndex={-1} className="access-confirmation" role="alertdialog" aria-modal="false" aria-label={t('Confirm access change')} onKeyDown={event => { if (event.key === 'Escape') onCancel(); }}>
    <strong>{t('Confirm access change')}</strong><p>{t('This removes account or clinical access. Check the selected person before continuing.')}</p>
    <div className="action-row"><button onClick={onConfirm}>{t('Confirm change')}</button><button className="secondary" onClick={onCancel}>{t('Cancel')}</button></div>
  </div>;
}
function AdminList({
  title,
  path,
  render,
  searchable = false,
  initialFilters = ''
}) {
  const [rows, setRows] = useState([]);
  const [offset, setOffset] = useState(0);
  const [filters, setFilters] = useState(initialFilters);
  const [pendingChange, setPendingChange] = useState(null);
  const defaults = new URLSearchParams(initialFilters);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    setBusy(true);
    setError('');
    try {
      const response = await api(`${path}?offset=${offset}${filters ? '&' + filters : ''}`);
      if (!Array.isArray(response)) throw new Error('The list could not be read. Refresh and try again.');
      setRows(response);
    } catch (err) {
      setRows([]);
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }, [path, offset, filters]);
  useEffect(() => {
    const timer = setTimeout(load, 0);
    return () => clearTimeout(timer);
  }, [load]);
  async function change(url, body, confirmed = false) {
    if (!confirmed && (body.active === false || body.approved === false)) { setPendingChange({ url, body }); return; }
    setPendingChange(null);
    setBusy(true);
    setError('');
    try {
      await api(url, {
        method: 'PATCH',
        body
      });
      await load();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }
  return <section className="card stack admin-record-list"><h2>{t(title)}</h2>
    {searchable && <form className="record-filters" onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget), params = new URLSearchParams(); for (const key of ['q', 'role', 'active', 'approval']) if (data.get(key)) params.set(key, data.get(key)); setFilters(params.toString()); setOffset(0); }}>
      <label>{t('Search name or email')}<input name="q" type="search" maxLength={80} defaultValue={defaults.get('q') || ''} /></label>
      <label>{t('Account role')}<select name="role" defaultValue={defaults.get('role') || ''}><option value="">{t('All roles')}</option>{['patient', 'doctor', 'admin'].map(role => <option key={role} value={role}>{t(role)}</option>)}</select></label>
      <label>{t('Account status')}<select name="active" defaultValue={defaults.get('active') || ''}><option value="">{t('All statuses')}</option><option value="true">{t('Active')}</option><option value="false">{t('Disabled')}</option></select></label>
      <label>{t('Doctor approval')}<select name="approval" defaultValue={defaults.get('approval') || ''}><option value="">{t('All applications')}</option><option value="pending">{t('Awaiting approval')}</option><option value="approved">{t('Approved')}</option></select></label><button className="secondary">{t('Search accounts')}</button>
    </form>}
    {pendingChange && <AccessConfirmation onConfirm={() => change(pendingChange.url, pendingChange.body, true)} onCancel={() => setPendingChange(null)} />}
    {error && <p role="alert" className="error">{error}</p>}
    {busy && <p role="status">{t("Loading…")}</p>}
    {!busy && !rows.length && <p>{t("No entries.")}</p>}
    {rows.map(row => <article className="record" key={row.id}>{render(row, change, busy)}</article>)}
    <div className="nav"><button disabled={busy} onClick={load}>{t("Refresh")}{title.toLowerCase()}</button>
      <button disabled={busy || offset === 0} onClick={() => setOffset(n => n - 50)}>{t("Previous")}</button>
      <button disabled={busy || rows.length < 50} onClick={() => setOffset(n => n + 50)}>{t("Next")}</button></div>
  </section>;
}
export function AdminAccounts() {
  const location = useLocation();
  const [tab, setTab] = useState('people');
  const tabs = [['people', 'People'], ['appointments', 'Appointments'], ['activity', 'Activity']];
  return <div className="stack"><header className="workspace-heading"><div><span className="eyebrow">{t('PEOPLE & ACCESS')}</span><h1>{t('Accounts and care activity')}</h1><p>{t('Review applications, manage access and follow account activity.')}</p></div></header>
    <div className="admin-tabs" role="tablist" aria-label={t('Account management')} onKeyDown={event => { if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return; event.preventDefault(); const buttons = [...event.currentTarget.querySelectorAll('[role=tab]')], current = tabs.findIndex(([key]) => key === tab); const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length; setTab(tabs[next][0]); buttons[next].focus(); }}>{tabs.map(([key, label]) => <button role="tab" id={'tab-' + key} aria-controls={'panel-' + key} key={key} aria-selected={tab === key} tabIndex={tab === key ? 0 : -1} onClick={() => setTab(key)}>{t(label)}</button>)}</div>
    <div role="tabpanel" id={'panel-' + tab} aria-labelledby={'tab-' + tab}>
    {tab === 'people' && <AdminList key={location.search} initialFilters={location.search.replace(/^\?/, '')} title="Patients and doctors" path="/admin/accounts" searchable render={(u, change, busy) => <>
      <h3>{u.full_name}</h3><p>{u.email} · {t(u.role)} · {u.active ? t("Active") : t("Disabled")}</p>
      {u.role === 'doctor' && <><p>{u.registration_number} · {u.specialty} · {u.approved ? t("Approved") : t("Pending / approval revoked")}</p>
        <button disabled={busy} onClick={() => change(`/admin/doctors/${u.id}/approval`, {
          approved: !u.approved
        })}>
          {u.approved ? t("Revoke doctor approval") : t("Approve doctor")}</button></>}
      {u.role !== 'admin' && <button disabled={busy} className="secondary" onClick={() => change(`/admin/accounts/${u.id}/status`, {
        active: !u.active
      })}>
        {u.active ? t("Disable account") : t("Enable account")}</button>}
    </>} />}
    {tab === 'appointments' && <AdminList title="Appointments" path="/admin/appointments" render={a => <>
      <p>{a.patient} → {a.doctor}</p><p>{new Date(a.scheduled_at).toLocaleString()} · {a.status}</p></>} />}
    {tab === 'activity' && <AdminList title="Activity" path="/admin/activity" render={a => <>
      <p>{a.actor} · {t(activityLabel(a.action))}</p><p>{new Date(a.created_at).toLocaleString()}</p>
</>} />}
    </div></div>;
}
