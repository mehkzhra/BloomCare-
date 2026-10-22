import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App.jsx';
import { localDateTime } from './appointments.jsx';

const patient = { id: 'patient-1', role: 'patient', full_name: 'Patient', email: 'patient@example.com' };
const doctor = { id: 'doctor-1', role: 'doctor', full_name: 'Doctor One', email: 'doctor@example.com' };
const record = { id: 'record-1', created_at: '2026-10-10T09:00:00Z', observations: {
  age_years: 25, gestational_weeks: 24, systolic_mmhg: 120, diastolic_mmhg: 80,
  glucose_mmol_l: 7, temperature_c: 37, heart_rate_bpm: 78,
} };
const appointment = {
  id: 'appointment-1', patient_id: patient.id, doctor_id: doctor.id,
  patient_name: patient.full_name, doctor_name: doctor.full_name,
  scheduled_at: new Date((Math.floor(Date.now() / 1800000) + 100) * 1800000).toISOString(),
  reason: 'Review selected measurements', health_record_ids: [record.id], status: 'PENDING',
  record_access_available: false, access_until: null,
};
let user, appointments, notes, savedBooking, savedNote, bookingError, decisionError, reviewDenied;

beforeEach(() => {
  user = patient; appointments = []; notes = []; savedBooking = null; savedNote = null;
  bookingError = 0; decisionError = 0; reviewDenied = false;
  vi.stubGlobal('fetch', vi.fn(async (url, options = {}) => {
    let status = 200, data;
    if (url === '/api/auth/me') { status = user ? 200 : 401; data = user || { detail: 'Please sign in' }; }
    else if (url === '/api/doctors') data = [{ id: doctor.id, full_name: doctor.full_name, specialty: 'Obstetrics' }];
    else if (url === '/api/patients/me/health-records?offset=0') data = [record];
    else if (url === '/api/patients/me/appointments' && options.method === 'POST') {
      if (bookingError) { status = bookingError; data = { detail: 'The doctor or patient already has a request at this time' }; }
      else {
        savedBooking = JSON.parse(options.body);
        data = { ...appointment, ...savedBooking }; appointments = [data]; status = 201;
      }
    }
    else if (url.endsWith('/appointments?offset=0')) data = appointments;
    else if (url.endsWith('/appointment-1/decision')) {
      if (decisionError) { status = decisionError; data = { detail: 'This appointment cannot make the requested transition' }; }
      else {
        const action = JSON.parse(options.body).action;
        data = { ...appointments[0], status: { ACCEPT: 'ACCEPTED', REJECT: 'REJECTED', CANCEL: 'CANCELLED', COMPLETE: 'COMPLETED' }[action],
          record_access_available: action === 'ACCEPT', access_until: new Date(Date.now() + 86400000).toISOString() };
        appointments = [data];
      }
    }
    else if (url.endsWith('/appointment-1/cancel')) {
      data = { ...appointments[0], status: 'CANCELLED', record_access_available: false }; appointments = [data];
    }
    else if (url.endsWith('/appointment-1/review')) {
      if (reviewDenied) { status = 403; data = { detail: 'Record access requires an accepted, unexpired care episode' }; }
      else data = { appointment: appointments[0], profile: { user_id: patient.id, phone: '+92 300 1234567',
        date_of_birth: '2001-01-01', due_date: '2027-02-01', preferred_language: 'en' }, records: [record] };
    }
    else if (url.endsWith('/appointment-1/records/record-1/assessments')) {
      if (reviewDenied) { status = 403; data = { detail: 'Record access requires an accepted, unexpired care episode' }; }
      else data = [];
    }
    else if (url.endsWith('/appointment-1/notes')) {
      if (options.method === 'POST') {
        if (reviewDenied) { status = 403; data = { detail: 'Record access requires an accepted, unexpired care episode' }; }
        else {
          savedNote = JSON.parse(options.body);
          data = { ...savedNote, id: 'note-1', author_name: doctor.full_name, created_at: new Date().toISOString() };
          notes = [data]; status = 201;
        }
      } else data = user.role === 'patient' ? notes.filter(note => note.patient_visible) : notes;
    }
    else { status = 404; data = { detail: 'Not found' }; }
    return { ok: status < 400, status, json: async () => data };
  }));
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });
function start(path = '/patient/appointments') {
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}
async function fillBooking(consent = true) {
  await screen.findByLabelText('Doctor');
  fireEvent.change(screen.getByLabelText('Doctor'), { target: { value: doctor.id } });
  fireEvent.change(screen.getByLabelText('Requested start time'), {
    target: { value: localDateTime(new Date(appointment.scheduled_at)) },
  });
  fireEvent.change(screen.getByLabelText('Reason for appointment'), { target: { value: appointment.reason } });
  fireEvent.click(screen.getByRole('checkbox', { name: /BP 120\/80/ }));
  if (consent) fireEvent.click(screen.getByRole('checkbox', { name: /I agree to share my profile/ }));
}
function accepted() {
  user = doctor; appointments = [{ ...appointment, status: 'ACCEPTED', record_access_available: true,
    access_until: new Date(Date.now() + 86400000).toISOString() }];
}

describe('appointment and scoped doctor review flows', () => {
  it('requires sign-in before booking', async () => {
    user = null; start();
    expect(await screen.findByText('Welcome back')).toBeInTheDocument();
    expect(fetch.mock.calls.some(([url]) => url === '/api/doctors')).toBe(false);
  });
  it('books with explicit consent, selected records, and a UTC start time', async () => {
    start(); await fillBooking();
    fireEvent.click(screen.getByRole('button', { name: 'Request appointment' }));
    expect(await screen.findByText(/Appointment requested. Waiting/)).toBeInTheDocument();
    expect(savedBooking).toEqual({ doctor_id: doctor.id, scheduled_at: appointment.scheduled_at,
      reason: appointment.reason, health_record_ids: [record.id], share_profile: true });
    expect(await screen.findByText('PENDING')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Review shared records' })).not.toBeInTheDocument();
  });
  it('does not submit the form without profile-sharing consent', async () => {
    start(); await fillBooking(false);
    fireEvent.click(screen.getByRole('button', { name: 'Request appointment' }));
    expect(savedBooking).toBeNull();
    expect(screen.getByRole('checkbox', { name: /I agree to share my profile/ })).toBeInvalid();
  });
  it('keeps the entered request and shows a real booking conflict', async () => {
    bookingError = 409; start(); await fillBooking();
    fireEvent.click(screen.getByRole('button', { name: 'Request appointment' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('already has a request');
    expect(screen.getByLabelText('Reason for appointment')).toHaveValue(appointment.reason);
    expect(screen.queryByText('PENDING')).not.toBeInTheDocument();
  });
  it('lets the selected doctor accept and then exposes the review link', async () => {
    user = doctor; appointments = [{ ...appointment }]; start('/doctor/appointments');
    fireEvent.click(await screen.findByRole('button', { name: 'Accept request' }));
    expect(await screen.findByText('ACCEPTED')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Review shared records' })).toHaveAttribute('href', '/doctor/appointments/appointment-1');
    const call = fetch.mock.calls.find(([url, options]) => url.endsWith('/decision') && options.method === 'POST');
    expect(JSON.parse(call[1].body)).toEqual({ action: 'ACCEPT' });
  });
  it('retains a failed doctor decision message after refreshing the appointment list', async () => {
    user = doctor; appointments = [{ ...appointment }]; decisionError = 409; start('/doctor/appointments');
    fireEvent.click(await screen.findByRole('button', { name: 'Accept request' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('cannot make the requested transition');
    expect(await screen.findByText('PENDING')).toBeInTheDocument();
  });
  it('lets a patient cancel an accepted appointment', async () => {
    appointments = [{ ...appointment, status: 'ACCEPTED', record_access_available: true, access_until: appointment.scheduled_at }];
    start();
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel appointment' }));
    expect(await screen.findByText('CANCELLED')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancel appointment' })).not.toBeInTheDocument();
  });
  it('shows shared measurements and fetches saved assessments without generating one', async () => {
    accepted(); start('/doctor/appointments/appointment-1');
    expect(await screen.findByText('120/80 mmHg')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'View saved assessments' }));
    expect(await screen.findByText('No assessment was saved for this record.')).toBeInTheDocument();
    expect(fetch.mock.calls.some(([url, options]) => url === '/api/patients/me/assessments' && options.method === 'POST')).toBe(false);
  });
  it('saves clinician authorship on the server and an explicit private-note choice', async () => {
    accepted(); start('/doctor/appointments/appointment-1');
    const input = await screen.findByLabelText('Note');
    fireEvent.change(input, { target: { value: 'Private review entry' } });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Share this note with the patient' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save clinician note' }));
    expect(await screen.findByText('Clinician note saved.')).toBeInTheDocument();
    expect(savedNote).toEqual({ body: 'Private review entry', patient_visible: false });
    expect(await screen.findByText('Private review entry')).toBeInTheDocument();
    expect(screen.getByText(/Private clinician entry/)).toBeInTheDocument();
  });
  it('does not expose review content or a note form when the episode is unavailable', async () => {
    accepted(); reviewDenied = true; start('/doctor/appointments/appointment-1');
    expect(await screen.findByRole('alert')).toHaveTextContent('accepted, unexpired care episode');
    expect(screen.queryByText('120/80 mmHg')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Note')).not.toBeInTheDocument();
  });
  it('clears review content when a note request reports that access was revoked', async () => {
    accepted(); start('/doctor/appointments/appointment-1');
    fireEvent.change(await screen.findByLabelText('Note'), { target: { value: 'Unsaved review' } });
    reviewDenied = true;
    fireEvent.click(screen.getByRole('button', { name: 'Save clinician note' }));
    await waitFor(() => expect(screen.queryByText('120/80 mmHg')).not.toBeInTheDocument());
    expect(screen.queryByLabelText('Note')).not.toBeInTheDocument();
    expect(screen.queryByText('Clinician note saved.')).not.toBeInTheDocument();
  });
  it('lets the patient read the API-filtered visible notes after an appointment closes', async () => {
    notes = [
      { id: 'public', author_name: doctor.full_name, body: 'Patient-visible follow-up', patient_visible: true, created_at: appointment.scheduled_at },
      { id: 'private', author_name: doctor.full_name, body: 'Private clinician entry', patient_visible: false, created_at: appointment.scheduled_at },
    ];
    start('/patient/appointments/appointment-1');
    expect(await screen.findByText('Patient-visible follow-up')).toBeInTheDocument();
    expect(screen.queryByText('Private clinician entry')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Note')).not.toBeInTheDocument();
  });
  it('clears the open review when its access window expires', async () => {
    vi.useFakeTimers(); accepted();
    appointments[0].access_until = new Date(Date.now() + 1000).toISOString();
    await act(async () => start('/doctor/appointments/appointment-1'));
    expect(screen.getByLabelText('Note')).toBeInTheDocument();
    reviewDenied = true;
    await act(async () => vi.advanceTimersByTimeAsync(1001));
    expect(screen.queryByText('120/80 mmHg')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Note')).not.toBeInTheDocument();
  });
  it('avoids a refresh loop when the device clock reaches expiry before the server', async () => {
    vi.useFakeTimers(); accepted();
    appointments[0].access_until = new Date(Date.now() + 1000).toISOString();
    await act(async () => start('/doctor/appointments/appointment-1'));
    await act(async () => vi.advanceTimersByTimeAsync(5000));
    const reads = fetch.mock.calls.filter(([url]) => url.endsWith('/appointment-1/review'));
    expect(reads).toHaveLength(2);
    expect(screen.getByLabelText('Note')).toBeInTheDocument();
  });
  it('checks expiry after a long grant exceeds the browser timeout limit', async () => {
    vi.useFakeTimers(); accepted();
    appointments[0].access_until = new Date(Date.now() + 30 * 86400000).toISOString();
    await act(async () => start('/doctor/appointments/appointment-1'));
    await act(async () => vi.advanceTimersByTimeAsync(2147483647));
    expect(screen.getByLabelText('Note')).toBeInTheDocument();
    reviewDenied = true;
    await act(async () => vi.advanceTimersByTimeAsync(30 * 86400000 - 2147483647 + 1));
    expect(screen.queryByText('120/80 mmHg')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Note')).not.toBeInTheDocument();
  });
});
