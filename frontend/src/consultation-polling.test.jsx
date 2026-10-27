import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, test, vi } from 'vitest';
import { api } from './api.js';
import { ConsultationPage } from './consultation.jsx';

vi.mock('./api.js', () => ({ api: vi.fn() }));

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

test.each([
  ['3000', 3000],
  ['not-a-number', 3000]
])('call signaling respects the hosting interval %s and stops after leaving', async (value, delay) => {
  vi.useFakeTimers();
  vi.stubEnv('VITE_CALL_SIGNAL_POLL_MS', value);
  const stop = vi.fn();
  const track = { stop };
  const stream = { getTracks: () => [track] };
  const close = vi.fn();
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(stream) } });
  vi.stubGlobal('RTCPeerConnection', class {
    addTrack() {}
    close = close;
  });
  api.mockImplementation(async path => path.endsWith('/consultation')
    ? { id: 'call-1', ice_servers: [] } : []);
  const page = render(<MemoryRouter initialEntries={['/patient/appointments/appointment-1/call']}>
    <Routes><Route path="/patient/appointments/:appointmentId/call"
      element={<ConsultationPage role="patient" />} /></Routes>
  </MemoryRouter>);
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Join consultation' })));
  expect(api).toHaveBeenCalledWith('/appointments/appointment-1/consultation');
  const polls = () => api.mock.calls.filter(([path]) => path.includes('/signals')).length;
  expect(polls()).toBe(1);
  await act(async () => vi.advanceTimersByTime(delay - 1));
  expect(polls()).toBe(1);
  await act(async () => vi.advanceTimersByTime(1));
  expect(polls()).toBe(2);
  page.unmount();
  await act(async () => vi.advanceTimersByTime(delay * 2));
  expect(polls()).toBe(2);
  expect(stop).toHaveBeenCalledOnce();
  expect(close).toHaveBeenCalledOnce();
});

test.each([503, 403])('signaling failure %s only reconnects when temporary', async status => {
  vi.useFakeTimers();
  const stop = vi.fn();
  const close = vi.fn();
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }) } });
  vi.stubGlobal('RTCPeerConnection', class { addTrack() {} close = close; });
  let polls = 0;
  api.mockImplementation(async path => {
    if (path.endsWith('/consultation')) return { id: 'call-1', ice_servers: [] };
    if (++polls === 1) throw Object.assign(new Error('Unavailable'), { status });
    return [];
  });
  const page = render(<MemoryRouter initialEntries={['/patient/appointments/a/call']}>
    <Routes><Route path="/patient/appointments/:appointmentId/call" element={<ConsultationPage role="patient" />} /></Routes>
  </MemoryRouter>);
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Join consultation' })));
  if (status === 503) {
    expect(close).not.toHaveBeenCalled();
    expect(stop).not.toHaveBeenCalled();
    await act(async () => vi.advanceTimersByTime(3000));
    expect(polls).toBe(2);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  } else {
    expect(close).toHaveBeenCalledOnce();
    await act(async () => vi.advanceTimersByTime(3000));
    expect(polls).toBe(1);
  }
  page.unmount();
});
