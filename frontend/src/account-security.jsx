import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { api } from './api.js';
import { t } from './i18n.js';

export function AccountRecoveryPage({ mode, onReset }) {
  const location = useLocation(), navigate = useNavigate();
  const [token, setToken] = useState(() => new URLSearchParams(location.hash.slice(1)).get('token'));
  const [busy, setBusy] = useState(false), [error, setError] = useState(null), [message, setMessage] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const validToken = typeof token === 'string' && /^[A-Za-z0-9_-]{43}$/.test(token);
  useEffect(() => {
    // Keep the link secret out of browser history after reading it into memory.
    if (location.hash) navigate(location.pathname, { replace: true });
  }, [location.hash, location.pathname, navigate]);
  const confirm = validToken && mode !== 'forgot';
  const title = mode === 'forgot' ? 'Reset your password' : mode === 'verify' ? 'Verify your email' : 'Choose a new password';
  async function submit(event) {
    event.preventDefault();
    if (!event.currentTarget.checkValidity()) { event.currentTarget.reportValidity(); return; }
    const data = new FormData(event.currentTarget);
    if (mode === 'reset' && data.get('password') !== data.get('confirm_password')) {
      setError(new Error('Passwords do not match.')); return;
    }
    const path = mode === 'forgot' ? '/auth/forgot-password' : mode === 'verify' ? (confirm ? '/auth/verification/confirm' : '/auth/verification/request') : '/auth/reset-password';
    const body = confirm ? { token, ...(mode === 'reset' ? { password: data.get('password') } : {}) } : { email: data.get('email') };
    setBusy(true); setError(null); setMessage('');
    try {
      const result = await api(path, { method: 'POST', body });
      setMessage(result.message);
      if (mode === 'reset') onReset?.();
    } catch (err) { setError(err); }
    finally { setBusy(false); }
  }
  return <section className="card auth stack"><span className="eyebrow">{t('Your account, protected')}</span><h1>{t(title)}</h1>
    {message ? <p className="success" role="status">{t(message)}</p> : mode === 'reset' && !validToken ? <p className="banner">{t('Open the latest password-reset link from your email. If it expired or you refreshed this page, request a new link.')}</p> : <>
      <p className="muted">{t(confirm ? 'This link works once. Confirm below when you are ready.' : 'Enter your account email address. We will not disclose whether an account exists.')}</p>
      <form className="stack" onSubmit={submit}>
        {!confirm && <label>{t('Email address')}<input name="email" type="email" autoComplete="email" required maxLength={254} disabled={busy} /></label>}
        {mode === 'reset' && <><label>{t('New password')}<input name="password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" required minLength={12} maxLength={128} disabled={busy} /></label>
          <label>{t('Confirm new password')}<input name="confirm_password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" required minLength={12} maxLength={128} disabled={busy} /></label>
          <button type="button" className="secondary" aria-pressed={showPassword} disabled={busy} onClick={() => setShowPassword(v => !v)}>{t(showPassword ? 'Hide password' : 'Show password')}</button>
          <small className="muted">{t('Use 12–128 characters.')}</small></>}
        <button disabled={busy}>{t(busy ? 'Please wait…' : mode === 'reset' ? 'Update password' : confirm ? 'Verify email address' : mode === 'forgot' ? 'Send password-reset email' : 'Request verification email')}</button>
      </form>
    </>}
    {error && <p className="error" role="alert">{t(error.message)}{error.retryAfterSeconds && <> {t('Retry after')} {error.retryAfterSeconds} {t('seconds')}.</>}</p>}
    <div className="action-row"><Link to="/login">{t('Return to sign in')}</Link>{mode === 'reset' && <Link to="/account/forgot">{t('Request a new reset link')}</Link>}{mode === 'verify' && confirm && <button className="secondary" type="button" onClick={() => { setToken(null); setMessage(''); setError(null); }}>{t('Request verification email')}</button>}</div>
  </section>;
}
