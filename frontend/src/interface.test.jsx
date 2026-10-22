import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App.jsx';
import { ReportShareDialog, WHATSAPP_URL } from './report-share.jsx';
import { AssessmentCard } from './assessments.jsx';
import { setLanguage } from './i18n.js';
import { emptyPatientWorkspace } from './workspace-fixtures.js';

const patient = { id: 'p', full_name: 'Patient', role: 'patient' };
const report = { id: 'private-report-id', title: 'Private patient report', media_type: 'application/pdf' };
const response = data => ({ ok: true, status: 200, json: async () => data });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); setLanguage('en'); });

function portal(path = '/patient', appointments = []) {
  vi.stubGlobal('fetch', vi.fn(async url => {
    if (url === '/api/auth/me') return response(patient);
    if (url.includes('/notifications')) return response({ items: [], unread_count: 0 });
    if (url.includes('/capabilities')) return response({ pregnancy_model_ready: false });
    if (url === '/api/patients/me/workspace') return response(emptyPatientWorkspace());
    if (url.includes('/appointments')) return response(appointments);
    return response([]);
  }));
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

it('keeps six main patient links and groups the remaining tools', async () => {
  portal();
  await screen.findByText('Your health, at a glance.');
  const nav = screen.getByRole('navigation', { name: 'Main navigation' });
  expect(within(nav).getAllByRole('link')).toHaveLength(6);
  expect(within(nav).getByRole('link', { name: 'Assistant' })).toHaveAttribute('href', '/patient/assistant');
  const summary = screen.getByText('More care tools');
  expect(summary.closest('details')).not.toHaveAttribute('open');
  fireEvent.click(summary);
  expect(summary.closest('details')).toHaveAttribute('open');
  expect(screen.getByRole('link', { name: 'Medications' })).toHaveAttribute('href', '/patient/medications');
});

it('places video access in the header and only offers accepted episodes with access', async () => {
  portal('/patient/consultations', [
    { id: 'open', status: 'ACCEPTED', record_access_available: true, doctor_name: 'Current Doctor', scheduled_at: '2026-10-16T09:00:00Z' },
    { id: 'expired', status: 'ACCEPTED', record_access_available: false, doctor_name: 'Expired Doctor' },
    { id: 'pending', status: 'PENDING', record_access_available: true, doctor_name: 'Pending Doctor' },
  ]);
  expect(await screen.findByRole('heading', { name: 'Video consultations' })).toBeInTheDocument();
  const header = screen.getByRole('navigation', { name: 'Workspace actions' });
  expect(within(header).getByRole('link', { name: 'Video consultation' })).toHaveAttribute('href', '/patient/consultations');
  expect(await screen.findByRole('link', { name: 'Open consultation' })).toHaveAttribute('href', '/patient/appointments/open/consultation');
  expect(screen.queryByText('Expired Doctor')).not.toBeInTheDocument();
  expect(screen.queryByText('Pending Doctor')).not.toBeInTheDocument();
});

it('opens mobile navigation and closes it with Escape', async () => {
  portal(); await screen.findByText('Your health, at a glance.');
  const menu = screen.getByRole('button', { name: 'Open navigation' });
  fireEvent.click(menu);
  expect(menu).toHaveAttribute('aria-expanded', 'true');
  fireEvent.keyDown(window, { key: 'Escape' });
  expect(menu).toHaveAttribute('aria-expanded', 'false');
});

it('keeps the new navigation and video access usable in Urdu', async () => {
  portal(); await screen.findByText('Your health, at a glance.');
  fireEvent.change(screen.getByLabelText('Language'), { target: { value: 'ur' } });
  expect(await screen.findByRole('link', { name: 'ویڈیو مشاورت' })).toHaveAttribute('href', '/patient/consultations');
  expect(document.documentElement).toHaveAttribute('dir', 'rtl');
  expect(screen.getByText('مزید سہولیات')).toBeInTheDocument();
});

function sharing({ native = false, share = vi.fn().mockResolvedValue(undefined), denied = false } = {}) {
  const RealURL = URL;
  vi.stubGlobal('URL', class extends RealURL {
    static createObjectURL = vi.fn(() => 'blob:private-report');
    static revokeObjectURL = vi.fn();
  });
  vi.stubGlobal('navigator', { canShare: vi.fn(() => native), share });
  vi.stubGlobal('fetch', vi.fn(async () => denied
    ? { ok: false, status: 403, json: async () => ({ detail: 'Access denied' }) }
    : { ok: true, status: 200, blob: async () => new Blob(['%PDF-1.4 report bytes'], { type: 'application/pdf' }) }));
  const close = vi.fn();
  const view = render(<ReportShareDialog report={report} onClose={close} />);
  return { share, close, view };
}

it('requires consent and passes an actual file to the device share sheet', async () => {
  const { share } = sharing({ native: true });
  const button = await screen.findByRole('button', { name: 'Choose WhatsApp' });
  expect(button).toBeDisabled(); expect(share).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(button);
  await waitFor(() => expect(share).toHaveBeenCalledOnce());
  const data = share.mock.calls[0][0];
  expect(data.files[0]).toBeInstanceOf(File);
  expect(data.files[0].type).toBe('application/pdf');
  expect(data.files[0].size).toBeGreaterThan(0);
  expect(data).not.toHaveProperty('url');
  expect(JSON.stringify(data)).not.toContain(report.id);
  expect(await screen.findByRole('status')).toHaveTextContent('Confirm the recipient');
});

it('downloads a copy and opens WhatsApp without placing private data in its URL', async () => {
  sharing();
  const open = vi.spyOn(window, 'open').mockReturnValue(null);
  const download = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  const button = screen.getByRole('button', { name: 'Download & open WhatsApp' });
  expect(button).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox'));
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  expect(download).toHaveBeenCalledOnce();
  expect(open).toHaveBeenCalledWith(WHATSAPP_URL, '_blank', 'noopener,noreferrer');
  expect(WHATSAPP_URL).not.toContain(report.id);
  expect(decodeURIComponent(WHATSAPP_URL)).not.toContain(report.title);
  expect(WHATSAPP_URL).not.toContain('/api/');
  expect(screen.getByRole('status')).toHaveTextContent('Attach it in WhatsApp before sending');
});

it('treats cancellation as cancellation and never claims delivery', async () => {
  const share = vi.fn().mockRejectedValue(new DOMException('Cancelled', 'AbortError'));
  sharing({ native: true, share });
  const button = await screen.findByRole('button', { name: 'Choose WhatsApp' });
  fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(button);
  expect(await screen.findByRole('status')).toHaveTextContent('Sharing cancelled');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

it('cannot share a report when its authenticated download is denied', async () => {
  const { share } = sharing({ native: true, denied: true });
  expect(await screen.findByRole('alert')).toHaveTextContent('Access denied');
  fireEvent.click(screen.getByRole('checkbox'));
  expect(screen.getByRole('button', { name: 'Download & open WhatsApp' })).toBeDisabled();
  expect(share).not.toHaveBeenCalled();
});

function assessment(risk) {
  return { id: 'a', health_record_id: 'r', maternal_risk: risk, created_at: '2026-10-15T08:00:00Z',
    model: { version: 'v', source: { name: 'Source', license: 'CC BY 4.0' }, limitations: [], evaluation: { accuracy: .7, medium_recall: .33, held_out_rows: 90 } },
    class_scores: { LOW: .2, MEDIUM: .3, HIGH: .5 }, explanation: { features: [], base_score: .3, model_score: .5 },
  };
}
it.each(['MEDIUM', 'HIGH'])('includes PE review in a %s assessment without inventing a PE prediction', risk => {
  render(<MemoryRouter><AssessmentCard assessment={assessment(risk)} /></MemoryRouter>);
  expect(screen.getByRole('heading', { name: 'Pre-eclampsia screening' })).toBeInTheDocument();
  expect(screen.getByText(/PE screening is currently unavailable/)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Arrange a doctor review' })).toHaveAttribute('href', '/patient/appointments?review=pe&record=r');
});
it('does not present a low maternal category as a negative PE diagnosis', () => {
  render(<MemoryRouter><AssessmentCard assessment={assessment('LOW')} /></MemoryRouter>);
  expect(screen.queryByRole('heading', { name: 'Pre-eclampsia screening' })).not.toBeInTheDocument();
  expect(screen.getByText(/low category does not rule out pre-eclampsia/)).toBeInTheDocument();
});
it('keeps the clinician assessment view free of patient appointment actions', () => {
  render(<MemoryRouter><AssessmentCard assessment={assessment('HIGH')} viewerRole="doctor" /></MemoryRouter>);
  expect(screen.queryByRole('link', { name: 'Arrange a doctor review' })).not.toBeInTheDocument();
});
