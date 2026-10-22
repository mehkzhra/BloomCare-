import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { HealthPage } from './health-form.jsx';
import { CarePlanPanel, ClinicalReviewPanel, FollowUpInbox, RescheduleForm, WhatsAppAssessmentAlert } from './clinical-ui.jsx';
import { setLanguage } from './i18n.js';

const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
const assessment = { id: 'assessment-1', clinical_review: { version: 3, status: 'PENDING' } };
const capabilities = { pregnancy_model_ready: true, assessment_ranges: { glucose_mmol_l: [6, 19], temperature_c: [35, 41] } };
let requests;
beforeEach(() => { setLanguage('en'); requests = []; });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); setLanguage('en'); });
function mock(handler = () => []) {
  vi.stubGlobal('fetch', vi.fn(async (url, options = {}) => {
    const call = { url, method: options.method, body: options.body ? JSON.parse(options.body) : undefined };
    requests.push(call);
    return handler(call);
  }));
}
function fillHealth() {
  for (const [label, value] of [['Age (years)', '27'], ['Pregnancy duration (weeks)', '24'], ['Systolic blood pressure (mmHg)', '120'], ['Diastolic blood pressure (mmHg)', '80'], ['Blood glucose (mg/dL)', '108'], ['Body temperature (°F)', '98.6'], ['Heart rate (beats/minute)', '78']]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
}

it('converts entered glucose and temperature in both directions without changing measured meaning', async () => {
  mock(() => response(capabilities));
  render(<MemoryRouter><HealthPage /></MemoryRouter>);
  await screen.findByPlaceholderText('108–342');
  fillHealth();
  fireEvent.change(screen.getByLabelText('Glucose unit'), { target: { value: 'mmol/L' } });
  fireEvent.change(screen.getByLabelText('Temperature unit'), { target: { value: '°C' } });
  expect(screen.getByLabelText('Blood glucose (mmol/L)')).toHaveValue(6);
  expect(screen.getByLabelText('Body temperature (°C)')).toHaveValue(37);
  fireEvent.change(screen.getByLabelText('Glucose unit'), { target: { value: 'mg/dL' } });
  fireEvent.change(screen.getByLabelText('Temperature unit'), { target: { value: '°F' } });
  expect(screen.getByLabelText('Blood glucose (mg/dL)')).toHaveValue(108);
  expect(screen.getByLabelText('Body temperature (°F)')).toHaveValue(98.6);
});

it('reuses a record request ID after an uncertain save and excludes unknown clinical answers', async () => {
  mock(call => call.method === 'POST' ? response({ detail: 'Try again' }, 503) : response(capabilities));
  render(<MemoryRouter><HealthPage /></MemoryRouter>);
  await screen.findByPlaceholderText('108–342'); fillHealth();
  fireEvent.click(screen.getByRole('button', { name: 'Save health record' }));
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Save health record' }));
  await waitFor(() => expect(requests.filter(r => r.method === 'POST')).toHaveLength(2));
  const [first, retry] = requests.filter(r => r.method === 'POST');
  expect(retry.body.request_id).toBe(first.body.request_id);
  expect(first.body.glucose_mmol_l).toBe(6);
  expect(first.body.temperature_c).toBe(37);
  expect(first.body).not.toHaveProperty('clinical_indicators');
});

it('explains 12-week PE coverage before submit while preserving the entered duration', async () => {
  mock(call => call.method === 'POST' ? response({ detail: 'Try again' }, 503) : response({ ...capabilities, pe_input_fields: [{ name: 'gestational_weeks', minimum: 14, maximum: 40 }] }));
  render(<MemoryRouter><HealthPage /></MemoryRouter>);
  await screen.findByPlaceholderText('108–342'); fillHealth();
  fireEvent.change(screen.getByLabelText('Pregnancy duration (weeks)'), { target: { value: '12' } });
  expect(screen.getByRole('status')).toHaveTextContent('14–40');
  expect(screen.getByRole('status')).toHaveTextContent('This is not a LOW result');
  expect(screen.getByRole('status')).toHaveTextContent('pregnancy weeks are not an input');
  expect(screen.getByRole('button', { name: 'Run complete assessment' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Save health record' }));
  await screen.findByRole('alert');
  expect(requests.find(r => r.method === 'POST').body.gestational_weeks).toBe(12);
  expect(screen.getByLabelText('Pregnancy duration (weeks)')).toHaveValue(12);
  fireEvent.change(screen.getByLabelText('Pregnancy duration (weeks)'), { target: { value: '14' } });
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

it('requests a care plan only after consent and returns the saved assessment', async () => {
  const changed = vi.fn();
  mock(() => response({ ...assessment, care_plan: { content: 'Saved care guide' } }));
  render(<CarePlanPanel assessment={assessment} viewerRole="patient" onChanged={changed} />);
  fireEvent.click(screen.getByText('Personalized care plan'));
  const checkbox = screen.getByRole('checkbox');
  expect(checkbox.closest('form').checkValidity()).toBe(false);
  expect(requests).toHaveLength(0);
  fireEvent.click(checkbox);
  fireEvent.click(screen.getByRole('button', { name: 'Generate and save care plan' }));
  await waitFor(() => expect(changed).toHaveBeenCalled());
  expect(requests[0].body).toEqual({ consent: true, language: 'en' });
});

it('loads review history when opened and submits the displayed review version', async () => {
  const changed = vi.fn();
  mock(call => response(call.method === 'PUT' ? assessment : []));
  render(<ClinicalReviewPanel assessment={assessment} appointmentId="appointment-1" viewerRole="doctor" onChanged={changed} />);
  expect(requests).toHaveLength(0);
  fireEvent.click(screen.getByText('Review history'));
  await screen.findByText('No review changes yet.');
  fireEvent.change(screen.getByLabelText('Review status'), { target: { value: 'URGENT_FOLLOW_UP' } });
  fireEvent.change(screen.getByLabelText('Review reason / follow-up instructions'), { target: { value: 'Arrange a clinician discussion' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save review status' }));
  await waitFor(() => expect(changed).toHaveBeenCalledWith(assessment));
  expect(requests.find(r => r.method === 'PUT').body).toEqual({ status: 'URGENT_FOLLOW_UP', reason: 'Arrange a clinician discussion', follow_up_at: null, expected_version: 3 });
});

it('requires fresh sharing consent before accepting a linked follow-up proposal', async () => {
  const changed = vi.fn();
  const proposal = { id: 'proposal-1', health_record_id: 'record-1', doctor_name: 'Dr Example', scheduled_at: '2027-01-10T10:00:00Z', reason: 'Follow-up discussion' };
  mock(call => response(call.method === 'POST' ? {} : [proposal]));
  render(<FollowUpInbox onChanged={changed} />);
  expect(requests).toHaveLength(0);
  fireEvent.click(screen.getByText('Doctor follow-up proposals'));
  await screen.findByText('Dr Example');
  expect(screen.getByRole('checkbox').closest('form').checkValidity()).toBe(false);
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(screen.getByRole('button', { name: 'Request this follow-up' }));
  await waitFor(() => expect(changed).toHaveBeenCalled());
  expect(requests.find(r => r.method === 'POST').body).toEqual({ share_profile: true, health_record_ids: ['record-1'] });
});

it('includes the original appointment timestamp when requesting a revised time', async () => {
  const changed = vi.fn(), updated = '2026-10-16T10:00:00Z';
  mock(() => response({}));
  render(<RescheduleForm appointment={{ id: 'appointment-1', reason: 'Routine discussion', updated_at: updated }} onChanged={changed} />);
  fireEvent.click(screen.getByText('Reschedule appointment'));
  fireEvent.change(screen.getByLabelText('New start time'), { target: { value: '2027-01-10T10:00' } });
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(screen.getByRole('button', { name: 'Save new appointment time' }));
  await waitFor(() => expect(changed).toHaveBeenCalled());
  expect(requests[0].body.expected_updated_at).toBe(updated);
  expect(requests[0].body.scheduled_at).toBe(new Date('2027-01-10T10:00').toISOString());
});

it('shows a queued alert accurately and requires a fresh draft and consent for another alert', async () => {
  const alerts = [];
  mock(call => {
    if (call.url.endsWith('/whatsapp/status')) return response({ configured: true });
    if (call.method === 'POST') alerts.push({ id: String(alerts.length), recipient: '••••0101', status: 'QUEUED' });
    return response([...alerts]);
  });
  render(<WhatsAppAssessmentAlert assessmentId="assessment-1" />);
  fireEvent.click(screen.getByText('WhatsApp care alert'));
  await screen.findByLabelText('Approved care contact');
  const send = () => {
    fireEvent.change(screen.getByLabelText('Approved care contact'), { target: { value: '+15555550101' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Send care alert' }));
  };
  send();
  await screen.findByText(/QUEUED/);
  expect(screen.queryByRole('button', { name: 'Send care alert' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Prepare another alert' }));
  expect(screen.getByRole('checkbox')).not.toBeChecked();
  send();
  await waitFor(() => expect(requests.filter(r => r.method === 'POST')).toHaveLength(2));
  const [first, second] = requests.filter(r => r.method === 'POST');
  expect(first.body.request_id).not.toBe(second.body.request_id);
});
