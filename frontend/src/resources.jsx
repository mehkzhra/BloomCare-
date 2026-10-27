import { useEffect, useState } from 'react';
import { api } from './api.js';
import { t } from './i18n.js';
export function useResource(path, { pollMs = 0, validate } = {}) {
  const [state, setState] = useState({ data: null, error: '', loading: true });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer;
    let pending = false;
    async function refresh() {
      if (pending || controller.signal.aborted) return;
      clearTimeout(timer);
      pending = true;
      try {
        const data = await api(path, { signal: controller.signal });
        if (validate && !validate(data)) throw new Error('The workspace response could not be read. Refresh and try again.');
        if (!controller.signal.aborted) setState({ data, error: '', loading: false, path });
      } catch (err) {
        if (!controller.signal.aborted) setState(previous => ({
          data: previous.path === path && ![401, 403].includes(err.status) ? previous.data : null,
          error: err.message, loading: false, path
        }));
      } finally {
        pending = false;
        if (pollMs && !controller.signal.aborted && !document.hidden) timer = setTimeout(refresh, pollMs);
      }
    }
    function visibilityChanged() {
      clearTimeout(timer);
      if (!document.hidden) refresh();
    }
    refresh();
    if (pollMs) document.addEventListener('visibilitychange', visibilityChanged);
    return () => {
      controller.abort();
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', visibilityChanged);
    };
  }, [path, attempt, pollMs, validate]);
  // Keep only this mounted view's data. A different resource must never show it.
  const current = state.path === path ? state : { data: null, error: '', loading: true };
  return { ...current, retry: () => setAttempt(n => n + 1) };
}
export function ResourceStatus({
  resource
}) {
  if (resource.loading) return <p role="status">{t("Loading your records…")}</p>;
  if (resource.error) return <div className="error" role="alert">{resource.error}
    <button className="secondary ml-4" onClick={resource.retry}>{t("Retry")}</button></div>;
  return null;
}
