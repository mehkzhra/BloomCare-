import { useEffect, useState } from 'react';
import { api } from './api.js';
import { t } from './i18n.js';
export function useResource(path, {
  pollMs = 0,
  validate
} = {}) {
  const [state, setState] = useState({
    data: null,
    error: '',
    loading: true
  });
  const [attempt, setAttempt] = useState(0);
  const key = `${path}:${attempt}`;
  useEffect(() => {
    if (!pollMs) return;
    const timer = setInterval(() => setAttempt(n => n + 1), pollMs);
    return () => clearInterval(timer);
  }, [pollMs]);
  useEffect(() => {
    const controller = new AbortController();
    api(path, {
      signal: controller.signal
    }).then(data => {
      if (validate && !validate(data)) throw new Error('The workspace response could not be read. Refresh and try again.');
      if (!controller.signal.aborted) setState({
        data,
        error: '',
        loading: false,
        key
      });
    }).catch(err => {
      if (!controller.signal.aborted) setState({
        data: null,
        error: err.message,
        loading: false,
        key
      });
    });
    return () => controller.abort();
  }, [path, key, validate]);
  const current = state.key === key ? state : {
    data: null,
    error: '',
    loading: true
  };
  return {
    ...current,
    retry: () => setAttempt(n => n + 1)
  };
}
export function ResourceStatus({
  resource
}) {
  if (resource.loading) return <p role="status">{t("Loading your records…")}</p>;
  if (resource.error) return <div className="error" role="alert">{resource.error}
    <button className="secondary ml-4" onClick={resource.retry}>{t("Retry")}</button></div>;
  return null;
}
