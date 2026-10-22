import { useState } from 'react';
import { Link } from 'react-router-dom';
import { t } from './i18n.js';
import { ResourceStatus, useResource } from './resources.jsx';
import { Icon } from './ui.jsx';

const names = { email: 'Account verification & recovery', groq: 'AI assistant & care guides', whatsapp: 'WhatsApp care alerts', video: 'Video consultations' };
const labels = { CONNECTED: 'Connected', CONFIGURED: 'Settings saved', NOT_CONFIGURED: 'Not configured', NEEDS_SETUP: 'Not configured', DIRECT_ONLY: 'Direct connection mode', STUN_CONFIGURED: 'STUN settings saved', RELAY_CONFIGURED: 'Relay settings saved', INVALID: 'Fix network settings' };
const icons = { database: 'report', email: 'shield', groq: 'chat', whatsapp: 'chat', video: 'video' };

export function ServiceOverview({ data }) {
  return <><div className="service-row"><span className="service-icon"><Icon name="report" size={18} /></span><span><strong>{t('Database')}</strong><small>{t('Verified by this request')}</small></span><span className="service-badge">{t('Connected')}</span></div>{(data.service_configuration?.email ? ['email', 'groq', 'whatsapp', 'video'] : ['groq', 'whatsapp', 'video']).map(key => {
    const item = data.service_configuration?.[key];
    const status = item?.status || data.integrations?.[key];
    const fallback = key === 'whatsapp' && ['NEEDS_SETUP', 'NOT_CONFIGURED'].includes(status) ? 'Automatic alerts off' : labels[status] || 'Check configuration';
    return <div className="service-row" key={key}><span className="service-icon"><Icon name={icons[key]} size={18} /></span><span><strong>{t(names[key])}</strong></span><span className={'service-badge ' + (status === 'INVALID' ? 'service-error' : 'service-neutral')}>{t(item?.label || fallback)}</span></div>;
  })}<Link className="text-link service-settings-link" to="/admin/services">{t('Check setup & next steps')}<Icon name="arrow" size={16} /></Link></>;
}

function SetupCard({ name, item }) {
  const [copied, setCopied] = useState(false), [error, setError] = useState('');
  async function copy() {
    try { await navigator.clipboard.writeText(item.command); setCopied(true); setError(''); }
    catch { setError(t('Select and copy the command below.')); }
  }
  return <section className="card service-setup-card stack" id={name}><div className="panel-heading"><div><span className="eyebrow">{t('CONNECTED SERVICE')}</span><h2>{t(names[name])}</h2></div><span className={'service-badge ' + (item.status === 'INVALID' ? 'service-error' : 'service-neutral')}>{t(item.label)}</span></div><p>{t(item.summary)}</p>
    {item.missing?.length > 0 && <div className="missing-settings"><strong>{t('Settings to complete')}</strong><ul>{item.missing.map(setting => <li key={setting}><code>{setting}</code></li>)}</ul></div>}
    <div className="setup-command"><span>{t('Run in CMD from your BloomCare folder')}</span><code>{item.command}</code><button className="secondary" onClick={copy}>{t(copied ? 'Command copied' : 'Copy command')}</button>{error && <p role="status">{error}</p>}</div>
    <p className="scope-note">{t('Restart the backend after saving settings, then refresh this page.')}</p>
    <p className="scope-note">{t('Hosted installation: enter these settings in your hosting dashboard Environment, then redeploy.')}</p>
    {name === 'video' ? <ol className="setup-checks"><li>{t('Use localhost on this computer or HTTPS for other devices.')}</li><li>{t('Request and accept an appointment; its access must still be active.')}</li><li>{t('The doctor starts the call. The patient opens the same accepted appointment.')}</li><li>{t('Allow camera and microphone on both devices. Test across the networks you will use.')}</li></ol> : name === 'whatsapp' ? <div className="stack"><p>{t('Manual sharing: the patient can download an assessment PDF and attach it in WhatsApp now.')}</p><ol className="setup-checks"><li>{t('Save your Twilio Account SID, Auth Token, approved sender and opted-in recipient numbers.')}</li><li>{t('For a sandbox sender, each recipient must join that sandbox first.')}</li><li>{t('For sandbox alerts, leave Content SID blank and send within 24 hours of the recipient’s join message. Custom templates require a registered sender.')}</li><li>{t('Outside an active WhatsApp service window, use an approved message template with the two BloomCare variables.')}</li><li>{t('The patient chooses a contact and consents to an alert. Refresh its delivery status afterwards.')}</li></ol></div> : name === 'groq' ? <p>{t('Check the saved Groq key, available model and provider quota with one consented question from the patient Assistant page.')}</p> : null}
    {name === 'email' && <p className="scope-note">{t('Use the sign-in page to request verification and password-reset links. Test your inbox, expiry and one-time use before public onboarding.')}</p>}
    <p className="service-note">{t('This checks saved configuration. Provider delivery and real calls need a live check.')}</p>
  </section>;
}
export function ServiceSettingsPage() {
  const resource = useResource('/admin/service-configuration');
  return <div className="stack"><header className="workspace-heading"><div><span className="eyebrow">{t('ADMINISTRATION')}</span><h1>{t('Connected services')}</h1><p>{t('See what is ready, what needs configuration and how to finish setup.')}</p></div><button className="secondary" disabled={resource.loading} onClick={resource.retry}>{t('Refresh status')}</button></header><ResourceStatus resource={resource} />{resource.data?.services && <><p className="service-note">{t('Credentials are entered on your server. Secret values and contact numbers are hidden here.')}</p>{Object.entries(resource.data.services).map(([name, item]) => <SetupCard key={name} name={name} item={item} />)}</>}<Link to="/admin">{t('Back to administration')} →</Link></div>;
}
