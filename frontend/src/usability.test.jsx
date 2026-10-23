import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { InformationPage } from './ui.jsx';
import { OversightPage } from './extended.jsx';
import { setLanguage } from './i18n.js';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); setLanguage('en'); });
const mount = node => render(<MemoryRouter>{node}</MemoryRouter>);
const reply = data => ({ ok: true, status: 200, json: async () => data });

it.each([
  ['patient', 'Join a video consultation', 'Approve a doctor'],
  ['doctor', 'Review a patient assessment', 'Share a report on WhatsApp'],
  ['admin', 'Approve a doctor', 'Join a video consultation'],
])('gives %s relevant help without developer diagnostics', (role, title, hidden) => {
  vi.stubGlobal('fetch', vi.fn());
  mount(<InformationPage kind="help" role={role} />);
  expect(screen.getByRole('heading', { name: title })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: hidden })).not.toBeInTheDocument();
  expect(screen.queryByText('Application version')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Check server version' })).not.toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});

it('loads access history on demand and shows human areas and outcomes rather than API routes', async () => {
  vi.stubGlobal('fetch', vi.fn(async url => reply(url.startsWith('/api/admin/audit') ? [
    { id: 'event-1', actor: 'Example Doctor', method: 'GET', route: '/api/doctors/me/appointments/{appointment_id}', status_code: 403, created_at: '2026-10-22T10:00:00Z' },
  ] : { account_roles: { patient: 3, doctor: 1 }, appointment_status: { PENDING: 2 }, clinical_review_status: {}, assessment_categories: {}, symptom_severity: {}, report_count: 4, message_count: 8, active_medications: 2, registrations_last_30_days: 3, report_bytes: 1048576 })));
  mount(<OversightPage />);
  await screen.findByText('Saved reports');
  expect(screen.getByText('Requested')).toBeInTheDocument();
  expect(fetch.mock.calls.some(([url]) => url.includes('/admin/audit'))).toBe(false);
  fireEvent.click(screen.getByText('Access history'));
  expect(await screen.findByText('Example Doctor')).toBeInTheDocument();
  expect(screen.getByText('Appointments · Access not granted')).toBeInTheDocument();
  expect(screen.queryByText(/appointment_id/)).not.toBeInTheDocument();
  expect(screen.queryByText('403')).not.toBeInTheDocument();
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.includes('/admin/audit'))).toHaveLength(1));
});
