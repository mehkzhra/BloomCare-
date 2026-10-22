import { t } from './i18n.js';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { privacyContent } from './privacy-content.js';
import { ReleaseCheck } from './release-check.jsx';

const paths = {
  overview: <><rect x="3" y="3" width="7" height="7" rx="2" /><rect x="14" y="3" width="7" height="7" rx="2" /><rect x="3" y="14" width="7" height="7" rx="2" /><rect x="14" y="14" width="7" height="7" rx="2" /></>,
  heart: <><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" /><path d="M5 12h4l2-4 2 8 2-4h4" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M16 3v4M8 3v4M3 11h18m-13 5h2m4 0h2" /></>,
  report: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6M8 13h8m-8 4h5" /></>,
  assessment: <><path d="M9 3H6a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2h-3" /><rect x="9" y="1" width="6" height="4" rx="1" /><path d="m8 13 3 3 5-6" /></>,
  chat: <><path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7A8.4 8.4 0 0 1 4 11.5a8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z" /><path d="M8 11h8m-8 4h5" /></>,
  video: <><rect x="2" y="5" width="14" height="14" rx="3" /><path d="m16 10 6-4v12l-6-4Z" /></>,
  arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
  chevron: <path d="m9 5 7 7-7 7" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-11 12a2 2 0 0 0 4 0" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  shield: <><path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6Z" /><path d="m8 12 3 3 5-6" /></>,
  users: <><circle cx="9" cy="8" r="4" /><path d="M2 21v-2a7 7 0 0 1 14 0v2m0-17a4 4 0 0 1 0 8m4 9v-2a7 7 0 0 0-4-6" /></>,
  leaf: <><path d="M20 3C9 2 2 9 5 17c8 3 15-4 15-14Z" /><path d="M4 21 16 9" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
};
export function Icon({ name, size = 20, ...props }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name] || paths.heart}</svg>;
}
export function Brand() {
  return <Link to="/" className="brand" aria-label="BloomCare home"><img className="brand-mark" src="/bloomcare-mark.svg?v=1.2.0" width="40" height="40" alt="" /><span>Bloom<span className="brand-light">Care</span><small>{t('A little care. Every day.')}</small></span></Link>;
}
export function BloomArt() {
  return <div className="bloom-art" aria-hidden="true"><svg viewBox="0 0 400 360" fill="none">
    <path d="M70 309V151a130 130 0 0 1 260 0v158Z" fill="#D4E9DE" />
    <circle cx="303" cy="81" r="31" fill="#F4BD96" />
    <path d="M73 308h258" stroke="#9ABAA8" strokeWidth="2" />
    <path d="M106 307c-7-49-13-80-43-111 36 0 60 30 62 70-1-50 4-79 23-104 12 42-1 88-23 113 20-29 38-40 67-38-10 31-32 54-61 59" fill="#739D85" />
    <path d="m238 292 36 43h35c5-1 6-7 0-11l-27-15-19-34" fill="#BA7062" />
    <path d="M231 260c-16 21-32 33-61 35l-17 28h33l35-29 34-19" fill="#DAA087" />
    <path d="M190 148c-34 5-47 34-43 67 2 25-5 48-11 77 39 17 90 15 139-8-4-25-15-48-22-59 8-34-15-59-38-65Z" fill="#175D53" />
    <path d="M177 159c8 11 30 13 44 1l-6-24-29-1Z" fill="#DAA087" />
    <path d="M171 94c11-18 49-12 53 9l1 16 8 14-12 6c-4 17-15 24-28 17-16-7-22-29-22-62Z" fill="#EAB69B" />
    <path d="M173 135c-11-9-17-21-14-38 3-27 38-34 56-19 10 8 13 19 8 30l-13-11c-6 12-20 16-30 16l4 24Z" fill="#203D38" />
    <circle cx="167" cy="91" r="18" fill="#203D38" />
    <path d="M206 119h3" stroke="#764E46" strokeWidth="3" strokeLinecap="round" />
    <path d="M166 175c-19 29-14 49 2 59 12 8 33 10 59 7" stroke="#EAB69B" strokeWidth="18" strokeLinecap="round" />
    <path d="M227 241c10-1 18-5 19-10-10-8-15-6-25-2" fill="#EAB69B" />
    <path d="M236 181c15 14 23 30 21 43" stroke="#EAB69B" strokeWidth="12" strokeLinecap="round" />
    <path d="m240 205 34-8 10 36-35 9Z" fill="#F3D9B6" stroke="#E5C499" strokeWidth="2" />
    <path d="m249 212 17-4m-14 12 17-4" stroke="#9A896D" strokeWidth="2" strokeLinecap="round" />
    <path d="M280 146c0-18 23-35 33-44 10 15 17 39 0 53-13 10-29 4-33-9Z" fill="#F7F2E6" />
    <path d="m302 144 10-24" stroke="#89A69A" strokeWidth="2" strokeLinecap="round" />
    <path d="M321 262c7-26 17-40 34-47-1 27-13 42-31 51m-2-8c-16-13-22-27-19-45 20 9 28 26 19 45Z" fill="#739D85" />
  </svg></div>;
}

const patientLinks = [
  ['Overview', '/patient', 'overview'], ['Health record', '/patient/health', 'heart'],
  ['Assessments', '/patient/assessments', 'assessment'], ['Appointments', '/patient/appointments', 'calendar'],
  ['Reports', '/patient/reports', 'report'], ['Assistant', '/patient/assistant', 'chat'],
];
const careLinks = [
  ['History', '/patient/history'], ['Symptoms', '/patient/symptoms'], ['Medications', '/patient/medications'],
  ['Reminders', '/patient/reminders'], ['Timeline', '/patient/timeline'], ['Health passport', '/patient/passport'],
  ['Family', '/patient/family'], ['Profile', '/patient/profile'],
];
export function PortalNavigation({ role, close }) {
  const location = useLocation();
  const links = role === 'patient' ? patientLinks : role === 'doctor'
    ? [['Overview', '/doctor', 'overview'], ['Appointments', '/doctor/appointments', 'calendar'], ['Shared assessments', '/doctor/cases', 'assessment']]
    : [['Overview', '/admin', 'overview'], ['Accounts', '/admin/accounts', 'users'], ['Analytics and audit', '/admin/oversight', 'assessment'], ['Connected services', '/admin/services', 'video']];
  return <><div className="sidebar-caption">{t(role === 'patient' ? 'MY CARE' : role === 'doctor' ? 'PRACTICE' : 'ADMINISTRATION')}</div>
    <nav className="portal-nav" aria-label="Main navigation">{links.map(([label, path, icon]) => <NavLink key={path} to={path} end={path === `/${role}`} onClick={close}><Icon name={icon} /><span>{t(label)}</span><Icon name="chevron" size={14} className="nav-chevron" /></NavLink>)}</nav>
    {role === 'patient' && <details className="care-menu" key={location.pathname} open={careLinks.some(([, path]) => path === location.pathname)}><summary><Icon name="plus" size={18} />{t('More care tools')}</summary><nav aria-label="More care tools">{careLinks.map(([label, path]) => <NavLink key={path} to={path} onClick={close}>{t(label)}</NavLink>)}</nav></details>}
    <div className="sidebar-note"><Icon name="shield" /><strong>{t(role === 'doctor' ? 'Care built on trust.' : role === 'admin' ? 'Accountable access.' : 'Your care. Your choice.')}</strong><p>{t(role === 'doctor' ? 'Access follows each patient’s active sharing choices.' : role === 'admin' ? 'Review approvals, service setup and audit activity.' : 'You decide which records to share with your care team.')}</p><Link to="/privacy" onClick={close}>{t('Privacy & sharing')}<Icon name="arrow" size={15} /></Link></div>
  </>;
}

export function InformationPage({ kind, role }) {
  if (kind === 'privacy') {
    const content = privacyContent[role] || privacyContent.public;
    return <div className="information-page privacy-page stack"><header className="privacy-heading"><span className="privacy-symbol"><Icon name="shield" size={28} /></span><div><span className="eyebrow">{t('Privacy & sharing')} · {t(role === 'admin' ? 'Administrator' : role === 'doctor' ? 'Doctor account' : role === 'patient' ? 'Patient account' : 'BloomCare')}</span><h1>{t(content.heading)}</h1><p>{t(content.description)}</p></div></header><nav className="privacy-actions" aria-label={t('Privacy controls')}>{content.actions.map(([title, path]) => <Link className="button secondary" key={path} to={path}>{t(title)}<Icon name="arrow" size={16} /></Link>)}</nav><div className="privacy-grid">{content.sections.map(([title, body], index) => <section className="card privacy-section" key={title}><span className="privacy-number" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span><h2>{t(title)}</h2><p>{t(body)}</p></section>)}</div></div>;
  }
  const pages = {
    about: ['About BloomCare', 'Care that stays connected.', [
      ['One place for your health', 'Keep observations, medications, symptoms and medical reports together, with a timeline you can return to.'],
      ['A closer connection to your doctor', 'Request an appointment with an approved doctor, choose what to share, and continue the conversation through messages and video consultations.'],
      ['Answers, when you need them', 'The assistant helps explain your questions and selected records. Health assessments are a separate screening feature and do not replace clinical care.'],
    ]],
    help: ['Help & support', 'A clear next step, whenever you need one.', [
      ['Join a video consultation', 'Open Video consultation at the top of your workspace. Choose an accepted appointment with active access, allow camera and microphone, and join when your doctor starts the call.'],
      ['Share a report on WhatsApp', 'Open Reports and choose WhatsApp beside a report. On supported devices, select WhatsApp from the share menu. Otherwise, download the copy, open WhatsApp and attach it before sending.'],
      ['Understand an assessment', 'Enter your actual measurements and known antenatal results in one form. Maternal categories or recorded warning indicators can open PE screening. Unsupported readings stay recorded for clinical review. A saved care guide and PDF report remain linked to your assessment.'],
      ['Get help with your account', 'Check your selected sign-in role and contact your BloomCare administrator for account access or doctor approval.'],
    ]],
  };
  const [label, heading, sections] = pages[kind];
  return <div className="information-page stack"><header><span className="eyebrow">{t(label)}</span><h1>{t(heading)}</h1></header><div className="card stack">{sections.map(([title, body]) => <section key={title}><h2>{t(title)}</h2><p className="muted">{t(body)}</p></section>)}</div>{kind === 'help' && <ReleaseCheck />}<Link to="/">{t('Back to BloomCare')} →</Link></div>;
}
