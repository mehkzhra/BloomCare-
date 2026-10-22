export const SESSION_REJECTED_EVENT = 'bloomcare:session-rejected';
const publicAuthPaths = new Set(['/auth/me', '/auth/login', '/auth/register', '/auth/register-doctor', '/auth/forgot-password', '/auth/reset-password', '/auth/verification/request', '/auth/verification/confirm']);

export async function api(path, { method = 'GET', body, signal, raw = false, headers = {}, responseType = 'json', timeoutMs } = {}) {
  const controller = new AbortController();
  const cancel = () => controller.abort(signal.reason);
  if (signal?.aborted) cancel();
  else signal?.addEventListener('abort', cancel, { once: true });
  let timedOut = false;
  const limit = timeoutMs ?? (publicAuthPaths.has(path) || method === 'GET' ? 15000
    : path === '/patients/me/assistant' || path.endsWith('/care-plan') ? 60000 : 30000);
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, limit);
  try {
    const response = await fetch(`/api${path}`, {
      method, credentials: 'include', signal: controller.signal,
      headers: { ...(body && !raw ? { 'Content-Type': 'application/json' } : {}), ...headers },
      body: body ? (raw ? body : JSON.stringify(body)) : undefined,
    });
    if (response.status === 204) return null;
    if (response.ok && responseType === 'blob') {
      const blob = await response.blob();
      return blob;
    }
    const data = await response.json().catch(error => {
      if (controller.signal.aborted) throw error;
      return {};
    });
    if (!response.ok) {
      if (response.status === 401 && !publicAuthPaths.has(path) && !controller.signal.aborted) {
        window.dispatchEvent(new Event(SESSION_REJECTED_EVENT));
      }
      const detail = Array.isArray(data.detail)
        ? data.detail.map(item => `${item.loc.slice(1).join('.')}: ${item.msg}`).join('; ')
        : typeof data.detail === 'string' ? data.detail
          : data.detail?.message || `Request failed (${response.status})`;
      const error = new Error(detail);
      error.status = response.status;
      error.details = data.detail;
      const retry = Number(response.headers?.get?.('Retry-After'));
      if (Number.isFinite(retry) && retry > 0) error.retryAfterSeconds = retry;
      throw error;
    }
    return data;
  } catch (error) {
    if (timedOut && !signal?.aborted) {
      const timeout = new Error(method === 'GET' || publicAuthPaths.has(path)
        ? 'BloomCare is taking too long to respond. Check the connection and try again.'
        : 'The request timed out. Check your records before trying again; the action may have completed.');
      timeout.code = 'REQUEST_TIMEOUT';
      throw timeout;
    }
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', cancel);
  }
}
