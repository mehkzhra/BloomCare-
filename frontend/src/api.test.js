import { afterEach, expect, it, vi } from 'vitest';
import { api, SESSION_REJECTED_EVENT } from './api.js';

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

function stallUntilAborted(signal) {
  return new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
  });
}

it('ends a stalled session check after 15 seconds and leaves caller cancellation untouched', async () => {
  vi.useFakeTimers();
  const caller = new AbortController();
  vi.stubGlobal('fetch', vi.fn((url, options) => stallUntilAborted(options.signal)));
  const failure = api('/auth/me', { signal: caller.signal }).catch(error => error);
  await vi.advanceTimersByTimeAsync(15000);
  expect((await failure).code).toBe('REQUEST_TIMEOUT');
  expect(caller.signal.aborted).toBe(false);
  expect(fetch).toHaveBeenCalledOnce();
});

it('bounds a stalled response body as well as the initial connection', async () => {
  vi.useFakeTimers();
  vi.stubGlobal('fetch', vi.fn(async (url, options) => ({
    ok: true, status: 200, json: () => stallUntilAborted(options.signal),
  })));
  const failure = api('/patients/me/profile', { timeoutMs: 100 }).catch(error => error);
  await vi.advanceTimersByTimeAsync(100);
  expect((await failure).code).toBe('REQUEST_TIMEOUT');
});

it('preserves page cancellation without dispatching a session-expired event', async () => {
  const caller = new AbortController();
  const rejected = vi.fn();
  window.addEventListener(SESSION_REJECTED_EVENT, rejected);
  try {
    vi.stubGlobal('fetch', vi.fn((url, options) => stallUntilAborted(options.signal)));
    const failure = api('/patients/me/profile', { signal: caller.signal }).catch(error => error);
    caller.abort();
    expect((await failure).name).toBe('AbortError');
    expect(rejected).not.toHaveBeenCalled();
  } finally { window.removeEventListener(SESSION_REJECTED_EVENT, rejected); }
});

it('keeps database outages distinct from expired sessions and shows the server message', async () => {
  const rejected = vi.fn();
  window.addEventListener(SESSION_REJECTED_EVENT, rejected);
  try {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: false, status: 503, json: async () => ({ detail: 'Database temporarily unavailable' }),
    })));
    await expect(api('/patients/me/profile')).rejects.toMatchObject({
      status: 503, message: 'Database temporarily unavailable',
    });
    expect(rejected).not.toHaveBeenCalled();
  } finally { window.removeEventListener(SESSION_REJECTED_EVENT, rejected); }
});

it('does not automatically retry a timed-out write or claim that it was saved', async () => {
  vi.useFakeTimers();
  vi.stubGlobal('fetch', vi.fn((url, options) => stallUntilAborted(options.signal)));
  const failure = api('/patients/me/symptoms', { method: 'POST', body: { symptom: 'Demo' } })
    .catch(error => error);
  await vi.advanceTimersByTimeAsync(30000);
  expect((await failure).message).toContain('Check your records');
  expect(fetch).toHaveBeenCalledOnce();
});
