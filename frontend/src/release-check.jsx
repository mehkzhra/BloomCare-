import { useState } from 'react';
import manifest from '../package.json';
import { api } from './api.js';
import { t } from './i18n.js';

export const APP_VERSION = manifest.version;
export function ReleaseCheck() {
  const [server, setServer] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function check() {
    setBusy(true); setError('');
    try {
      const result = await api('/health/live');
      if (typeof result.version !== 'string') throw new Error(t('The server version could not be checked.'));
      setServer(result.version);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="card stack release-check"><h2>{t('Application version')}</h2><p>{t('Interface version')}: <strong>v{APP_VERSION}</strong></p>{server && <p role="status">{t('Server version')}: <strong>v{server}</strong></p>}{server && server !== APP_VERSION && <p className="banner" role="alert">{t('The interface and server versions differ. Ask your administrator to complete the update and restart both services, then refresh with Ctrl+F5.')}</p>}{server === APP_VERSION && <p className="success">{t('The interface and server versions match.')}</p>}{error && <p role="alert" className="error">{error}</p>}<div><button className="secondary" disabled={busy} onClick={check}>{t(busy ? 'Checking…' : 'Check server version')}</button></div></section>;
}
