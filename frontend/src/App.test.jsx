import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App.jsx';
import { emptyPatientWorkspace } from './workspace-fixtures.js';

const patient = { id: 'patient-1', role: 'patient', full_name: 'Patient', email: 'patient@example.com' };
let loggedIn;
let records;
let savedHealth;
let protectedStatus;
let loginRejected;

beforeEach(() => {
  loggedIn = false; records = []; savedHealth = null; protectedStatus = 200; loginRejected = false;
  vi.stubGlobal('fetch', vi.fn(async (url, options = {}) => {
    let status = 200; let data = {};
    if (!url.startsWith('/api/auth/') && protectedStatus >= 400) {
      status = protectedStatus; data = { detail: protectedStatus === 401 ? 'Please sign in' : 'Access denied' };
    }
    else if (url === '/api/auth/me') { status = loggedIn ? 200 : 401; data = loggedIn ? patient : { detail: 'Please sign in' }; }
    else if (url === '/api/auth/login') {
      if (loginRejected) { status = 401; data = { detail: 'Incorrect email or password' }; }
      else { loggedIn = true; data = patient; }
    }
    else if (url === '/api/auth/register') { status = 201; data = patient; }
    else if (url === '/api/doctors') data = [];
    else if (url === '/api/patients/me/workspace') data = emptyPatientWorkspace();
    else if (url.startsWith('/api/patients/me/health-records')) {
      if (options.method === 'POST') {
        savedHealth = JSON.parse(options.body);
        data = { id: 'record-1', created_at: new Date().toISOString(), observations: savedHealth };
        records.push(data); status = 201;
      } else data = records;
    }
    return { ok: status < 400, status, json: async () => data };
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function start(path) { render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>); }
function fillHealthForm() {
  fireEvent.change(screen.getByLabelText('Glucose unit'), { target: { value: 'mmol/L' } });
  fireEvent.change(screen.getByLabelText('Temperature unit'), { target: { value: '°C' } });
  for (const [label, value] of [['Age (years)', '27'], ['Pregnancy duration (weeks)', '24'],
    ['Systolic blood pressure (mmHg)', '120'], ['Diastolic blood pressure (mmHg)', '80'],
    ['Blood glucose (mmol/L)', '5.12'], ['Body temperature (°C)', '36.85'], ['Heart rate (beats/minute)', '78']]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
}

describe('patient application flows', () => {
  it('redirects a signed-out visitor from a protected page to login', async () => {
    start('/patient/history');
    expect(await screen.findByText('Welcome back')).toBeInTheDocument();
    expect(screen.queryByText('Health history')).not.toBeInTheDocument();
  });
  it('logs in and shows actual empty history without a fake prediction', async () => {
    start('/login');
    await screen.findByText('Welcome back');
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'patient@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'ValidPassword123!' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    });
    expect(await screen.findByRole('heading', { name: 'Your health, at a glance.' })).toBeInTheDocument();
    expect(await screen.findByText('No approved doctors have been added yet.')).toBeInTheDocument();
    expect(await screen.findByText(/Health screening is currently unavailable/)).toBeInTheDocument();
  });
  it('saves numeric measurements through the API and renders stored history', async () => {
    loggedIn = true; start('/patient/health');
    await screen.findByText('Add health observations');
    fillHealthForm();
    fireEvent.click(screen.getByRole('button', { name: 'Save health record' }));
    expect(await screen.findByText('Health history')).toBeInTheDocument();
    expect(await screen.findByText('120')).toBeInTheDocument();
    expect(savedHealth.glucose_mmol_l).toBe(5.12);
    expect(savedHealth.temperature_c).toBe(36.85);
  });
  it('blocks a patient from the admin route', async () => {
    loggedIn = true; start('/admin');
    expect(await screen.findByText('Your health, at a glance.')).toBeInTheDocument();
    expect(screen.queryByText('BloomCare administration')).not.toBeInTheDocument();
  });
  it('shows an explicit connection error when the server is unavailable', async () => {
    fetch.mockRejectedValue(new Error('Network unavailable'));
    start('/');
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Unable to reach'));
  });
  it('leaves session loading after a timeout and can retry the connection', async () => {
    vi.useFakeTimers();
    try {
      fetch.mockImplementationOnce((url, options) => new Promise((resolve, reject) => {
        options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
      }));
      start('/');
      expect(screen.getByRole('status')).toHaveTextContent('Checking your session');
      await act(async () => { await vi.advanceTimersByTimeAsync(15000); });
      expect(screen.getByRole('alert')).toHaveTextContent('taking too long');
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
      await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Retry connection' })); });
      expect(screen.getByRole('heading', { name: 'A clearer path. A little more care.' })).toBeInTheDocument();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    } finally { vi.useRealTimers(); }
  });
  it('shows a database outage without leaving the visitor stuck in session loading', async () => {
    fetch.mockResolvedValue({ ok: false, status: 503, json: async () => ({ detail: 'Database temporarily unavailable' }) });
    start('/login');
    expect(await screen.findByRole('alert')).toHaveTextContent('Database temporarily unavailable');
    expect(screen.queryByText('Checking your session…')).not.toBeInTheDocument();
    expect(screen.getByText('Welcome back')).toBeInTheDocument();
  });
  it('returns to sign-in after a protected read rejects the session and clears the notice on login', async () => {
    loggedIn = true; start('/patient/history');
    await screen.findByText('Health history');
    protectedStatus = 401;
    fireEvent.click(screen.getByRole('link', { name: 'Assessments' }));
    expect(await screen.findByText('Welcome back')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Your session is no longer valid');
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
    protectedStatus = 200;
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'patient@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'ValidPassword123!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Your health, at a glance.')).toBeInTheDocument();
    expect(screen.queryByText(/Your session is no longer valid/)).not.toBeInTheDocument();
  });
  it('returns to sign-in when a record submission rejects the session without reporting a save', async () => {
    loggedIn = true; start('/patient/health');
    await screen.findByText('Add health observations');
    fillHealthForm(); protectedStatus = 401;
    fireEvent.click(screen.getByRole('button', { name: 'Save health record' }));
    expect(await screen.findByText('Welcome back')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Your session is no longer valid');
    expect(savedHealth).toBeNull();
  });
  it('shows incorrect login credentials without calling them an expired session', async () => {
    loginRejected = true; start('/login');
    await screen.findByText('Welcome back');
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'patient@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'WrongPassword123!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Incorrect email or password')).toBeInTheDocument();
    expect(screen.queryByText(/Your session is no longer valid/)).not.toBeInTheDocument();
  });
  it('keeps the session when a protected request is forbidden rather than unauthenticated', async () => {
    loggedIn = true; protectedStatus = 403; start('/patient/history');
    expect(await screen.findByText('Access denied')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();
    expect(screen.getByText('Health history')).toBeInTheDocument();
    expect(screen.queryByText('Welcome back')).not.toBeInTheDocument();
  });
  it('ignores a late unauthorized response from a page that was already left', async () => {
    loggedIn = true;
    const normalFetch = fetch.getMockImplementation();
    let finishOldRequest;
    fetch.mockImplementation((url, options) => url === '/api/patients/me/health-records?offset=0'
      ? new Promise(resolve => { finishOldRequest = resolve; })
      : normalFetch(url, options));
    start('/patient/history');
    await screen.findByText('Health history');
    fireEvent.click(screen.getByRole('link', { name: 'Health record' }));
    await screen.findByText('Add health observations');
    await act(async () => finishOldRequest({ ok: false, status: 401, json: async () => ({ detail: 'Please sign in' }) }));
    expect(screen.getByText('Add health observations')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();
    expect(screen.queryByText(/Your session is no longer valid/)).not.toBeInTheDocument();
  });
});
