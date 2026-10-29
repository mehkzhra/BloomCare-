import { t } from "./i18n.js";
import { useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { api } from './api.js';
import { ResourceStatus, useResource } from './pages.jsx';
import { Icon } from './ui.jsx';
import { BloodPressureNotice, bloodPressureAction } from './blood-pressure-notice.jsx';
import { PEScreeningStage } from './pe-screening.jsx';
import { AssessmentReportActions, CarePlanPanel, ClinicalReviewPanel, WhatsAppAssessmentAlert } from './clinical-ui.jsx';
import { RecordFilters } from './search-ui.jsx';
import { AssessmentRemoval, HealthRecordRemoval, RemovedAssessments } from './assessment-removal.jsx';
export function AssessmentCard({
  assessment: initialAssessment,
  viewerRole = 'patient',
  peCapabilities,
  appointmentId,
  onRemoved
}) {
  const [latest, setLatest] = useState(null);
  const [removed, setRemoved] = useState(false);
  const assessment = latest || initialAssessment;
  const peRequired = assessment.pe_required ?? ['MEDIUM', 'HIGH'].includes(assessment.maternal_risk);
  if (removed) return <section className="card success" role="status">{t('Assessment deleted from active history.')} <Link to="/patient/health">{t('Add a corrected health record')} →</Link></section>;
  return <article className="card stack assessment-result">
    <BloodPressureNotice observations={assessment.observations} saved />
    <div className="assessment-stages"><span><b className="stage-number">1</b>{t('Maternal risk screening')}</span>{peRequired && <><Icon name="arrow" size={15} /><span className="pending-stage"><b className="stage-number">2</b>{t('Pre-eclampsia screening')}</span></>}</div>
    <div className="assessment-heading"><div><span className="eyebrow">{t(viewerRole === 'doctor' ? 'Patient assessment' : 'Your assessment result')}</span>
      <h2 className="!text-2xl">{t("Screening category:")}{assessment.maternal_risk}</h2></div>
      <span className={'risk-badge risk-' + assessment.maternal_risk.toLowerCase()}>{assessment.maternal_risk}</span></div>
    <div className="assessment-record-toolbar"><p className="muted text-sm m-0">{t("Saved")}{new Date(assessment.created_at).toLocaleString()}</p>{viewerRole === 'patient' && <AssessmentRemoval assessmentId={assessment.id} onRemoved={() => { setRemoved(true); onRemoved?.(assessment.id); }} />}</div>
    <p className="screening-notice">{t('Screening has not been clinically validated. This result supports a doctor conversation; it is not a diagnosis.')}</p>
    {peRequired ? <PEScreeningStage assessment={assessment} capabilities={peCapabilities} viewerRole={viewerRole} onChanged={setLatest} /> : <p className="muted text-sm">{t('PE review was not triggered by this result. A low category does not rule out pre-eclampsia.')}</p>}
    <section className="result-next-step"><span className="step-icon"><Icon name="calendar" size={20} /></span><div><strong>{t('Your next step')}</strong><p>{t(viewerRole === 'doctor' ? 'Review the recorded readings and add your clinical assessment below.' : assessment.clinical_review?.status === 'URGENT_FOLLOW_UP' ? 'Read your doctor’s follow-up instructions below and arrange the requested care.' : 'Review your readings and this result with your doctor, even when the category is LOW.')}</p></div>{viewerRole === 'patient' && bloodPressureAction(assessment.observations) !== 'IMMEDIATE_MATERNITY_REVIEW' && <Link className="text-link" to="/patient/appointments">{t('Book a doctor')}<Icon name="arrow" size={15} /></Link>}</section>
    <details className="explanation"><summary>{t('View saved measurements')}</summary><Measurements values={assessment.observations} /></details>
    <CarePlanPanel assessment={assessment} onChanged={setLatest} viewerRole={viewerRole} />
    <ClinicalReviewPanel assessment={assessment} onChanged={setLatest} viewerRole={viewerRole} appointmentId={appointmentId} />
    <AssessmentReportActions key={[assessment.pe_screening?.id, assessment.care_plan?.id, assessment.clinical_review?.version].join(':')} assessment={assessment} viewerRole={viewerRole} appointmentId={appointmentId} />
    {viewerRole === 'patient' && <WhatsAppAssessmentAlert assessmentId={assessment.id} />}
    <details className="explanation"><summary>{t('Understanding this screening')}</summary>
      <p>{t('This result helps you discuss your readings with your doctor. It cannot diagnose a condition or rule out complications, including when the category is LOW.')}</p>
      <p>{t('Screening has not been clinically validated. Continue your antenatal visits and ask your care team about any symptoms or concerns.')}</p>
    </details>
  </article>;
}
export function RecordAssessmentPage() {
  const {
    recordId
  } = useParams();
  return <RecordAssessment key={recordId} recordId={recordId} />;
}
function RecordAssessment({
  recordId
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const record = useResource('/patients/me/health-records/' + recordId);
  const history = useResource('/patients/me/health-records/' + recordId + '/assessments');
  const capabilities = useResource('/capabilities');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [created, setCreated] = useState(null);
  const [removedNotice, setRemovedNotice] = useState(false);
  const results = created ? [created, ...(history.data || []).filter(item => item.id !== created.id)] : history.data;
  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const result = await api('/patients/me/assessments', {
        method: 'POST',
        body: {
          health_record_id: recordId
        }
      });
      setCreated(result);
      history.retry();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  const ready = capabilities.data?.pregnancy_model_ready && record.data && !history.loading && !history.error;
  return <div className="stack"><div><span className="eyebrow">{t("One record, explained")}</span>
    <h1 className="!text-3xl">{t("Health assessment")}</h1><Link to="/patient/history">{t("← Health history")}</Link></div>
    {location.state?.carePlanError && <p className="banner" role="alert">{t('The assessment was saved. The care plan could not be prepared:')}{location.state.carePlanError}</p>}
    {removedNotice && <p className="success" role="status">{t('Assessment deleted from active history.')} <Link to="/patient/health">{t('Add a corrected health record')} →</Link></p>}
    <section className="card stack"><ResourceStatus resource={record} />{record.data && <>
      <div className="assessment-record-toolbar"><h2>{t("Saved measurements")}</h2><HealthRecordRemoval recordId={recordId} onRemoved={() => navigate('/patient/history', { state: { recordRemoved: true } })} /></div><BloodPressureNotice observations={record.data.observations} saved /><Measurements values={record.data.observations} />
      </>}
      <ResourceStatus resource={capabilities} />
      {capabilities.data && !capabilities.data.pregnancy_model_ready && <div className="banner">{t("New assessments are currently unavailable. Previously saved results remain readable.")}</div>}
      <p className="screening-notice">{t('Screening has not been clinically validated. This result supports a doctor conversation; it is not a diagnosis.')}</p>
      {error && <div className="error" role="alert">{error.message}
        {error.details?.fields && <ul className="limitations">{error.details.fields.map(field => <li key={field.feature}>{field.label}: {field.value} {field.unit}{t("; supported screening range")}{' '}
            {Number(field.minimum).toFixed(2)}–{Number(field.maximum).toFixed(2)} {field.unit}.</li>)}</ul>}</div>}
      <div><button disabled={!ready || busy} onClick={submit}>{busy ? t("Assessing…") : t("Run assessment")}<Icon name="arrow" size={17} /></button></div>
    </section>
    <ResourceStatus resource={history} />
    {results?.length === 0 && <p className="muted">{t("No assessment has been saved for this record.")}</p>}
    {results?.map(item => <AssessmentCard key={item.id} assessment={item} peCapabilities={capabilities.data} onRemoved={() => { setCreated(null); setRemovedNotice(true); history.retry(); }} />)}</div>;
}
function Measurements({
  values
}) {
  if (!values) return <p className="muted">{t('Readings are not available for this result.')}</p>;
  return <dl className="grid-form measurements">
    <div><dt>{t("Age")}</dt><dd>{values.age_years}{t("years")}</dd></div>
    <div><dt>{t("Pregnancy duration")}</dt><dd>{values.gestational_weeks}{t("weeks")}</dd></div>
    <div><dt>{t("Blood pressure")}</dt><dd>{values.systolic_mmhg}/{values.diastolic_mmhg}{t("mmHg")}</dd></div>
    <div><dt>{t("Blood glucose")}</dt><dd>{values.glucose_mmol_l}{t("mmol/L")}</dd></div>
    <div><dt>{t("Temperature")}</dt><dd>{values.temperature_c}{t("°C")}</dd></div>
    <div><dt>{t("Heart rate")}</dt><dd>{values.heart_rate_bpm}{t("beats/minute")}</dd></div>
  </dl>;
}
export function AssessmentHistoryPage() {
  const [offset, setOffset] = useState(0);
  const [filters, setFilters] = useState('');
  const [removedCount, setRemovedCount] = useState(0);
  const history = useResource('/patients/me/assessments?offset=' + offset + (filters ? '&' + filters : ''));
  const capabilities = useResource('/capabilities');
  return <div className="stack"><div><span className="eyebrow">{t("Your results, over time")}</span>
    <h1 className="!text-3xl">{t("Assessment history")}</h1>
    <p className="muted">{t("Your saved readings, screening results and doctor reviews, together.")}</p></div>
    <RecordFilters clinical onChange={query => { setFilters(query); setOffset(0); }} />
    {removedCount > 0 && <p className="success" role="status">{t('Assessment deleted from active history.')} <Link to="/patient/health">{t('Add a corrected health record')} →</Link></p>}
    <ResourceStatus resource={history} />
    {history.data?.length === 0 && <div className="card"><p>{t("No assessments have been saved on this page.")}</p>
      <Link to="/patient/history">{t("Choose a health record →")}</Link></div>}
    {history.data?.map(item => <div className="stack" key={item.id}><AssessmentCard assessment={item} peCapabilities={capabilities.data} onRemoved={() => { setRemovedCount(n => n + 1); history.retry(); }} />
      <Link to={'/patient/assessments/' + item.health_record_id}>{t("View linked measurements →")}</Link></div>)}
    <div className="flex gap-3"><button className="secondary" disabled={offset === 0 || history.loading} onClick={() => setOffset(n => n - 50)}>{t("Newer results")}</button>
      <button className="secondary" disabled={history.data?.length !== 50 || history.loading} onClick={() => setOffset(n => n + 50)}>{t("Older results")}</button></div>
    <RemovedAssessments version={removedCount} />
  </div>;
}
