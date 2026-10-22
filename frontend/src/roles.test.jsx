import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App.jsx';
import { AdminAccounts } from './admin.jsx';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('registers a doctor through the web without approval or role escalation fields', async () => {
  vi.stubGlobal('fetch', vi.fn(async url => ({ ok: url !== '/api/auth/me', status: url === '/api/auth/me' ? 401 : 201, json: async () => ({}) })));
  render(<MemoryRouter initialEntries={['/register']}><App /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText('Register as'), { target: { value: 'doctor' } });
  for (const [label, value] of [['Full name', 'Web Doctor'], ['Email address', 'web@example.com'], ['Password', 'ValidPassword123!'], ['Registration number', 'WEB-10'], ['Specialty', 'Obstetrics']]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
  fireEvent.click(screen.getByRole('button', { name: 'Create doctor account' }));
  expect(await screen.findByText(/Admin approval is required/)).toBeInTheDocument();
  const call = fetch.mock.calls.find(([url]) => url === '/api/auth/register-doctor');
  const body = JSON.parse(call[1].body);
  expect(body.registration_number).toBe('WEB-10');
  expect(body).not.toHaveProperty('role'); expect(body).not.toHaveProperty('approved');
});
it('offers all three login roles and only patient or doctor registration', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 401, json: async () => ({}) })));
  render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>);
  await screen.findByLabelText('Sign in as');
  expect(screen.getByRole('option', { name: 'Admin' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('link', { name: 'Create an account' }));
  await screen.findByLabelText('Register as');
  expect(screen.queryByRole('option', { name: 'Admin' })).not.toBeInTheDocument();
});
it('admin approves a pending doctor and sees refreshed status', async () => {
  let approved = false;
  vi.stubGlobal('fetch', vi.fn(async (url, opts = {}) => {
    if (opts.method === 'PATCH') approved = JSON.parse(opts.body).approved;
    const data = url.startsWith('/api/admin/accounts') ? [{ id: 'd', full_name: 'Pending Doctor', role: 'doctor', email: 'd@example.com', active: true, approved, registration_number: 'WEB', specialty: 'Obstetrics' }] : [];
    return { ok: true, status: 200, json: async () => data };
  }));
  render(<MemoryRouter><AdminAccounts /></MemoryRouter>);
  fireEvent.click(await screen.findByRole('button', { name: 'Approve doctor' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Revoke doctor approval' })).toBeInTheDocument());
  expect(fetch.mock.calls.some(([url, opt]) => url === '/api/admin/doctors/d/approval' && opt.method === 'PATCH')).toBe(true);
});
