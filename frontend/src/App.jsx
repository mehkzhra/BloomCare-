import { t, useLanguage } from "./i18n.js";
import { LanguageSelector } from "./language.jsx";
import { Component, Suspense, createContext, lazy, useContext, useEffect, useRef, useState } from 'react';
import { Link, Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom';
import { BloomArt, Brand, Icon, InformationPage, PortalNavigation } from './ui.jsx';
import { VideoHub } from './video-hub.jsx';
import { APP_VERSION } from './release-check.jsx';
import { AccountRecoveryPage } from './account-security.jsx';
import { DoctorCaseWorkspace } from './analytics-ui.jsx';
import { ConsultationPage } from './consultation.jsx';
import { ReportsPage, MessagesPage, NotificationsPage, NotificationBell } from './communication.jsx';
import { api, SESSION_REJECTED_EVENT } from './api.js';
import { AssessmentHistoryPage, RecordAssessmentPage } from './assessments.jsx';
import { AppointmentsPage, DoctorAppointmentReview, PatientAppointmentNotes } from './appointments.jsx';
import { AdminPage, DoctorPage, HealthPage, HistoryPage, PatientPage, ProfilePage } from './pages.jsx';
const lazyNamed = (load, name) => lazy(() => load().then(module => ({ default: module[name] })));
const loadExtended = () => import('./extended.jsx');
const FamilyPage = lazyNamed(loadExtended, 'FamilyPage');
const RemindersPage = lazyNamed(loadExtended, 'RemindersPage');
const AssistantPage = lazyNamed(loadExtended, 'AssistantPage');
const OversightPage = lazyNamed(loadExtended, 'OversightPage');
const loadCare = () => import('./care.jsx');
const CarePage = lazyNamed(loadCare, 'CarePage');
const TimelinePage = lazyNamed(loadCare, 'TimelinePage');
const PassportPage = lazyNamed(loadCare, 'PassportPage');
const AdminAccounts = lazyNamed(() => import('./admin.jsx'), 'AdminAccounts');
const ServiceSettingsPage = lazyNamed(() => import('./service-configuration.jsx'), 'ServiceSettingsPage');
class ViewBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return <div className="card stack" role="alert"><h2>{t('This workspace could not open')}</h2><p>{t('Refresh to load the current version of BloomCare.')}</p><div><button onClick={() => window.location.reload()}>{t('Refresh BloomCare')}</button></div></div>;
    return this.props.children;
  }
}
const Auth = createContext(null);
export function useAuth() {
  return useContext(Auth);
}
function Protected({
  role,
  children
}) {
  const {
    user,
    loading
  } = useAuth();
  if (loading) return <p role="status">{t("Checking your session…")}</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={`/${user.role}`} replace />;
  return children;
}
function AccountPage({
  register = false
}) {
  const {
    user,
    acceptSession
  } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [created, setCreated] = useState(false);
  const [role, setRole] = useState('patient');
  const [showPassword, setShowPassword] = useState(false);
  const [verificationRequired, setVerificationRequired] = useState(false);
  if (user) return <Navigate to={`/${user.role}`} replace />;
  async function submit(event) {
    event.preventDefault();
    setError('');
    setBusy(true);
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      if (register) {
        delete data.role;
        const account = await api(role === 'doctor' ? '/auth/register-doctor' : '/auth/register', {
          method: 'POST',
          body: data
        });
        setVerificationRequired(Boolean(account.email_verification_required));
        setCreated(true);
      } else {
        const account = await api('/auth/login', {
          method: 'POST',
          body: data
        });
        acceptSession(account);
        navigate(`/${account.role}`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  if (created) return <div className="card auth"><h2>{t(verificationRequired ? 'Check your email' : 'Your account is ready')}</h2>
    {verificationRequired && <p>{t('Open the verification link in your email before signing in. If it does not arrive, request a new link.')}</p>}
    <p>{role === 'doctor' ? t("Sign in to check your account. Admin approval is required before you can receive appointments or review patient records.") : t("Sign in to start your personal health record.")}</p><Link className="button" to="/login">{t("Sign in")}</Link> <Link to="/account/verify">{t('Request verification email')}</Link></div>;
  return <div className="account-layout"><aside className="account-story"><span className="eyebrow">{t("YOUR CARE, TOGETHER")}</span><h2>{t("A little care.")}<br /><em>{t("For every chapter.")}</em></h2><p>{t("Your health record, your care team and a clearer next step.")}</p><BloomArt /><span className="account-trust"><Icon name="shield" size={18} />{t("Your records, your choice")}</span></aside><div className="card auth"><span className="eyebrow">{t("Your care, connected")}</span>
    <h1 className="!text-3xl">{register ? t("Start with BloomCare") : t("Welcome back")}</h1>
    <p className="muted">{register ? t("Choose a patient or doctor account.") : t("Sign in to your secure care space.")}</p>
    <form onSubmit={submit}>
      <label>{register ? t("Register as") : t("Sign in as")}<select name="role" value={role} onChange={e => setRole(e.target.value)}>
        <option value="patient">{t("Patient")}</option><option value="doctor">{t("Doctor")}</option>
        {!register && <option value="admin">{t("Admin")}</option>}
      </select></label>
      {register && role === 'doctor' && <>
        <label>{t("Registration number")}<input name="registration_number" required minLength={2} maxLength={80} /></label>
        <label>{t("Specialty")}<input name="specialty" required minLength={2} maxLength={120} /></label>
        <p className="muted">{t("Your account will await administrator approval.")}</p>
      </>}
      {register && <label>{t("Full name")}<input name="full_name" required minLength={2} maxLength={120} autoComplete="name" /></label>}
      <label>{t("Email address")}<input type="email" name="email" required autoComplete="email" maxLength={254} /></label>
      <label>{t("Password")}<input type={showPassword ? 'text' : 'password'} name="password" minLength={12} maxLength={128} required autoComplete={register ? 'new-password' : 'current-password'} /></label>
      <button type="button" className="secondary" aria-pressed={showPassword} onClick={() => setShowPassword(v => !v)}>{showPassword ? t("Hide password") : t("Show password")}</button>
      <span className="muted text-sm">{t("Use 12–128 characters.")}</span>
      {error && <p className="error" role="alert">{t(error)}</p>}
      <button disabled={busy}>{busy ? t("Please wait…") : register ? t(`Create ${role} account`) : t('Sign in')}</button>
    </form><p className="text-sm muted">{register ? t("Already registered? ") : t("New to BloomCare? ")}
      <Link to={register ? '/login' : '/register'}>{register ? t("Sign in") : t("Create an account")}</Link></p>
      {!register && <div className="action-row text-sm"><Link to="/account/forgot">{t('Forgot password?')}</Link><Link to="/account/verify">{t('Verify email address')}</Link></div>}
  </div></div>;
}
function Home() {
  return <div className="public-home stack"><section className="landing-hero"><div className="landing-copy"><span className="eyebrow"><span className="status-dot" />{t('BloomCare · Maternal health')}</span>
    <h1>{t('A little care.')}<br /><em>{t('For every chapter.')}</em></h1>
    <p className="landing-description">{t('A personal space for your pregnancy journey.')} {t('Keep your health information together, ready for a more connected care experience.')}</p>
    <div className="action-row"><Link className="button" to="/register">{t('Create your account')}<Icon name="arrow" size={17} /></Link><Link className="text-link" to="/about">{t('Meet BloomCare')}<Icon name="arrow" size={17} /></Link></div>
    <div className="landing-assurances"><span><Icon name="shield" size={16} />{t('Your records, your choice')}</span><span><Icon name="video" size={16} />{t('Connected care')}</span></div>
  </div><div className="landing-visual"><BloomArt /><div className="care-caption"><span className="care-caption-icon"><Icon name="heart" size={21} /></span><span><strong>{t('Made for your journey')}</strong><small>{t('A little more connected, every day.')}</small></span></div></div></section>
    <section className="home-introduction"><span className="eyebrow">{t('YOUR CARE, TOGETHER')}</span><h2>{t('Less searching. More caring.')}</h2><p>{t('From your first record to your next conversation, keep the important things close.')}</p></section>
    <section className="feature-grid">{[
      ['report', 'A clearer health story', 'Your observations, reports and medications, together in one personal record.', 'coral'],
      ['video', 'Care, with a connection', 'Book a doctor, share selected records and meet through a video consultation.', 'teal'],
      ['chat', 'A little more clarity', 'A separate assistant for your questions, with the context you choose to share.', 'violet'],
    ].map(([icon, title, text, tone], index) => <article className={'feature-card feature-' + tone} key={title}><div className="feature-top"><span className="feature-icon"><Icon name={icon} size={23} /></span><span className="feature-number">0{index + 1}</span></div><h2>{t(title)}</h2><p>{t(text)}</p></article>)}</section>
    <section className="home-care-path"><div><span className="eyebrow">{t('ONE CONNECTED JOURNEY')}</span><h2>{t('Your next step, made simpler.')}</h2></div><ol>{[['Save your observations', 'Keep a clear personal record.'], ['Understand your assessment', 'View supported screening and next steps.'], ['Connect with your doctor', 'Choose what to share for your appointment.']].map(([title, description], i) => <li key={title}><span>{i + 1}</span><div><strong>{t(title)}</strong><p>{t(description)}</p></div></li>)}</ol><Link className="button secondary" to="/register">{t('Start with BloomCare')}<Icon name="arrow" size={16} /></Link></section>
  </div>;
}
function Layout() {
  const {
    user,
    setUser,
    loading,
    sessionError,
    sessionNotice,
    retrySession
  } = useAuth();
  const [logoutError, setLogoutError] = useState('');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const sidebar = useRef(null);
  useEffect(() => {
    if (!drawerOpen) return;
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    sidebar.current?.querySelector('a')?.focus();
    function keyboard(event) {
      if (event.key === 'Escape') setDrawerOpen(false);
      if (event.key === 'Tab') {
        const controls = [...sidebar.current.querySelectorAll('a, button, summary')].filter(el => el.getClientRects().length);
        const first = controls[0], last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }
    window.addEventListener('keydown', keyboard);
    return () => { document.body.style.overflow = overflow; window.removeEventListener('keydown', keyboard); previous?.focus(); };
  }, [drawerOpen]);
  const navigate = useNavigate();
  async function logout() {
    try {
      await api('/auth/logout', {
        method: 'POST'
      });
      setUser(null);
      navigate('/login');
    } catch (err) {
      setLogoutError(err.message);
    }
  }
  return <div className={`app-frame ${user ? 'with-sidebar portal-' + user.role : 'public-frame'}`}><a className="skip-link" href="#main-content">{t('Skip to content')}</a>
    {user && <><aside ref={sidebar} id="portal-sidebar" className={`sidebar ${drawerOpen ? 'is-open' : ''}`}><div className="sidebar-brand"><Brand /><button className="icon-button mobile-only" aria-label={t('Close navigation').trim()} onClick={() => setDrawerOpen(false)}><Icon name="close" /></button></div>
      <PortalNavigation role={user.role} close={() => setDrawerOpen(false)} />
      <div className="sidebar-account"><span className="avatar">{user.full_name?.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('')}</span><div><strong>{user.full_name}</strong><small>{t(user.role === 'patient' ? 'Patient account' : user.role === 'doctor' ? 'Doctor account' : 'Administrator')}</small></div><button className="signout-button" onClick={logout}>{t('Sign out')}</button></div>
    </aside>{drawerOpen && <button className="drawer-backdrop" aria-label={t('Dismiss navigation').trim()} onClick={() => setDrawerOpen(false)} />}</>}
    <div className="workspace"><header className="topbar">{user ? <div className="workspace-label"><button className="icon-button mobile-only" aria-label={t('Open navigation').trim()} aria-expanded={drawerOpen} aria-controls="portal-sidebar" onClick={() => setDrawerOpen(true)}><Icon name="menu" /></button><span>{t(user.role === 'patient' ? 'Your care workspace' : user.role === 'doctor' ? 'Doctor workspace' : 'Administration')}<small>{t('A little more connected, every day.')}</small></span></div> : <Brand />}
      <nav className="header-actions" aria-label="Workspace actions">
        {(user?.role === 'patient' || user?.role === 'doctor') && <Link className="button header-video" aria-label={t('Video consultation').trim()} to={`/${user.role}/consultations`}><Icon name="video" size={18} /><span>{t('Video consultation')}</span></Link>}
        {user && <NotificationBell />}<LanguageSelector />
        {!user && !loading && <><NavLink className="public-about" to="/about">{t('About')}</NavLink><NavLink to="/login">{t("Sign in")}</NavLink><NavLink className="button small-button" to="/register">{t("Register")}</NavLink></>}
      </nav></header><main className="shell" id="main-content" tabIndex={-1}>
      {sessionNotice && <p className="banner" role="alert">{sessionNotice}</p>}
      {sessionError && <p className="error" role="alert">{sessionError} <button onClick={retrySession}>{t("Retry connection")}</button></p>}
      {logoutError && <p className="error" role="alert">{logoutError}</p>}
      {loading ? <p role="status">{t("Checking your session…")}</p> : <ViewBoundary><Suspense fallback={<p role="status" className="service-note">{t("Opening your workspace…")}</p>}><Routes>
        <Route path="/" element={user ? <Navigate to={`/${user.role}`} replace /> : <Home />} />
        <Route path="/login" element={<AccountPage />} />
        <Route path="/register" element={<AccountPage key="register" register />} />
        <Route path="/account/forgot" element={<AccountRecoveryPage key="forgot" mode="forgot" />} />
        <Route path="/account/verify" element={<AccountRecoveryPage key="verify" mode="verify" />} />
        <Route path="/account/reset" element={<AccountRecoveryPage key="reset" mode="reset" onReset={() => setUser(null)} />} />
        <Route path="/about" element={<InformationPage kind="about" />} />
        <Route path="/privacy" element={<InformationPage kind="privacy" role={user?.role} />} />
        <Route path="/help" element={<InformationPage kind="help" />} />
        <Route path="/admin/services" element={<Protected role="admin"><ServiceSettingsPage /></Protected>} />
        <Route path="/patient" element={<Protected role="patient"><PatientPage user={user} /></Protected>} />
        <Route path="/patient/consultations" element={<Protected role="patient"><VideoHub role="patient" /></Protected>} />
        <Route path="/doctor/consultations" element={<Protected role="doctor"><VideoHub role="doctor" /></Protected>} />
        <Route path="/patient/profile" element={<Protected role="patient"><ProfilePage /></Protected>} />
        <Route path="/patient/health" element={<Protected role="patient"><HealthPage /></Protected>} />
        <Route path="/patient/history" element={<Protected role="patient"><HistoryPage /></Protected>} />
        <Route path="/patient/assessments" element={<Protected role="patient"><AssessmentHistoryPage /></Protected>} />
        <Route path="/patient/assessments/:recordId" element={<Protected role="patient"><RecordAssessmentPage /></Protected>} />
        <Route path="/patient/appointments" element={<Protected role="patient"><AppointmentsPage role="patient" /></Protected>} />
        <Route path="/patient/appointments/:appointmentId" element={<Protected role="patient"><PatientAppointmentNotes /></Protected>} />
        <Route path="/patient/symptoms" element={<Protected role="patient"><CarePage key="symptoms" kind="symptoms" /></Protected>} />
        <Route path="/patient/medications" element={<Protected role="patient"><CarePage key="medications" kind="medications" /></Protected>} />
        <Route path="/patient/timeline" element={<Protected role="patient"><TimelinePage /></Protected>} />
        <Route path="/patient/passport" element={<Protected role="patient"><PassportPage /></Protected>} />
        <Route path="/patient/reports" element={<Protected role="patient"><ReportsPage /></Protected>} />
        <Route path="/patient/appointments/:appointmentId/messages" element={<Protected role="patient"><MessagesPage role="patient" /></Protected>} />
        <Route path="/doctor/appointments/:appointmentId/messages" element={<Protected role="doctor"><MessagesPage role="doctor" /></Protected>} />
        <Route path="/notifications" element={user ? <NotificationsPage role={user.role} /> : <Navigate to="/login" replace />} />
        <Route path="/patient/family" element={<Protected role="patient"><FamilyPage /></Protected>} />
        <Route path="/patient/reminders" element={<Protected role="patient"><RemindersPage /></Protected>} />
        <Route path="/patient/assistant" element={<Protected role="patient"><AssistantPage /></Protected>} />
        <Route path="/admin/oversight" element={<Protected role="admin"><OversightPage /></Protected>} />
        <Route path="/patient/appointments/:appointmentId/consultation" element={<Protected role="patient"><ConsultationPage role="patient" /></Protected>} />
        <Route path="/doctor/appointments/:appointmentId/consultation" element={<Protected role="doctor"><ConsultationPage role="doctor" /></Protected>} />
        <Route path="/doctor" element={<Protected role="doctor"><DoctorPage /></Protected>} />
        <Route path="/doctor/cases" element={<Protected role="doctor"><DoctorCaseWorkspace /></Protected>} />
        <Route path="/doctor/appointments" element={<Protected role="doctor"><AppointmentsPage role="doctor" /></Protected>} />
        <Route path="/doctor/appointments/:appointmentId" element={<Protected role="doctor"><DoctorAppointmentReview /></Protected>} />
        <Route path="/admin" element={<Protected role="admin"><AdminPage /></Protected>} />
        <Route path="/admin/accounts" element={<Protected role="admin"><AdminAccounts /></Protected>} />
        <Route path="*" element={<div className="card"><h2>{t("Page not found")}</h2><Link to="/">{t("Go to overview")}</Link></div>} />
      </Routes></Suspense></ViewBoundary>}
    </main><footer><span>© {new Date().getFullYear()} BloomCare · {t('Care that stays connected.')} <span className="release-version" title={t('Application version')}>v{APP_VERSION}</span></span><nav aria-label="Information"><Link to="/about">{t('About')}</Link><Link to="/privacy">{t('Privacy & sharing')}</Link><Link to="/help">{t('Help & support')}</Link></nav></footer></div></div>;
}
export default function App() {
  useLanguage();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState('');
  const [sessionNotice, setSessionNotice] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    function rejectSession() {
      if (!user) return;
      setUser(null);
      setSessionError('');
      setSessionNotice('Your session is no longer valid. Sign in again to continue.');
    }
    window.addEventListener(SESSION_REJECTED_EVENT, rejectSession);
    return () => window.removeEventListener(SESSION_REJECTED_EVENT, rejectSession);
  }, [user]);
  useEffect(() => {
    const controller = new AbortController();
    api('/auth/me', {
      signal: controller.signal
    }).then(account => {
      if (!controller.signal.aborted) setUser(account);
    }).catch(err => {
      if (controller.signal.aborted) return;
      if (err.status === 401) setUser(null);
      else setSessionError(err.status === 503 || err.code === 'REQUEST_TIMEOUT'
        ? err.message : 'Unable to connect to BloomCare. Check that the backend is running.');
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [attempt]);
  function acceptSession(account) {
    setUser(account);
    setSessionNotice('');
    setSessionError('');
  }
  function retrySession() {
    setLoading(true);
    setSessionError('');
    setAttempt(n => n + 1);
  }
  return <Auth.Provider value={{
    user,
    setUser,
    acceptSession,
    loading,
    sessionError,
    sessionNotice,
    retrySession
  }}>
    <Layout /></Auth.Provider>;
}
