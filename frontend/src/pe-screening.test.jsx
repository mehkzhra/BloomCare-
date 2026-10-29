import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AssessmentCard } from './assessments.jsx';
import manifest from '../../ml/artifacts/legacy_pe_v0.7.1/manifest.json';

const observations = { age_years: 25, gestational_weeks: 24, systolic_mmhg: 120,
  diastolic_mmhg: 80, glucose_mmol_l: 12, temperature_c: 37, heart_rate_bpm: 80 };
const assessment = { id: 'assessment-1', health_record_id: 'record-1', observations,
  maternal_risk: 'HIGH', pe_required: true, pe_status: 'AWAITING_INPUTS',
  created_at: '2026-10-15T09:00:00Z', model: { version: 'maternal_rf_v0.2', limitations: [],
    source: { name: 'UCI', license: 'CC BY 4.0' }, evaluation: { accuracy: .71, held_out_rows: 90 } },
  class_scores: { LOW: .1, MEDIUM: .2, HIGH: .7 },
  explanation: { features: [], base_score: .4, model_score: .7 },
};
const peModel = { version: manifest.version, input_fields: manifest.features,
  source: { repository: manifest.source.repository, commit: manifest.source.commit },
  limitations: manifest.limitations };
const capabilities = { pe_model_ready: true, pe_input_fields: manifest.features, pe_model: peModel };
const additional = { gravida: 2, parity: 1, bmi: 24.5, diabetes: false,
  history_of_hypertension: false, hb: 10.5, fetal_weight_kg: 1.2,
  protein_uria: false, amniotic_fluid_level_cm: 12 };
const saved = { id: 'pe-1', risk: 'MEDIUM', class_scores: { LOW: .1, MEDIUM: .7, HIGH: .2 },
  observations: { age_years: 25, gestational_weeks: 24, systolic_mmhg: 120, diastolic_mmhg: 80, ...additional },
  model: peModel, created_at: '2026-10-15T09:01:00Z' };

beforeEach(() => vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200,
  json: async () => ({ ...assessment, pe_status: 'COMPLETED', pe_screening: saved }) }))));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function start(row = assessment, caps = capabilities, viewerRole = 'patient') {
  render(<MemoryRouter><AssessmentCard assessment={row} peCapabilities={caps} viewerRole={viewerRole} /></MemoryRouter>);
}
function fill() {
  for (const field of manifest.features.filter(item => !item.from_record)) {
    fireEvent.change(screen.getByRole(field.kind === 'boolean' ? 'combobox' : 'spinbutton', { name: name => name.startsWith(field.label) }),
      { target: { value: field.kind === 'boolean' ? (additional[field.name] ? 'yes' : 'no') : String(additional[field.name]) } });
  }
}

it.each(['MEDIUM', 'HIGH'])('opens the additional PE form for %s without inventing values', risk => {
  start({ ...assessment, maternal_risk: risk });
  expect(screen.getByRole('form', { name: 'Additional PE measurements' })).toBeInTheDocument();
  const numeric = screen.getAllByRole('spinbutton');
  expect(numeric).toHaveLength(6);
  for (const input of numeric) { expect(input.value).toBe(''); expect(input.placeholder).toMatch(/–/); }
  for (const select of screen.getAllByRole('combobox')) expect(select.value).toBe('');
  expect(screen.queryByLabelText(/Doppler/)).not.toBeInTheDocument();
  expect(screen.queryByRole('spinbutton', { name: /Systolic/ })).not.toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});

it('posts only the nine extra fields and renders the returned saved PE category', async () => {
  start(); fill();
  fireEvent.click(screen.getByRole('button', { name: 'Complete PE screening' }));
  expect(await screen.findByText('PE screening category: MEDIUM')).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
  const [url, request] = fetch.mock.calls[0];
  expect(url).toBe('/api/patients/me/assessments/assessment-1/pe');
  expect(JSON.parse(request.body)).toEqual(additional);
  expect(screen.queryByRole('form', { name: 'Additional PE measurements' })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Arrange a doctor review' })).toHaveAttribute('href', '/patient/appointments?review=pe&record=record-1');
});

it('requires an explicit answer for all boolean measurements', () => {
  start();
  fireEvent.submit(screen.getByRole('form', { name: 'Additional PE measurements' }));
  expect(fetch).not.toHaveBeenCalled();
  for (const select of screen.getAllByRole('combobox')) expect(select).toBeRequired();
});

it('keeps actual out-of-range saved readings and directs the patient to review', () => {
  start({ ...assessment, observations: { ...observations, systolic_mmhg: 145 } });
  expect(screen.getByText(/These saved readings need a doctor review/)).toHaveTextContent('No PE category can be produced');
  expect(screen.getByRole('alert', { name: /Blood pressure care guidance/ })).toHaveTextContent('145');
  expect(screen.queryByRole('form')).not.toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});

it('does not open PE for LOW or allow doctors to enter patient PE values', () => {
  const view = render(<MemoryRouter><AssessmentCard assessment={{ ...assessment, maternal_risk: 'LOW', pe_required: false }} peCapabilities={capabilities} /></MemoryRouter>);
  expect(screen.queryByRole('form')).not.toBeInTheDocument();
  view.unmount(); start(assessment, capabilities, 'doctor');
  expect(screen.queryByRole('form')).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Arrange a doctor review' })).not.toBeInTheDocument();
});

it.each(['patient', 'doctor'])('explains the saved 12-week limitation to a %s without exposing a PE submission form', viewerRole => {
  start({ ...assessment, pe_status: 'OUTSIDE_COVERAGE', observations: { ...observations, gestational_weeks: 12 }, pe_input_issues: [{ name: 'gestational_weeks', label: 'Pregnancy duration', value: 12, minimum: 14, maximum: 40, unit: 'weeks' }] }, capabilities, viewerRole);
  expect(screen.getByText(/This does not mean LOW risk/)).toBeInTheDocument();
  expect(screen.getByText(/unavailable for your recorded week of pregnancy/)).toBeInTheDocument();
  expect(screen.getByRole('cell', { name: '12 weeks' })).toBeInTheDocument();
  expect(screen.getByRole('cell', { name: '14–40 weeks' })).toBeInTheDocument();
  expect(screen.queryByRole('form', { name: 'Additional PE measurements' })).not.toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});

it('reads stored PE labels and values even when the model is unavailable', () => {
  start({ ...assessment, pe_screening: saved }, { pe_model_ready: false }, 'doctor');
  expect(screen.getByText('PE screening category: MEDIUM')).toBeInTheDocument();
  expect(screen.getByText('Haemoglobin (HB)')).toBeInTheDocument();
  expect(screen.getByText('10.5')).toBeInTheDocument();
});

it('shows a failed PE request without a made-up category and permits retry', async () => {
  fetch.mockResolvedValueOnce({ ok: false, status: 503,
    json: async () => ({ detail: { code: 'PE_MODEL_UNAVAILABLE', message: 'PE model unavailable. No PE result was saved.' } }) });
  start(); fill(); fireEvent.click(screen.getByRole('button', { name: 'Complete PE screening' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('No PE result was saved');
  expect(screen.queryByText(/PE screening category:/)).not.toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole('button', { name: 'Complete PE screening' })).toBeEnabled());
});

it('keeps urgent BP guidance above a LOW category without routine appointment links', () => {
  start({ ...assessment, maternal_risk: 'LOW', observations: { ...observations, systolic_mmhg: 170, diastolic_mmhg: 110 } });
  expect(screen.getByRole('alert', { name: /Blood pressure care guidance/ })).toHaveTextContent('Seek urgent maternity care now');
  expect(screen.queryByRole('link', { name: 'Arrange a doctor review' })).not.toBeInTheDocument();
});
