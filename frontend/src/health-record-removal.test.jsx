import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { HistoryPage } from './pages.jsx';
import { HealthRecordRemoval, RemovedHealthRecords } from './assessment-removal.jsx';
import { ReleaseCheck, APP_VERSION } from './release-check.jsx';
import { AdminWorkspace } from './workspaces.jsx';
import { emptyAdminWorkspace } from './workspace-fixtures.js';
import { setLanguage } from './i18n.js';

const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
const mount = node => render(<MemoryRouter>{node}</MemoryRouter>);
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); setLanguage('en'); });

it('shows an explicit linked-assessment warning and posts only after confirmation', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ id: 'record-1' })));
  const removed = vi.fn(); mount(<HealthRecordRemoval recordId="record-1" onRemoved={removed} />);
  fireEvent.click(screen.getByRole('button', { name: 'Delete health record' }));
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.getByRole('alertdialog')).toHaveTextContent('all linked assessments');
  expect(screen.getByRole('alertdialog')).toHaveTextContent('dated audit copy remain');
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Wrong measurement date' } });
  fireEvent.submit(screen.getByRole('alertdialog'));
  expect(await screen.findByRole('status')).toHaveTextContent('Health record and linked assessments deleted from active care.');
  const [url, options] = fetch.mock.calls[0];
  expect(url).toBe('/api/patients/me/health-records/record-1');
  expect(options.method).toBe('DELETE');
  expect(JSON.parse(options.body)).toEqual({ reason: 'Wrong measurement date' });
  expect(removed).toHaveBeenCalledTimes(1);
});
it('cancels record deletion without a request and restores focus', () => {
  vi.stubGlobal('fetch', vi.fn()); mount(<HealthRecordRemoval recordId="record-1" />);
  const button = screen.getByRole('button', { name: 'Delete health record' }); button.focus(); fireEvent.click(button);
  fireEvent.click(screen.getByRole('button', { name: 'Keep health record' }));
  expect(button).toHaveFocus(); expect(fetch).not.toHaveBeenCalled();
});
it('puts a visible record-delete action in Health history and removes a successfully deleted row', async () => {
  let active = true;
  vi.stubGlobal('fetch', vi.fn(async (url, options = {}) => {
    if (options.method === 'DELETE') { active = false; return response({ id: 'record-1' }); }
    if (url.startsWith('/api/patients/me/health-records?')) return response(active ? [{ id: 'record-1', created_at: '2026-10-18T10:00:00Z', observations: { age_years: 27, gestational_weeks: 24, systolic_mmhg: 120, diastolic_mmhg: 80, glucose_mmol_l: 7, temperature_c: 37, heart_rate_bpm: 78 } }] : []);
    return response([]);
  }));
  mount(<HistoryPage />);
  fireEvent.click(await screen.findByRole('button', { name: 'Delete health record' }));
  fireEvent.change(screen.getByRole('textbox', { name: 'Reason for deletion' }), { target: { value: 'Incorrect reading' } });
  fireEvent.submit(screen.getByRole('alertdialog'));
  expect(await screen.findByRole('status')).toHaveTextContent('Health record and linked assessments deleted from active care.');
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Delete health record' })).not.toBeInTheDocument());
  expect(await screen.findByText(/No health records on this page/)).toBeInTheDocument();
});
it('keeps the record visible if the server rejects deletion', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ detail: 'Please retry later' }, 503)));
  mount(<HealthRecordRemoval recordId="record-1" />);
  fireEvent.click(screen.getByRole('button', { name: 'Delete health record' }));
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Incorrect reading' } });
  fireEvent.submit(screen.getByRole('alertdialog'));
  expect(await screen.findByRole('alert')).toHaveTextContent('Please retry later');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});
it('loads only deletion metadata when the record log is opened', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response([{ id: 'r1', created_at: '2026-10-17T10:00:00Z', removed_at: '2026-10-18T10:00:00Z', reason: 'Incorrect record' }])));
  mount(<RemovedHealthRecords />); expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Deleted health record log'));
  expect(await screen.findByText('Incorrect record')).toBeInTheDocument();
  expect(fetch.mock.calls[0][0]).toBe('/api/patients/me/removed-health-records?offset=0');
});
it.each([[APP_VERSION, false], ['1.0.0', true]])('checks a server version on demand and explains mismatches', async (version, mismatch) => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ status: 'ok', version })));
  mount(<ReleaseCheck />); expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Check server version' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Server version');
  if (mismatch) expect(screen.getByRole('alert')).toHaveTextContent('versions differ');
  else expect(screen.getByText('The interface and server versions match.')).toBeInTheDocument();
});
it('keeps the administrator focused on accounts and care rather than model metrics', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response(emptyAdminWorkspace())));
  mount(<AdminWorkspace />); await screen.findByText('Applications are up to date');
  expect(screen.queryByText('Model evaluation & evidence')).not.toBeInTheDocument();
  expect(screen.queryByText('71.1%')).not.toBeInTheDocument();
  expect(screen.queryByText('33.3%')).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Manage accounts' })).toHaveAttribute('href', '/admin/accounts');
  expect(fetch.mock.calls.some(([url]) => url.includes('model-evaluation') || url.includes('training-evidence'))).toBe(false);
});
