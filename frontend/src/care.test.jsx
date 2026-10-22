import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CarePage, PassportPage, TimelinePage } from './care.jsx';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it('saves a symptom with explicit timezone and refreshes history', async () => {
  let rows = []; let submitted;
  vi.stubGlobal('fetch', vi.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      submitted = JSON.parse(options.body);
      rows = [{ ...submitted, id: 's1' }];
    }
    return { ok: true, status: 200, json: async () => options.method === 'POST' ? rows[0] : rows };
  }));
  render(<CarePage kind="symptoms" />);
  await screen.findByText('No records yet.');
  fireEvent.change(screen.getByLabelText('Symptom description'), { target: { value: 'Nausea' } });
  fireEvent.change(screen.getByLabelText('When it occurred'), { target: { value: '2026-01-01T10:00' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save symptom' }));
  expect(await screen.findByRole('heading', { name: 'Nausea' })).toBeInTheDocument();
  expect(submitted.occurred_at.endsWith('Z')).toBe(true);
});
it('updates medication record status through its owned endpoint', async () => {
  let active = true;
  vi.stubGlobal('fetch', vi.fn(async (url, options = {}) => {
    if (options.method === 'PATCH') active = JSON.parse(options.body).active;
    return { ok: true, status: 200, json: async () => [{ id: 'm1', name: 'Prescribed medicine', dose: 'Dose', schedule: 'Morning', prescriber: 'Doctor', active }] };
  }));
  render(<CarePage kind="medications" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Mark inactive' }));
  expect(await screen.findByText('Listed as inactive')).toBeInTheDocument();
  expect(fetch.mock.calls.some(([url, opt]) => url === '/api/patients/me/medications/m1' && opt.method === 'PATCH')).toBe(true);
});
it('renders timeline server errors with retry', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => ({ detail: 'Unavailable' }) })));
  render(<MemoryRouter><TimelinePage /></MemoryRouter>);
  const events = within(screen.getByRole('region', { name: 'Recorded care events' }));
  expect(await events.findByRole('alert')).toHaveTextContent('Unavailable');
  expect(events.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
});
it('exports escaped patient text and supports browser PDF printing', async () => {
  let exported;
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => ({
    patient: { full_name: '<script>test</script>', email: 'p@example.com' }, profile: {},
    generated_at: '2026-01-01T00:00:00Z', active_medications: [], recent_timeline: [], timeline_limit: 100, notice: 'Patient summary'
  }) })));
  vi.stubGlobal('Blob', class { constructor(parts) { exported = parts.join(''); } });
  URL.createObjectURL = vi.fn(() => 'blob:test'); URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  const print = vi.spyOn(window, 'print').mockImplementation(() => {});
  render(<PassportPage />);
  fireEvent.click(await screen.findByRole('button', { name: 'Download health passport' }));
  await waitFor(() => expect(exported).toContain('&lt;script&gt;test&lt;/script&gt;'));
  expect(exported).not.toContain('<script>');
  fireEvent.click(screen.getByRole('button', { name: 'Print / Save PDF' }));
  expect(print).toHaveBeenCalledOnce();
});
