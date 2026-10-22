import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import App from './App.jsx';
import { HealthPage } from './pages.jsx';
import { MessagesPage, NotificationsPage, ReportsPage } from './communication.jsx';
import { api, SESSION_REJECTED_EVENT } from './api.js';

const reply = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('shows and hides the same password without submitting', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => reply({}, 401)));
  render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>);
  const input = await screen.findByLabelText('Password');
  fireEvent.change(input, { target: { value: 'PrivatePassword123!' } });
  fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
  expect(input).toHaveAttribute('type', 'text'); expect(input.value).toBe('PrivatePassword123!');
  fireEvent.click(screen.getByRole('button', { name: 'Hide password' }));
  expect(input).toHaveAttribute('type', 'password');
  expect(fetch.mock.calls.some(([url]) => url === '/api/auth/login')).toBe(false);
});
it('uses model limits as faint empty range placeholders', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => reply({ assessment_ranges: { glucose_mmol_l: [6, 19] } })));
  render(<MemoryRouter><HealthPage /></MemoryRouter>);
  fireEvent.change(screen.getByLabelText('Glucose unit'), { target: { value: 'mmol/L' } });
  await waitFor(() => expect(screen.getByLabelText('Blood glucose (mmol/L)')).toHaveAttribute('placeholder', '6–19'));
  expect(screen.getByLabelText('Blood glucose (mmol/L)')).toHaveAttribute('min', '1');
  expect(screen.getByLabelText('Blood glucose (mmol/L)').value).toBe('');
});
it('uploads raw report bytes and refreshes the list', async () => {
  let uploaded = false;
  vi.stubGlobal('fetch', vi.fn(async (url, opt = {}) => {
    if (opt.method === 'POST') uploaded = true;
    if (url.includes('/appointments')) return reply([]);
    return reply(uploaded ? [{ id: 'r', title: 'CBC report', byte_size: 10, created_at: '2026-01-01T00:00:00Z', media_type: 'application/pdf' }] : []);
  }));
  render(<ReportsPage />); await screen.findByText('No reports yet.');
  fireEvent.change(screen.getByLabelText('Report title'), { target: { value: 'CBC report' } });
  const file = new File(['%PDF-1.4'], 'report.pdf', { type: 'application/pdf' });
  fireEvent.change(screen.getByLabelText('Report file'), { target: { files: [file] } });
  fireEvent.submit(screen.getByRole('button', { name: 'Upload report' }).closest('form'));
  await screen.findByRole('heading', { name: 'CBC report' });
  const call = fetch.mock.calls.find(([, opt]) => opt.method === 'POST');
  expect(call[1].body).toBe(file); expect(call[1].headers['X-Report-Title']).toBe('CBC%20report');
});
it('requires explicit consent before report sharing', async () => {
  vi.stubGlobal('fetch', vi.fn(async url => {
    if (url === '/api/patients/me/appointments?offset=0') return reply([{ id: 'a', doctor_name: 'Doctor', scheduled_at: '2026-10-13T00:00:00Z', record_access_available: true }]);
    if (url.includes('/appointments/a/reports')) return reply([]);
    return reply([{ id: 'r', title: 'CBC report', byte_size: 10, created_at: '2026-01-01T00:00:00Z' }]);
  }));
  render(<ReportsPage />); await screen.findByRole('option', { name: /Doctor/ });
  fireEvent.change(screen.getByLabelText('Accepted appointment'), { target: { value: 'a' } });
  const button = await screen.findByRole('button', { name: 'Share report' });
  expect(button).toBeDisabled(); fireEvent.click(screen.getByRole('checkbox'));
  await waitFor(() => expect(button).not.toBeDisabled());
});
it('reuses message retry identifiers after a server failure', async () => {
  let sends = 0;
  vi.stubGlobal('fetch', vi.fn(async (url, opt = {}) => {
    if (opt.method === 'POST') return ++sends === 1 ? reply({ detail: 'Temporary failure' }, 503) : reply({ id: 'm' }, 201);
    return reply({ can_send: true, messages: [] });
  }));
  render(<MemoryRouter initialEntries={['/a']}><Routes><Route path="/:appointmentId" element={<MessagesPage role="patient" />} /></Routes></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText('Your message'), { target: { value: 'Question for doctor' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send message' })); await screen.findByRole('alert');
  await waitFor(() => expect(screen.getByRole('button', { name: 'Send message' })).not.toBeDisabled());
  fireEvent.click(screen.getByRole('button', { name: 'Send message' })); await waitFor(() => expect(sends).toBe(2));
  const bodies = fetch.mock.calls.filter(([, opt]) => opt.method === 'POST').map(([, opt]) => JSON.parse(opt.body));
  expect(bodies[0].client_message_id).toBe(bodies[1].client_message_id);
});
it('marks a notification read and refreshes the count', async () => {
  let read = false;
  vi.stubGlobal('fetch', vi.fn(async (url, opt = {}) => {
    if (opt.method === 'PATCH') read = true;
    return reply({ unread_count: read ? 0 : 1, items: [{ id: 'n', kind: 'NEW_MESSAGE', read, created_at: '2026-01-01T00:00:00Z' }] });
  }));
  render(<MemoryRouter><NotificationsPage role="patient" /></MemoryRouter>);
  fireEvent.click(await screen.findByRole('button', { name: 'Mark read' }));
  expect(await screen.findByText('0 unread')).toBeInTheDocument();
});
it('handles rejected sessions during binary downloads', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => reply({ detail: 'Sign in' }, 401)));
  const handler = vi.fn(); window.addEventListener(SESSION_REJECTED_EVENT, handler);
  try {
    await expect(api('/patients/me/reports/r/download', { responseType: 'blob' })).rejects.toThrow('Sign in');
    expect(handler).toHaveBeenCalledOnce();
  } finally { window.removeEventListener(SESSION_REJECTED_EVENT, handler); }
});
