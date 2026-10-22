import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App.jsx';

const patient = { id: 'patient-1', role: 'patient', full_name: 'Patient', email: 'patient@example.com' };
const observations = {
  age_years: 25, gestational_weeks: 24, systolic_mmhg: 120, diastolic_mmhg: 80,
  glucose_mmol_l: 7, temperature_c: 37, heart_rate_bpm: 80,
};
const record = { id: 'record-1', observations, created_at: '2026-10-10T09:00:00Z' };
const model = {
  version: 'maternal_rf_v0.2', research_only: true,
  evaluation: { accuracy: 0.7111111111, macro_f1: 0.667145, medium_recall: 0.3333333, held_out_rows: 90 },
  source: { name: 'UCI Maternal Health Risk', license: 'CC BY 4.0' },
  limitations: ['No independent external or clinical validation was performed.'],
};
const result = {
  id: 'assessment-1', health_record_id: record.id, observations, model, research_only: true,
  maternal_risk: 'HIGH', class_scores: { HIGH: 0.82, LOW: 0.1, MEDIUM: 0.08 },
  pe_required: true, pe_status: 'UNAVAILABLE',
  pe_reason: 'The PE stage is required, but no verified PE model is available. This assessment is incomplete.',
  created_at: '2026-10-10T09:01:00Z',
  explanation: {
    explained_class: 'HIGH', base_score: 0.4, model_score: 0.82, method: 'Tree SHAP',
    features: [
      { feature: 'glucose_mmol_l', label: 'Blood glucose', value: 7, unit: 'mmol/L', contribution: 0.15 },
      { feature: 'systolic_mmhg', label: 'Systolic blood pressure', value: 120, unit: 'mmHg', contribution: 0.2 },
      { feature: 'diastolic_mmhg', label: 'Diastolic blood pressure', value: 80, unit: 'mmHg', contribution: 0.05 },
      { feature: 'temperature_c', label: 'Body temperature', value: 37, unit: 'degrees Celsius', contribution: -0.02 },
      { feature: 'heart_rate_bpm', label: 'Heart rate', value: 80, unit: 'beats/minute', contribution: 0.04 },
      { feature: 'age_years', label: 'Age', value: 25, unit: 'years', contribution: 0 },
    ],
  },
};
let stored;
let errorStatus;
let modelReady;
let signedIn;

beforeEach(() => {
  stored = []; errorStatus = 0; modelReady = true; signedIn = true;
  vi.stubGlobal('fetch', vi.fn(async (url, options = {}) => {
    let status = 200; let data;
    if (url === '/api/auth/me') {
      status = signedIn ? 200 : 401; data = signedIn ? patient : { detail: 'Please sign in' };
    } else if (url === '/api/capabilities') {
      data = { pregnancy_model_ready: modelReady, pe_model_ready: false, maternal_model: modelReady ? model : null };
    } else if (url === '/api/patients/me/health-records/record-1') data = record;
    else if (url === '/api/patients/me/health-records/record-1/assessments' ||
      url === '/api/patients/me/assessments?offset=0') data = stored;
    else if (url === '/api/patients/me/assessments' && options.method === 'POST') {
      if (errorStatus === 422) {
        status = 422; data = { detail: {
          code: 'MODEL_INPUT_OUTSIDE_RANGE',
          message: 'No assessment was created: measurements are outside this model range. Your health record is still saved.',
          fields: [{ feature: 'glucose_mmol_l', label: 'Blood glucose', value: 5.1, minimum: 6, maximum: 19, unit: 'mmol/L' }],
        } };
      } else if (errorStatus) {
        status = 503; data = { detail: 'The experimental assessment could not be verified. No result was saved.' };
      } else { data = result; stored = [result]; }
    } else {
      status = 404; data = { detail: 'Unexpected endpoint in test: ' + url };
    }
    return { ok: status < 400, status, json: async () => data };
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function start(path = '/patient/assessments/record-1') {
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

describe('experimental assessment workflow', () => {
  it('protects the new assessment screen when signed out', async () => {
    signedIn = false; start();
    expect(await screen.findByText('Welcome back')).toBeInTheDocument();
    expect(screen.queryByText('Saved measurements')).not.toBeInTheDocument();
  });

  it('requests a saved record assessment and displays the API result, SHAP, and unavailable PE stage', async () => {
    start();
    const button = await screen.findByRole('button', { name: 'Run assessment' });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    expect(await screen.findByText('Screening category: HIGH')).toBeInTheDocument();
    expect(screen.queryByText('Held-out accuracy')).not.toBeInTheDocument();
    expect(screen.queryByText('Medium-class recall')).not.toBeInTheDocument();
    expect(screen.queryByText('71.1%')).not.toBeInTheDocument();
    expect(screen.queryByText('33.3%')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Understanding this screening'));
    expect(screen.getByText('The model can miss some medium-risk cases. Review the measurements and result with your clinician even when the category is LOW.')).toBeInTheDocument();
    expect(screen.getByText('Model unavailable')).toBeInTheDocument();
    expect(screen.getByText('82.0%')).toBeInTheDocument();
    expect(screen.getByText(/not probabilities of complications/)).toBeInTheDocument();
    fireEvent.click(screen.getByText('How measurements contributed to this result'));
    expect(screen.getByText('+20.00 pp')).toBeInTheDocument();
    const request = fetch.mock.calls.find(([url, options]) => url === '/api/patients/me/assessments' && options.method === 'POST');
    expect(JSON.parse(request[1].body)).toEqual({ health_record_id: record.id });
    expect(fetch.mock.calls.some(([url]) => url.endsWith('/pe'))).toBe(false);
  });

  it('shows a structured unsupported-input message while keeping the saved measurements visible', async () => {
    errorStatus = 422; start();
    const button = await screen.findByRole('button', { name: 'Run assessment' });
    await waitFor(() => expect(button).toBeEnabled()); fireEvent.click(button);
    expect(await screen.findByRole('alert')).toHaveTextContent('Your health record is still saved');
    expect(screen.getByText('120/80 mmHg')).toBeInTheDocument();
    expect(screen.queryByText(/Screening category:/)).not.toBeInTheDocument();
  });

  it('shows a failed model check without fabricating a result', async () => {
    errorStatus = 503; start();
    const button = await screen.findByRole('button', { name: 'Run assessment' });
    await waitFor(() => expect(button).toBeEnabled()); fireEvent.click(button);
    expect(await screen.findByRole('alert')).toHaveTextContent('No result was saved');
    expect(screen.queryByText(/Screening category:/)).not.toBeInTheDocument();
  });

  it('keeps saved results readable while new assessments are unavailable', async () => {
    modelReady = false; stored = [result]; start();
    expect(await screen.findByText('Screening category: HIGH')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run assessment' })).toBeDisabled();
    expect(screen.getByText(/Previously saved results remain readable/)).toBeInTheDocument();
  });

  it('renders persisted assessment history from the API', async () => {
    stored = [result]; start('/patient/assessments');
    expect(await screen.findByText('Assessment history')).toBeInTheDocument();
    expect(await screen.findByText('Screening category: HIGH')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View linked measurements →' })).toHaveAttribute('href', '/patient/assessments/record-1');
  });
});
