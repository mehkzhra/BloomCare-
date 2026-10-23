import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from './api.js';
import { t } from './i18n.js';
import { Icon } from './ui.jsx';

const rangeLabel = field => `${field.minimum}–${field.maximum}`;

export function PEScreeningStage({ assessment, capabilities, viewerRole, onChanged }) {
  const [saved, setSaved] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [values, setValues] = useState(() => Object.fromEntries(Object.entries(assessment.clinical_indicators || {}).map(([key, value]) => [key, typeof value === 'boolean' ? (value ? 'yes' : 'no') : value])));
  const screening = saved || assessment.pe_screening;
  const fields = capabilities?.pe_input_fields || screening?.model?.input_fields || [];
  const ready = capabilities?.pe_model_ready && fields.length > 0;
  const outside = fields.filter(field => field.from_record &&
    (!Number.isFinite(assessment.observations?.[field.name]) || assessment.observations[field.name] < field.minimum || assessment.observations[field.name] > field.maximum));
  const additional = fields.filter(field => !field.from_record);
  const coverageIssues = assessment.pe_input_issues?.length ? assessment.pe_input_issues : outside.map(field => ({ ...field, value: assessment.observations[field.name] }));
  const durationOutsidePE = coverageIssues.some(field => field.name === 'gestational_weeks');
  const statusLabel = assessment.pe_status === 'OUTSIDE_COVERAGE' ? 'Doctor review needed' : assessment.pe_status === 'UNAVAILABLE' ? 'Screening unavailable' : 'Measurements needed';

  async function submit(event) {
    event.preventDefault();
    if (!event.currentTarget.checkValidity()) { event.currentTarget.reportValidity(); return; }
    setBusy(true); setError(null);
    const body = Object.fromEntries(additional.map(field => [field.name,
      field.kind === 'boolean' ? values[field.name] === 'yes' : Number(values[field.name])]));
    try {
      const result = await api(`/patients/me/assessments/${assessment.id}/pe`, { method: 'POST', body });
      if (!result.pe_screening) throw new Error(t('PE screening could not be verified. Please refresh this assessment.'));
      setSaved(result.pe_screening);
      onChanged?.(result);
    } catch (err) { setError(err); }
    finally { setBusy(false); }
  }

  return <section className="pe-status stack" aria-label={t('Pre-eclampsia screening')}>
    <div className="assessment-heading"><h3>{t('Pre-eclampsia screening')}</h3>
      <span className={`risk-badge ${screening ? 'risk-' + screening.risk.toLowerCase() : 'status-neutral'}`}>{screening ? screening.risk : t(statusLabel)}</span></div>
    {screening ? <div className="stack" role="status">
      <h4 className="pe-result-title">{t('PE screening category:')}{' '}{screening.risk}</h4>
      <p className="muted text-sm m-0">{t('Saved')}{new Date(screening.created_at).toLocaleString()}</p>
      <p className="m-0">{t(viewerRole === 'doctor' ? 'Review this screening with the patient. A LOW category does not rule out pre-eclampsia.' : 'Review this screening result with your doctor. A LOW category does not rule out pre-eclampsia.')}</p>
      <details className="explanation"><summary>{t('View PE measurements')}</summary><p className="muted text-sm">{t('The haemoglobin unit is not confirmed here. Check the original lab result with your doctor.')}</p>
        <dl className="grid-form measurements">{Object.entries(screening.observations).map(([name, value]) => {
          const field = fields.find(item => item.name === name);
          return <div key={name}><dt>{t(field?.label || name.replaceAll('_', ' '))}</dt><dd>{typeof value === 'boolean' ? t(value ? 'Yes' : 'No') : value} {field?.unit || ''}</dd></div>;
        })}</dl>
      </details>
    </div> : <>
      <p className="m-0">{t('Your assessment needs a closer look at pre-eclampsia. Complete the measured details below, or arrange a doctor review.')}</p>
      {assessment.pe_status === 'OUTSIDE_COVERAGE' && <div className="coverage-panel"><strong>{t('Doctor review is the next step')}</strong><p>{t('Your readings are saved. PE screening cannot assess the values below, so no PE category was produced. Share these readings with your doctor.')}</p>
        {durationOutsidePE && <p>{t('Your pregnancy duration is saved as entered. This PE screening is unavailable for your recorded week of pregnancy.')} {t('This does not mean LOW risk. Your doctor can review the readings and advise you.')}</p>}
        {coverageIssues.length > 0 && <div className="table-scroll"><table className="coverage-table"><thead><tr><th>{t('Recorded measurement')}</th><th>{t('Your value')}</th><th>{t('Supported screening range')}</th></tr></thead><tbody>{coverageIssues.map(field => <tr key={field.name}><td>{t(field.label)}</td><td>{field.value} {field.unit}</td><td>{rangeLabel(field)} {field.unit}</td></tr>)}</tbody></table></div>}
        <p className="scope-note">{t('These are screening limits, not healthy ranges. Keep your actual measurements.')}</p><p className="scope-note">{t('No PE category was generated. This message does not confirm or rule out pre-eclampsia.')}</p></div>}
      {viewerRole !== 'patient' ? <p className="text-sm muted m-0">{t(assessment.pe_status === 'OUTSIDE_COVERAGE' ? 'Review the recorded values and document your clinical decision below.' : assessment.pe_status === 'UNAVAILABLE' ? 'PE screening is unavailable. Review the saved measurements and record your clinical decision.' : 'The patient has not completed the additional PE measurements.')}</p> : !ready ?
        <p className="text-sm muted m-0">{t('PE screening is currently unavailable. You can still arrange a clinical review.')}</p> : assessment.pe_status === 'OUTSIDE_COVERAGE' ? <p className="muted">{t('Your actual readings are preserved. Arrange a doctor review.')}</p> : <>
        <div className="pe-record-summary"><span>{t('From your saved record')}</span><strong>{assessment.observations.age_years} {t('years')} · {assessment.observations.gestational_weeks} {t('weeks')} · {assessment.observations.systolic_mmhg}/{assessment.observations.diastolic_mmhg} mmHg</strong></div>
        {outside.length > 0 ? <div className="banner" role="alert">{t('These saved readings need a doctor review. No PE category can be produced for them.')}<ul className="limitations">{outside.map(field => <li key={field.name}>{t(field.label)}: {assessment.observations[field.name]} {field.unit} ({t('Supported range:')} {rangeLabel(field)} {field.unit})</li>)}</ul></div> : <form className="stack pe-form" aria-label={t('Additional PE measurements')} onSubmit={submit}>
          <p className="text-sm muted m-0">{t('Use measured values from your antenatal and laboratory records. Do not guess missing results.')} {t('The haemoglobin unit is not confirmed here. Check the original lab result with your doctor.')}</p>
          <div className="grid-form">{additional.map(field => <label key={field.name}>{t(field.label)}{field.unit && <span className="muted"> ({field.unit})</span>}
            {field.kind === 'boolean' ? <select required name={field.name} value={values[field.name] ?? ''} disabled={busy} onChange={event => setValues(previous => ({ ...previous, [field.name]: event.target.value }))}>
              <option value="" disabled>{t('Select a result')}</option><option value="yes">{t('Yes')}</option><option value="no">{t('No')}</option>
            </select> : <input name={field.name} type="number" required min={field.minimum} max={field.maximum} step={field.kind === 'integer' ? 1 : 'any'} placeholder={rangeLabel(field)} value={values[field.name] ?? ''} disabled={busy} onChange={event => setValues(previous => ({ ...previous, [field.name]: event.target.value }))} />}
          </label>)}</div>
          {error && <div className="error" role="alert">{error.message}{error.details?.fields && <ul className="limitations">{error.details.fields.map(field => <li key={field.feature}>{t(field.label)}: {rangeLabel(field)} {field.unit}</li>)}</ul>}</div>}
          <p className="text-sm muted m-0">{t('Review the measurements before saving. For changed measurements, create a new health record.')}</p>
          <div><button disabled={busy}>{busy ? t('Screening…') : t('Complete PE screening')}<Icon name="arrow" size={17} /></button></div>
        </form>}
      </>}
    </>}
    {viewerRole === 'patient' && <Link className="text-link" to={`/patient/appointments?review=pe&record=${encodeURIComponent(assessment.health_record_id)}`}>{t('Arrange a doctor review')}<Icon name="arrow" size={16} /></Link>}
  </section>;
}
