import { Link } from 'react-router-dom';
import { t } from './i18n.js';
import { Icon } from './ui.jsx';
import { ResourceStatus, useResource } from './pages.jsx';
import { VideoReadiness } from './video-readiness.jsx';

export function VideoHub({ role }) {
  const resource = useResource(`/${role === 'patient' ? 'patients' : 'doctors'}/me/appointments?offset=0`, { pollMs: 15000 });
  const appointments = Array.isArray(resource.data) ? resource.data.filter(row => row.status === 'ACCEPTED' && row.record_access_available) : [];
  return <div className="stack"><div className="page-heading"><span className="eyebrow">{t('Face to face, wherever you are')}</span><h1>{t('Video consultations')}</h1><p className="muted">{t('Your accepted appointments, ready for a conversation.')}</p></div>
    <VideoReadiness />
    <ResourceStatus resource={resource} />
    {!resource.loading && !resource.error && appointments.length === 0 && <section className="card empty-state"><span className="feature-icon"><Icon name="video" size={28} /></span><h2>{t('Your next conversation starts here')}</h2><p className="muted">{t('Video is available for accepted appointments with active access. Your doctor starts the call, then you can join.')}</p><Link className="button" to={`/${role}/appointments`}>{t(role === 'patient' ? 'Request an appointment' : 'Manage appointments')}<Icon name="arrow" size={17} /></Link></section>}
    {appointments.map(row => <article className="card consultation-row" key={row.id}><span className="feature-icon"><Icon name="video" /></span><div><span className="eyebrow">{t('Accepted appointment')}</span><h2>{role === 'patient' ? row.doctor_name : row.patient_name}</h2><p className="muted">{new Date(row.scheduled_at).toLocaleString()}</p></div><Link className="button" to={`/${role}/appointments/${row.id}/consultation`}>{t(role === 'doctor' ? 'Start consultation' : 'Open consultation')}<Icon name="arrow" size={16} /></Link></article>)}
    {Array.isArray(resource.data) && resource.data.length === 50 && <p className="muted text-sm">{t('Showing your latest 50 appointments.')} <Link to={`/${role}/appointments`}>{t('View appointment history')}</Link></p>}
  </div>;
}
