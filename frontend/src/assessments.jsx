import { t } from "./i18n.js";
import { useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { api } from './api.js';
import { ResourceStatus, percent, useResource } from './pages.jsx';
import { Icon } from './ui.jsx';
import { PEScreeningStage } from './pe-screening.jsx';
import { AssessmentReportActions, CarePlanPanel, ClinicalReviewPanel, WhatsAppAssessmentAlert } from './clinical-ui.jsx';
import { RecordFilters } from './search-ui.jsx';
import { AssessmentRemoval, HealthRecordRemoval, RemovedAssessments } from './assessment-removal.jsx';
export function Contributions({
  explanation
}) {
  const features = [...explanation.features].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
  const largest = Math.max(...features.map(item => Math.abs(item.contribution)), 0.001);
  return <details className="explanation"><summary>{t("How measurements contributed to this result")}</summary>
    <p className="muted text-sm">{t("SHAP explains this record’s")}{explanation.explained_class}{t("model score. A positive contribution raises that class score; a negative contribution lowers it. Contributions explain model behavior, not medical causes.")}</p>
    <p className="text-sm">{t("Base score")}{percent(explanation.base_score)}{t("→ record score")}{percent(explanation.model_score)}.</p>
    <ul className="contributions">{features.map(item => {
        const positive = item.contribution >= 0;
        const width = Math.abs(item.contribution) / largest * 50;
        return <li key={item.feature}><div className="contribution-label">
        <span>{t(item.label)} <small className="muted">({typeof item.value === 'boolean' ? t(item.value ? 'Yes' : 'No') : item.value} {item.unit})</small></span>
        <strong>{positive ? '+' : ''}{(item.contribution * 100).toFixed(2)}{t("pp")}</strong></div>
        <div className="contribution-track" aria-hidden="true"><span className={positive ? 'contribution-positive' : 'contribution-negative'} style={{
              width: width + '%',
              left: (positive ? 50 : 50 - width) + '%'
            }} /></div></li>;
      })}</ul><p className="muted text-sm">{t("pp = percentage points of the model’s class score. Bar lengths compare contribution sizes.")}</p>
  </details>;
}
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
    <div className="assessment-stages"><span><b className="stage-number">1</b>{t('Maternal risk screening')}</span>{peRequired && <><Icon name="arrow" size={15} /><span className="pending-stage"><b className="stage-number">2</b>{t('Pre-eclampsia screening')}</span></>}</div>
    <div className="assessment-heading"><div><span className="eyebrow">{t("Your assessment result")}</span>
      <h2 className="!text-2xl">{t("Screening category:")}{assessment.maternal_risk}</h2></div>
      <span className={'risk-badge risk-' + assessment.maternal_risk.toLowerCase()}>{assessment.maternal_risk}</span></div>
    <div className="assessment-record-toolbar"><p className="muted text-sm m-0">{t("Saved")}{new Date(assessment.created_at).toLocaleString()} · {assessment.model.version}</p>{viewerRole === 'patient' && <AssessmentRemoval assessmentId={assessment.id} onRemoved={() => { setRemoved(true); onRemoved?.(assessment.id); }} />}</div>
    <p className="screening-notice">{t('Screening support only. Clinical validation is pending, and a low result does not rule out complications.')}</p>
    {peRequired ? <PEScreeningStage assessment={assessment} capabilities={peCapabilities} viewerRole={viewerRole} onChanged={setLatest} /> : <p className="muted text-sm">{t('PE review was not triggered by this result. A low category does not rule out pre-eclampsia.')}</p>}
    <details className="explanation"><summary>{t("Model class scores")}</summary><dl className="evaluation-grid">
      {['LOW', 'MEDIUM', 'HIGH'].map(risk => <div key={risk}><dt>{risk}</dt><dd>{percent(assessment.class_scores[risk])}</dd></div>)}</dl>
      <p className="muted text-sm">{t("Uncalibrated model scores, not probabilities of complications.")}</p></details>
    <Contributions explanation={assessment.explanation} />
    {assessment.pe_screening?.explanation && <details className="explanation"><summary>{t('PE feature explanation')}</summary><Contributions explanation={assessment.pe_screening.explanation} /></details>}
    {assessment.pe_screening && !assessment.pe_screening.explanation && viewerRole === 'patient' && <LegacyPEExplanation assessment={assessment} onChanged={setLatest} />}
    <CarePlanPanel assessment={assessment} onChanged={setLatest} viewerRole={viewerRole} />
    <ClinicalReviewPanel assessment={assessment} onChanged={setLatest} viewerRole={viewerRole} appointmentId={appointmentId} />
    <AssessmentReportActions key={[assessment.pe_screening?.id, assessment.care_plan?.id, assessment.clinical_review?.version].join(':')} assessment={assessment} viewerRole={viewerRole} appointmentId={appointmentId} />
    {viewerRole === 'patient' && <WhatsAppAssessmentAlert assessmentId={assessment.id} />}
    <details className="explanation"><summary>{t('Understanding this screening')}</summary>
      <p>{t('This category helps you discuss your recorded measurements with your doctor. It does not diagnose a complication or replace a clinical review.')}</p>
      <p>{t('The model can miss some medium-risk cases. Review the measurements and result with your clinician even when the category is LOW.')}</p>
      <p>{t('Maternal-risk screening and pre-eclampsia screening are separate. PE needs additional measured values within its model coverage.')}</p>
      <p>{t('Maternal screening does not use pregnancy duration. Its category does not establish a week-specific prediction or replace antenatal care.')}</p>
    </details>
  </article>;
}
function LegacyPEExplanation({ assessment, onChanged }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function load() {
    setBusy(true); setError('');
    try { onChanged(await api(`/patients/me/assessments/${assessment.id}/pe/explanation`, { method: 'POST' })); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <div><button className="secondary" disabled={busy} onClick={load}>{t('Explain saved PE result')}</button>{error && <p role="alert" className="error">{error}</p>}</div>;
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
      <div className="assessment-record-toolbar"><h2>{t("Saved measurements")}</h2><HealthRecordRemoval recordId={recordId} onRemoved={() => navigate('/patient/history', { state: { recordRemoved: true } })} /></div><Measurements values={record.data.observations} />
      </>}
      <ResourceStatus resource={capabilities} />
      {capabilities.data && !capabilities.data.pregnancy_model_ready && <div className="banner">{t("New assessments are currently unavailable. Previously saved results remain readable.")}</div>}
      <p className="screening-notice">{t('Results support a conversation with your doctor. This screening model has not been clinically validated. Always enter actual measurements.')}</p>
      {error && <div className="error" role="alert">{error.message}
        {error.details?.fields && <ul className="limitations">{error.details.fields.map(field => <li key={field.feature}>{field.label}: {field.value} {field.unit}{t("; model training range approximately")}{' '}
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
    <p className="muted">{t("Each result is linked to its saved observations and model version.")}</p></div>
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
