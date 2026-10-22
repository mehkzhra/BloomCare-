import { t } from "./i18n.js";
import { useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api } from './api.js';
import { AssessmentCard } from './assessments.jsx';
import { ResourceStatus, useResource } from './pages.jsx';
import { AmendNoteForm, FollowUpInbox, RescheduleForm } from './clinical-ui.jsx';
function dateTime(value) {
  return new Date(value).toLocaleString(undefined, {
    timeZoneName: 'short'
  });
}
export function localDateTime(date) {
  const pad = value => String(value).padStart(2, '0');
  return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate()) + 'T' + pad(date.getHours()) + ':' + pad(date.getMinutes());
}
function BookingForm({
  onBooked
}) {
  const doctors = useResource('/doctors');
  const records = useResource('/patients/me/health-records?offset=0');
  const [search] = useSearchParams();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [clock, setClock] = useState(() => Date.now());
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const nextSlot = new Date((Math.floor(clock / 1800000) + 1) * 1800000);
  const lastSlot = new Date(Math.floor((clock + 90 * 86400000) / 1800000) * 1800000);
  async function submit(event) {
    event.preventDefault();
    setError('');
    setBusy(true);
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      const local = data.get('scheduled_at');
      const date = new Date(local);
      if (!Number.isFinite(date.getTime()) || localDateTime(date) !== local) {
        throw new Error('Choose a valid time in your device timezone.');
      }
      const selected = data.getAll('health_record_id');
      if (selected.length > 20) throw new Error('Select up to 20 saved records.');
      await api('/patients/me/appointments', {
        method: 'POST',
        body: {
          doctor_id: data.get('doctor_id'),
          scheduled_at: date.toISOString(),
          reason: data.get('reason'),
          share_profile: data.get('share_profile') === 'on',
          health_record_ids: selected
        }
      });
      form.reset();
      setClock(Date.now());
      onBooked();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return <section className="card stack"><div><h2>{t("Request an appointment")}</h2>
    <p className="muted">{t("Requests need the selected doctor's acceptance. Each appointment lasts 30 minutes.")}</p></div>
    <ResourceStatus resource={doctors} /><ResourceStatus resource={records} />
    {doctors.data?.length === 0 && <p>{t("No approved doctors have been added yet.")}</p>}
    {doctors.data?.length > 0 && records.data && <form className="stack" onSubmit={submit}>
      <div className="grid-form">
        <label>{t("Doctor")}<select name="doctor_id" required defaultValue={search.get('doctor') || ''}>
          <option value="" disabled>{t("Select an approved doctor")}</option>
          {doctors.data.map(doctor => <option key={doctor.id} value={doctor.id}>
            {doctor.full_name} · {doctor.specialty}</option>)}</select></label>
        <label>{t("Requested start time")}<input type="datetime-local" name="scheduled_at" required step="1800" min={localDateTime(nextSlot)} max={localDateTime(lastSlot)} onFocus={() => setClock(Date.now())} /></label>
      </div>
      <p className="muted text-sm">{t("Times use your device timezone (")}{zone}{t("). Choose a half-hour start within 90 days.")}</p>
      <label>{t("Reason for appointment")}<textarea name="reason" required minLength={3} maxLength={1000} rows={3} defaultValue={search.get('review') === 'pe' ? 'Pre-eclampsia review following my health assessment.' : ''} /></label>
      <fieldset className="record-options"><legend>{t("Choose saved records to share (up to 20)")}</legend>
        {records.data.length === 0 && <p className="muted">{t("No saved records. You can request a profile-only appointment.")}</p>}
        {records.data.map(record => <label className="check-label" key={record.id}>
          <input type="checkbox" name="health_record_id" value={record.id} defaultChecked={search.get('review') === 'pe' && search.get('record') === record.id} />
          <span>{dateTime(record.created_at)}{t("· BP")}{record.observations.systolic_mmhg}/{record.observations.diastolic_mmhg}
            {' '}{t("mmHg · glucose")}{record.observations.glucose_mmol_l}{t("mmol/L")}</span></label>)}
        {records.data.length === 50 && <p className="muted text-sm">{t("Showing your latest 50 records.")}</p>}
      </fieldset>
      <label className="check-label"><input type="checkbox" name="share_profile" required />
        <span>{t("I agree to share my profile and selected records with this doctor after acceptance. Access ends when the appointment closes or 24 hours after its requested start time.")}</span></label>
      <p className="muted text-sm">{t("Later records are not shared automatically. Cancel this request to withdraw access.")}</p>
      {error && <p className="error" role="alert">{error}</p>}
      <div><button disabled={busy}>{busy ? t("Requesting…") : t("Request appointment")}</button></div>
    </form>}
  </section>;
}
function AppointmentItem({
  appointment,
  role,
  onChanged,
  onError
}) {
  const [busy, setBusy] = useState(false);
  const pending = appointment.status === 'PENDING';
  const accepted = appointment.status === 'ACCEPTED';
  async function action(value) {
    setBusy(true);
    try {
      const path = role === 'patient' ? '/patients/me/appointments/' + appointment.id + '/cancel' : '/doctors/me/appointments/' + appointment.id + '/decision';
      await api(path, {
        method: 'POST',
        body: role === 'doctor' ? {
          action: value
        } : undefined
      });
      onChanged();
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return <article className="card stack"><div className="assessment-heading">
    <div><h2>{role === 'patient' ? appointment.doctor_name : appointment.patient_name}</h2>
      <p className="muted m-0">{dateTime(appointment.scheduled_at)}{t("· 30 minutes")}</p></div>
    <span className="appointment-status">{appointment.status}</span></div>
    <p className="note-body m-0">{appointment.reason}</p>
    <p className="muted text-sm m-0">{appointment.health_record_ids.length}{t("selected records shared after acceptance.")}</p>
    {accepted && <p className="muted text-sm m-0">{appointment.record_access_available ? 'Review access ends ' + dateTime(appointment.access_until) + ', or when this appointment closes.' : t("Record access is no longer available for this episode.")}</p>}
    <div className="action-row">
      <Link to={`/${role}/appointments/${appointment.id}/messages`}>{t("Messages and reports")}</Link>
      {appointment.record_access_available && <Link to={`/${role}/appointments/${appointment.id}/consultation`}>{t("Video consultation")}</Link>}
      {role === 'doctor' && pending && <>
        <button disabled={busy} onClick={() => action('ACCEPT')}>{t("Accept request")}</button>
        <button className="secondary" disabled={busy} onClick={() => action('REJECT')}>{t("Reject request")}</button></>}
      {role === 'doctor' && accepted && <>
        {appointment.record_access_available && <Link className="button" to={'/doctor/appointments/' + appointment.id}>{t("Review shared records")}</Link>}
        <button className="secondary" disabled={busy} onClick={() => action('COMPLETE')}>{t("Complete appointment")}</button></>}
      {(pending || accepted) && <button className="secondary" disabled={busy} onClick={() => action('CANCEL')}>{t("Cancel appointment")}</button>}
      <Link to={'/' + role + '/appointments/' + appointment.id}>
        {role === 'patient' ? t("View clinician notes") : t("View appointment notes")}</Link>
    </div>{role === 'patient' && (pending || accepted) && <RescheduleForm appointment={appointment} onChanged={onChanged} />}</article>;
}
export function AppointmentsPage({
  role
}) {
  const [offset, setOffset] = useState(0);
  const resource = useResource('/' + (role === 'patient' ? 'patients' : 'doctors') + '/me/appointments?offset=' + offset);
  const [message, setMessage] = useState('');
  const [actionError, setActionError] = useState('');
  function booked() {
    setOffset(0);
    resource.retry();
    setMessage('Appointment requested. Waiting for the doctor to accept.');
  }
  function changed() {
    setMessage('');
    setActionError('');
    resource.retry();
  }
  function failed(message) {
    setActionError(message);
    resource.retry();
  }
  return <div className="stack"><div><span className="eyebrow">{t("Your care, connected")}</span><h1>{t("Appointments")}</h1>
    <p className="muted">{role === 'patient' ? t("Choose your doctor and decide which records to share.") : t("Respond to requests and review records shared for accepted appointments.")}</p></div>
    {role === 'patient' && <BookingForm onBooked={booked} />}
    {role === 'patient' && <FollowUpInbox onChanged={changed} />}
    {message && <p className="success" role="status">{message}</p>}
    {actionError && <p className="error" role="alert">{actionError}</p>}
    <section className="stack"><h2>{t("Appointment history")}</h2><ResourceStatus resource={resource} />
      {resource.data?.length === 0 && <p className="muted">{t("No appointments on this page.")}</p>}
      {resource.data?.map(appointment => <AppointmentItem key={appointment.id} appointment={appointment} role={role} onChanged={changed} onError={failed} />)}
      <div className="action-row"><button className="secondary" disabled={offset === 0 || resource.loading} onClick={() => setOffset(n => Math.max(0, n - 50))}>{t("Newer appointments")}</button>
        <button className="secondary" disabled={resource.loading || resource.data?.length !== 50} onClick={() => setOffset(n => n + 50)}>{t("Older appointments")}</button></div>
    </section></div>;
}
function Notes({
  resource,
  appointmentId
}) {
  return <section className="card stack"><h2>{t("Clinician notes")}</h2><ResourceStatus resource={resource} />
    {resource.data?.length === 0 && <p className="muted">{t("No clinician notes are available.")}</p>}
    {resource.data?.map(note => <article className="record" key={note.id}>
      <strong>{note.author_name}</strong><p className="muted text-sm">
        {dateTime(note.created_at)} · {note.patient_visible ? t("Visible to patient") : t("Private clinician entry")}</p>
      {note.assessment_id && <p className="muted text-sm">{t('Linked to assessment')}: {note.assessment_id.slice(0, 8)}</p>}
      {note.assessment_removed && <p className="subtle-tag">{t('Linked assessment removed by patient — note retained')}</p>}
      {note.supersedes_id && <p className="subtle-tag">{t('Amendment — original retained')}</p>}
      <p className="note-body">{note.body}</p>
      {appointmentId && !resource.data.some(item => item.supersedes_id === note.id) && <AmendNoteForm note={note} appointmentId={appointmentId} onSaved={resource.retry} />}
    </article>)}</section>;
}
export function PatientAppointmentNotes() {
  const {
    appointmentId
  } = useParams();
  const resource = useResource('/patients/me/appointments/' + appointmentId + '/notes');
  return <div className="stack"><div><h1>{t("Appointment notes")}</h1><Link to="/patient/appointments">{t("← Appointments")}</Link></div>
    <Notes resource={resource} /></div>;
}
function SharedRecord({
  record,
  appointmentId,
  onAccessLost
}) {
  const [state, setState] = useState({
    data: null,
    error: '',
    busy: false
  });
  const request = useRef(null);
  useEffect(() => () => request.current?.abort(), []);
  async function load() {
    const controller = new AbortController();
    request.current = controller;
    setState({
      data: null,
      error: '',
      busy: true
    });
    try {
      const data = await api('/doctors/me/appointments/' + appointmentId + '/records/' + record.id + '/assessments', {
        signal: controller.signal
      });
      if (!controller.signal.aborted) setState({
        data,
        error: '',
        busy: false
      });
    } catch (err) {
      if (!controller.signal.aborted) {
        setState({
          data: null,
          error: err.message,
          busy: false
        });
        if (err.status === 403) onAccessLost();
      }
    }
  }
  const o = record.observations;
  return <article className="record stack"><h3>{t("Record saved")}{dateTime(record.created_at)}</h3>
    <dl className="grid-form">
      <div><dt>{t("Age / pregnancy duration")}</dt><dd>{o.age_years}{t("years /")}{o.gestational_weeks}{t("weeks")}</dd></div>
      <div><dt>{t("Blood pressure")}</dt><dd>{o.systolic_mmhg}/{o.diastolic_mmhg}{t("mmHg")}</dd></div>
      <div><dt>{t("Blood glucose")}</dt><dd>{o.glucose_mmol_l}{t("mmol/L")}</dd></div>
      <div><dt>{t("Temperature / heart rate")}</dt><dd>{o.temperature_c}{t("°C /")}{o.heart_rate_bpm}{t("bpm")}</dd></div></dl>
    <div><button className="secondary" disabled={state.busy} onClick={load}>
      {state.busy ? t("Loading…") : t("View saved assessments")}</button></div>
    {state.error && <p className="error" role="alert">{state.error}</p>}
    {state.data?.length === 0 && <p className="muted">{t("No assessment was saved for this record.")}</p>}
    {state.data?.map(assessment => <AssessmentCard key={assessment.id} assessment={assessment} viewerRole="doctor" appointmentId={appointmentId} />)}
  </article>;
}
export function DoctorAppointmentReview() {
  const {
    appointmentId
  } = useParams();
  return <DoctorReview key={appointmentId} appointmentId={appointmentId} />;
}
function DoctorReview({
  appointmentId
}) {
  const review = useResource('/doctors/me/appointments/' + appointmentId + '/review');
  const notes = useResource('/doctors/me/appointments/' + appointmentId + '/notes');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const checkedExpiry = useRef(null);
  const expires = review.data?.appointment.access_until;
  const refreshReview = review.retry;
  useEffect(() => {
    if (!expires || checkedExpiry.current === expires) return;
    const timer = setTimeout(() => {
      if (new Date(expires).getTime() <= Date.now()) checkedExpiry.current = expires;
      refreshReview();
    }, Math.min(2147483647, Math.max(0, new Date(expires).getTime() - Date.now())));
    return () => clearTimeout(timer);
  }, [expires, refreshReview]);
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setSaved(false);
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await api('/doctors/me/appointments/' + appointmentId + '/notes', {
        method: 'POST',
        body: {
          body: data.get('body'),
          patient_visible: data.get('patient_visible') === 'on',
          ...(data.get('assessment_id') ? { assessment_id: data.get('assessment_id') } : {})
        }
      });
      form.reset();
      setSaved(true);
      notes.retry();
    } catch (err) {
      setError(err.message);
      if (err.status === 403) review.retry();
    } finally {
      setBusy(false);
    }
  }
  return <div className="stack"><div><span className="eyebrow">{t("Accepted care episode")}</span>
    <h1>{t("Appointment review")}</h1><Link to="/doctor/appointments">{t("← Appointments")}</Link></div>
    <ResourceStatus resource={review} />
    {review.data && <>
      <section className="card stack"><h2>{review.data.appointment.patient_name}</h2>
        <p className="muted">{t("Appointment")}{dateTime(review.data.appointment.scheduled_at)}</p>
        <p className="note-body">{review.data.appointment.reason}</p>
        <dl className="grid-form"><div><dt>{t("Date of birth")}</dt><dd>{review.data.profile.date_of_birth || 'Not provided'}</dd></div>
          <div><dt>{t("Due date")}</dt><dd>{review.data.profile.due_date || 'Not provided'}</dd></div>
          <div><dt>{t("Phone")}</dt><dd>{review.data.profile.phone || 'Not provided'}</dd></div>
          <div><dt>{t("Preferred language")}</dt><dd>{review.data.profile.preferred_language === 'ur' ? t("Urdu") : t("English")}</dd></div></dl>
        <div className="banner">{t('Only records selected for this appointment are shared. Screening results support your clinical review.')}</div>
        {review.data.records.length === 0 && <p>{t("No saved records were shared for this appointment.")}</p>}
        {review.data.records.map(record => <SharedRecord key={record.id} record={record} appointmentId={appointmentId} onAccessLost={review.retry} />)}</section>
      <section className="card stack"><h2>{t("Add a clinician note")}</h2>
        <form onSubmit={submit} className="stack">
          {review.data.assessments?.length > 0 && <label>{t('Assessment for this note')}<select name="assessment_id" required><option value="">{t('Choose an assessment')}</option>{review.data.assessments.map(a => <option key={a.id} value={a.id}>{dateTime(a.created_at)} · {a.maternal_risk}</option>)}</select></label>}
          <label>{t("Note")}<textarea name="body" required minLength={1} maxLength={4000} rows={5} /></label>
          <label className="check-label"><input type="checkbox" name="patient_visible" defaultChecked />
            <span>{t("Share this note with the patient")}</span></label>
          <p className="muted text-sm">{t('Saved notes retain their author and timestamp. Add an amendment to correct a note.')}</p>
          <div><button disabled={busy}>{busy ? t("Saving…") : t("Save clinician note")}</button></div>
        </form></section>
    </>}
    {error && <p className="error" role="alert">{error}</p>}
    {saved && <p className="success" role="status">{t("Clinician note saved.")}</p>}
    <Notes resource={notes} appointmentId={review.data ? appointmentId : null} />
  </div>;
}
