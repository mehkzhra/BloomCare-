import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AdminWorkspace, DoctorWorkspace, PatientWorkspace } from './workspaces.jsx';
import { AdminAccounts } from './admin.jsx';
import { PEScreeningStage } from './pe-screening.jsx';
import { emptyAdminWorkspace, emptyDoctorWorkspace, emptyPatientWorkspace } from './workspace-fixtures.js';
import { setLanguage } from './i18n.js';

const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
const user = { full_name: 'Example Patient' };
const observation = { age_years: 27, gestational_weeks: 24, systolic_mmhg: 120, diastolic_mmhg: 80, glucose_mmol_l: 6, temperature_c: 37, heart_rate_bpm: 78 };
const recorded = { id: 'record-1', observations: observation, created_at: '2026-10-16T08:00:00Z' };
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); setLanguage('en'); });
function mount(node, path = '/') { render(<MemoryRouter initialEntries={[path]}>{node}</MemoryRouter>); }
function replies(data) { vi.stubGlobal('fetch', vi.fn(async () => response(data))); }

it('gives a new patient useful next actions without made-up measurements or predictions', async () => {
  replies(emptyPatientWorkspace()); mount(<PatientWorkspace user={user} />);
  expect(await screen.findByText('Start with one clear record')).toBeInTheDocument();
  expect(screen.getByText('Make this space yours')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Add health observations' })).toHaveAttribute('href', '/patient/health');
  expect(screen.getByText('No approved doctors have been added yet.')).toBeInTheDocument();
  expect(screen.queryByText('120/80')).not.toBeInTheDocument();
  expect(screen.queryByText('LOW')).not.toBeInTheDocument();
});
it('shows server totals rather than treating the visible observations as all records', async () => {
  const data = emptyPatientWorkspace(); data.counts.records = 99; data.records = [recorded]; data.pregnancy = { estimated_weeks: 28, trimester: 3 };
  replies(data); mount(<PatientWorkspace user={user} />);
  expect(await screen.findByText('99')).toBeInTheDocument();
  expect(screen.getByText('120/80', { selector: 'strong' })).toBeInTheDocument();
  expect(screen.getByText('28')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Open pregnancy timeline' })).toHaveAttribute('href', '/patient/timeline');
  expect(screen.getByRole('columnheader', { name: 'Blood glucose' })).toBeInTheDocument();
});
it('surfaces a saved clinician follow-up with a link to the right assessment', async () => {
  const data = emptyPatientWorkspace(); data.urgent_reviews = [{ health_record_id: 'linked-record', clinical_review: { reason: 'Please arrange a follow-up discussion' } }];
  replies(data); mount(<PatientWorkspace user={user} />);
  expect(await screen.findByText('Please arrange a follow-up discussion')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Read review' })).toHaveAttribute('href', '/patient/assessments/linked-record');
});
it('keeps the doctor workspace private while registration approval is pending', async () => {
  const data = emptyDoctorWorkspace(); data.profile.approved = false; data.appointments = [{ patient_name: 'Must stay hidden' }];
  replies(data); mount(<DoctorWorkspace />);
  expect(await screen.findByText('Your registration is being reviewed')).toBeInTheDocument();
  expect(screen.queryByText('Must stay hidden')).not.toBeInTheDocument();
  expect(screen.queryByText('Patients sharing records')).not.toBeInTheDocument();
});
it('opens accepted cases for review and sends pending requests to appointment management', async () => {
  const data = emptyDoctorWorkspace(); data.counts.requests = 1;
  data.appointments = [{ id: 'accepted', record_access_available: true, patient_name: 'Accepted Patient', scheduled_at: '2027-01-10T10:00:00Z', status: 'ACCEPTED', reason: 'Review records' }, { id: 'pending', patient_name: 'New Patient', scheduled_at: '2027-01-11T10:00:00Z', status: 'PENDING', reason: 'First appointment' }];
  replies(data); mount(<DoctorWorkspace />);
  expect(await screen.findByRole('link', { name: 'Open patient review Accepted Patient' })).toHaveAttribute('href', '/doctor/appointments/accepted');
  expect(screen.getByRole('link', { name: 'Manage request New Patient' })).toHaveAttribute('href', '/doctor/appointments');
});
it('shows setup state accurately and links the admin to pending doctor applications', async () => {
  const data = emptyAdminWorkspace(); data.counts.pending_doctors = 1; data.pending_doctors = [{ id: 'd1', full_name: 'Dr Applicant', email: 'applicant@example.invalid', specialty: 'Obstetrics', registration_number: 'EXAMPLE-1' }];
  replies(data); mount(<AdminWorkspace />);
  await screen.findByText('Dr Applicant');
  expect(screen.getByText('Direct connection mode')).toBeInTheDocument();
  expect(screen.getByText('Automatic alerts off')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Check setup & next steps' })).toHaveAttribute('href', '/admin/services');
  expect(screen.getByRole('link', { name: 'Review applications' })).toHaveAttribute('href', '/admin/accounts?role=doctor&approval=pending&active=true');
  expect(screen.queryByText('Offline')).not.toBeInTheDocument();
});
it('loads model evidence only when the administrator opens it', async () => {
  vi.stubGlobal('fetch', vi.fn(async url => {
    if (url === '/api/admin/workspace') return response(emptyAdminWorkspace());
    if (url === '/api/admin/model-evaluation') return response({ active_model: null });
    return response({ candidates: [], pe: { usable_rows: 90, exact_duplicates_removed: 113, test_accuracy: 0.7222 }, limitations: [] });
  }));
  mount(<AdminWorkspace />); await screen.findByText('Applications are up to date');
  expect(fetch.mock.calls.some(([url]) => url.includes('model-evaluation') || url.includes('training-evidence'))).toBe(false);
  fireEvent.click(screen.getByText('Model evaluation & evidence'));
  expect(await screen.findByText('Retraining comparison')).toBeInTheDocument();
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/training-evidence'))).toBe(true);
});
it('reports malformed dashboard data and retries instead of inventing empty-state success', async () => {
  let bad = true; vi.stubGlobal('fetch', vi.fn(async () => response(bad ? [] : emptyPatientWorkspace())));
  mount(<PatientWorkspace user={user} />);
  expect(await screen.findByRole('alert')).toHaveTextContent('could not be read');
  expect(screen.queryByText('Start with one clear record')).not.toBeInTheDocument();
  bad = false; fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByText('Start with one clear record')).toBeInTheDocument();
});
it('loads only the selected account-management tab and preserves approval filters', async () => {
  replies([]); mount(<AdminAccounts />, '/admin/accounts?role=doctor&approval=pending');
  await screen.findByText('No entries.');
  expect(fetch.mock.calls[0][0]).toContain('approval=pending');
  expect(fetch.mock.calls.some(([url]) => url.startsWith('/api/admin/appointments'))).toBe(false);
  fireEvent.click(screen.getByRole('tab', { name: 'Appointments' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.startsWith('/api/admin/appointments'))).toBe(true));
  expect(screen.getByRole('tab', { name: 'Appointments' })).toHaveAttribute('aria-selected', 'true');
});
it('requires confirmation before removing a person’s account access', async () => {
  let active = true;
  vi.stubGlobal('fetch', vi.fn(async (url, options = {}) => {
    if (options.method === 'PATCH') { active = JSON.parse(options.body).active; return response({}); }
    return response([{ id: 'patient1', full_name: 'Example Patient', email: 'example@example.invalid', active, role: 'patient' }]);
  }));
  mount(<AdminAccounts />);
  fireEvent.click(await screen.findByRole('button', { name: 'Disable account' }));
  expect(fetch.mock.calls.filter(([, o]) => o.method === 'PATCH')).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Disable account' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm change' }));
  expect(await screen.findByRole('button', { name: 'Enable account' })).toBeInTheDocument();
  expect(fetch.mock.calls.filter(([, o]) => o.method === 'PATCH')).toHaveLength(1);
});
it('shows exactly which saved PE reading is unsupported and keeps its actual value', async () => {
  const assessment = { id: 'a1', health_record_id: 'record-1', pe_required: true, pe_status: 'OUTSIDE_COVERAGE', observations: { ...observation, systolic_mmhg: 140 }, pe_input_issues: [{ name: 'systolic_mmhg', label: 'Systolic blood pressure', unit: 'mmHg', value: 140, minimum: 90, maximum: 130 }] };
  mount(<PEScreeningStage assessment={assessment} capabilities={{ pe_model_ready: true, pe_input_fields: [{ name: 'systolic_mmhg', from_record: true, minimum: 90, maximum: 130 }] }} viewerRole="patient" onChanged={vi.fn()} />);
  const table = screen.getByRole('table');
  expect(within(table).getByRole('cell', { name: '140 mmHg' })).toBeInTheDocument();
  expect(within(table).getByRole('cell', { name: '90–130 mmHg' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Arrange a doctor review/ })).toHaveAttribute('href', '/patient/appointments?review=pe&record=record-1');
});

it('keeps the main patient actions available in Urdu', async () => {
  setLanguage('ur'); replies(emptyPatientWorkspace()); mount(<PatientWorkspace user={user} />);
  expect(await screen.findByRole('heading', { name: 'آپ کی صحت، ایک نظر میں۔' })).toBeInTheDocument();
  expect(await screen.findByRole('link', { name: 'متوقع تاریخ درج کریں' })).toHaveAttribute('href', '/patient/profile');
});

it('supports keyboard navigation across account-management tabs', async () => {
  replies([]); mount(<AdminAccounts />); await screen.findByText('No entries.');
  const people = screen.getByRole('tab', { name: 'People' }); people.focus();
  fireEvent.keyDown(people, { key: 'ArrowRight' });
  expect(screen.getByRole('tab', { name: 'Appointments' })).toHaveFocus();
  expect(screen.getByRole('tab', { name: 'Appointments' })).toHaveAttribute('aria-selected', 'true');
  fireEvent.keyDown(screen.getByRole('tab', { name: 'Appointments' }), { key: 'End' });
  expect(screen.getByRole('tab', { name: 'Activity' })).toHaveFocus();
});
