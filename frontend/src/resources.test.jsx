import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { api } from './api.js';
import { useResource } from './resources.jsx';
vi.mock('./api.js', () => ({ api: vi.fn() }));
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); vi.resetAllMocks(); });

test('slow polling never overlaps and refresh keeps the previous records', async () => {
  vi.useFakeTimers();
  let resolve;
  api.mockResolvedValueOnce(['record']).mockImplementationOnce(() => new Promise(done => { resolve = done; }));
  const hook = renderHook(() => useResource('/records', { pollMs: 1000 }));
  await act(async () => {});
  await act(async () => vi.advanceTimersByTime(1000));
  expect(hook.result.current.data).toEqual(['record']);
  expect(hook.result.current.loading).toBe(false);
  await act(async () => vi.advanceTimersByTime(5000));
  expect(api).toHaveBeenCalledTimes(2);
  await act(async () => resolve(['updated']));
  expect(hook.result.current.data).toEqual(['updated']);
  hook.unmount();
});

test('failed refresh preserves records, but a different path cannot see them', async () => {
  api.mockResolvedValueOnce(['private record']).mockRejectedValueOnce(new Error('Temporary outage'))
    .mockImplementationOnce(() => new Promise(() => {}));
  const hook = renderHook(({ path }) => useResource(path), { initialProps: { path: '/a' } });
  await act(async () => {});
  await act(async () => hook.result.current.retry());
  expect(hook.result.current.data).toEqual(['private record']);
  expect(hook.result.current.error).toBe('Temporary outage');
  hook.rerender({ path: '/b' });
  expect(hook.result.current.data).toBeNull();
  expect(hook.result.current.loading).toBe(true);
  hook.unmount();
});

test('hidden tabs stop polling and resume once visible', async () => {
  vi.useFakeTimers();
  const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
  api.mockResolvedValue([]);
  const hook = renderHook(() => useResource('/records', { pollMs: 1000 }));
  await act(async () => {});
  hidden.mockReturnValue(true);
  act(() => document.dispatchEvent(new Event('visibilitychange')));
  await act(async () => vi.advanceTimersByTime(10000));
  expect(api).toHaveBeenCalledTimes(1);
  hidden.mockReturnValue(false);
  await act(async () => document.dispatchEvent(new Event('visibilitychange')));
  expect(api).toHaveBeenCalledTimes(2);
  hook.unmount();
});
