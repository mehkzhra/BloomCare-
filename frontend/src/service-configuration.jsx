import { Link } from 'react-router-dom';
import { useState } from 'react';
import { api } from './api.js';
import { t } from './i18n.js';
import { ResourceStatus, useResource } from './resources.jsx';
import { Icon } from './ui.jsx';

const names = { email: 'Account emails', groq: 'Assistant & care guides', whatsapp: 'WhatsApp care alerts', video: 'Video consultations' };
const icons = { email: 'shield', groq: 'chat', whatsapp: 'chat', video: 'video' };

// Saved availability states are not evidence that a message or call was delivered.
function serviceState(name, status) {
  if (status === 'INVALID') return { label: 'Needs attention', tone: 'attention' };
  if (['NOT_CONFIGURED', 'NEEDS_SETUP'].includes(status)) return { label: name === 'whatsapp' ? 'Automatic alerts off' : 'Not available', tone: 'neutral' };
  if (name === 'video') return { label: ['RELAY_CONFIGURED', 'STUN_CONFIGURED'].includes(status) ? 'Connection support enabled' : status === 'DIRECT_ONLY' ? 'Basic calling enabled' : 'Status unavailable', tone: 'neutral' };
  return { label: ['CONNECTED', 'CONFIGURED'].includes(status) ? 'Enabled · check delivery' : 'Status unavailable', tone: 'neutral' };
}
function Badge({ name, status }) {
  const state = serviceState(name, status);
  return <span className={'service-badge service-' + state.tone}>{t(state.label)}</span>;
}
export function ServiceOverview({ data }) {
  const services = data.service_configuration;
  return <>
    <div className="service-row"><span className="service-icon"><Icon name="report" size={18} /></span><span><strong>{t('Saved records')}</strong><small>{t('Available in this session')}</small></span><span className="service-badge">{t('Connected')}</span></div>
    {(services?.email ? ['email', 'groq', 'whatsapp', 'video'] : ['groq', 'whatsapp', 'video']).map(name => <div className="service-row" key={name}>
      <span className="service-icon"><Icon name={icons[name]} size={18} /></span><span><strong>{t(names[name])}</strong></span><Badge name={name} status={services?.[name]?.status || data.integrations?.[name]} />
    </div>)}
    <Link className="text-link service-settings-link" to="/admin/services">{t('View service status')}<Icon name="arrow" size={16} /></Link>
  </>;
}
const descriptions = {
  email: 'Verification and password reset links are sent to each person’s registered email address.',
  groq: 'Patients can ask questions and request a care guide after choosing what to share.',
  whatsapp: 'Patients can choose a contact and consent to an automatic care alert when this service is enabled.',
  video: 'Patients and doctors meet through accepted appointments with active access.',
};
const checks = {
  email: 'Use Forgot password with an account you own and check that the reset email arrives.',
  groq: 'Ask one question from the patient Assistant page with consent, then check that a reply arrives.',
  whatsapp: 'Manual sharing is available: download the report and attach it in WhatsApp. Automatic alerts need a separate delivery check.',
  video: 'Use two devices to check a real call. The doctor starts it; both people allow camera and microphone.',
};
function ServiceCard({ name, item }) {
  const [busy, setBusy] = useState(false), [result, setResult] = useState(null);
  async function checkGroq() {
    setBusy(true); setResult(null);
    try { setResult(await api('/admin/service-configuration/groq/check', { method: 'POST', timeoutMs: 60000 })); }
    catch (error) { setResult({ ok: false, message: error.message }); }
    finally { setBusy(false); }
  }
  const needsAttention = ['INVALID', 'NEEDS_SETUP', 'NOT_CONFIGURED'].includes(item.status);
  return <section className="card service-status-card stack" id={name}>
    <div className="panel-heading"><div className="service-title"><span className="step-icon"><Icon name={icons[name]} size={22} /></span><h2>{t(names[name])}</h2></div><Badge name={name} status={item.status} /></div>
    <p>{t(descriptions[name])}</p>
    {name === 'groq' && <div className="stack"><p className="muted">{t('Send a short test prompt to Groq. No patient records are included.')}</p><div><button disabled={busy} onClick={checkGroq}>{t(busy ? 'Checking AI connection…' : 'Test AI connection')}</button></div>{result && <p role={result.ok ? 'status' : 'alert'} className={result.ok ? 'banner' : 'error'}>{result.code && <strong>{result.code}: </strong>}{t(result.message)}</p>}</div>}
    {name === 'video' && item.status === 'INVALID' && <p role="alert">{t('WEBRTC_ICE_SERVERS contains invalid configuration. In hosting environment settings, save only the JSON array from your TURN provider, then restart the app. Do not share the credentials here.')}</p>}
    {needsAttention && <p className="service-action-note"><Icon name="clock" size={17} />{t('Ask the person maintaining BloomCare to enable or check this service.')}</p>}
    <details className="explanation"><summary>{t('How to check this service')}</summary><p>{t(checks[name])}</p></details>
  </section>;
}
export function ServiceSettingsPage() {
  const resource = useResource('/admin/service-configuration');
  return <div className="stack"><header className="workspace-heading"><div><span className="eyebrow">{t('ADMINISTRATION')}</span><h1>{t('Service status')}</h1><p>{t('See which care services are enabled and where support is needed.')}</p></div><button className="secondary" disabled={resource.loading} onClick={resource.retry}>{t('Refresh status')}</button></header>
    <ResourceStatus resource={resource} />
    {resource.data?.services && <><p className="service-note">{t('Enabled means settings are saved. Confirm an actual email, reply, alert or call before relying on delivery.')}</p><div className="service-status-grid">{Object.entries(resource.data.services).filter(([name]) => names[name]).map(([name, item]) => <ServiceCard key={name} name={name} item={item} />)}</div></>}
    <Link className="text-link" to="/admin">{t('Back to administration')}<Icon name="arrow" size={16} /></Link>
  </div>;
}
