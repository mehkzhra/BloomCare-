import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from './api.js';
import { t, useLanguage } from './i18n.js';
import { useResource } from './resources.jsx';
import { Icon } from './ui.jsx';

const basic = [
  ['age_years', 'Age (years)', 10, 65, 1], ['gestational_weeks', 'Pregnancy duration (weeks)', 0, 45, 'any'],
  ['systolic_mmhg', 'Systolic blood pressure (mmHg)', 60, 260, 1], ['diastolic_mmhg', 'Diastolic blood pressure (mmHg)', 30, 180, 1],
  ['glucose_mmol_l', 'Blood glucose', 1, 40, 'any'], ['temperature_c', 'Body temperature', 32, 43, 'any'],
  ['heart_rate_bpm', 'Heart rate (beats/minute)', 30, 220, 1],
];
const extra = [
  ['gravida', 'Number of pregnancies', 1, 30, 1], ['parity', 'Number of previous births', 0, 25, 1],
  ['bmi', 'BMI (kg/m²)', 5, 100, 'any'], ['hb', 'Haemoglobin (HB)', 0, 30, 'any'],
  ['fetal_weight_kg', 'Estimated fetal weight (kg)', 0.0001, 15, 'any'],
  ['amniotic_fluid_level_cm', 'Amniotic fluid measurement (cm)', 0, 60, 'any'],
];
const booleans = [['diabetes', 'Diagnosed diabetes'], ['history_of_hypertension', 'History of hypertension'], ['protein_uria', 'Protein in urine']];
const clean = number => Number(number.toPrecision(12));
const hint = values => values.map(value => Number(value.toFixed(4))).join('–');

export function HealthPage() {
  const capabilities = useResource('/capabilities');
  const navigate = useNavigate(), language = useLanguage();
  const [values, setValues] = useState({}), [glucoseUnit, setGlucoseUnit] = useState('mg/dL'), [temperatureUnit, setTemperatureUnit] = useState('°F');
  const [busy, setBusy] = useState(false), [phase, setPhase] = useState(''), [error, setError] = useState(''), [savedRecord, setSavedRecord] = useState(null);
  const attempt = useRef({});
  const weeks = values.gestational_weeks === '' || values.gestational_weeks === undefined ? null : Number(values.gestational_weeks);
  const peWeeks = capabilities.data?.pe_input_fields?.find(field => field.name === 'gestational_weeks');
  const durationOutsidePE = Number.isFinite(weeks) && peWeeks && (weeks < peWeeks.minimum || weeks > peWeeks.maximum);
  function displayValue(key, value) { return key === 'glucose_mmol_l' && glucoseUnit === 'mg/dL' ? value * 18 : key === 'temperature_c' && temperatureUnit === '°F' ? value * 9 / 5 + 32 : value; }
  function changeUnit(key, next) {
    const previous = key === 'glucose_mmol_l' ? glucoseUnit : temperatureUnit;
    if (values[key] !== undefined && values[key] !== '' && previous !== next) {
      const value = Number(values[key]);
      const converted = key === 'glucose_mmol_l' ? (next === 'mg/dL' ? value * 18 : value / 18) : next === '°F' ? value * 9 / 5 + 32 : (value - 32) * 5 / 9;
      setValues(v => ({ ...v, [key]: String(clean(converted)) }));
    }
    if (key === 'glucose_mmol_l') setGlucoseUnit(next); else setTemperatureUnit(next);
  }
  async function submit(event) {
    event.preventDefault(); const form = event.currentTarget;
    if (!form.checkValidity()) { form.reportValidity(); return; }
    const complete = event.nativeEvent.submitter?.value === 'assess';
    const data = new FormData(form);
    const body = Object.fromEntries(basic.map(([key]) => [key, Number(data.get(key))]));
    if (glucoseUnit === 'mg/dL') body.glucose_mmol_l = clean(body.glucose_mmol_l / 18);
    if (temperatureUnit === '°F') body.temperature_c = clean((body.temperature_c - 32) * 5 / 9);
    if (body.diastolic_mmhg >= body.systolic_mmhg) { setError('Systolic pressure must be greater than diastolic pressure.'); return; }
    const clinical = {};
    extra.forEach(([key]) => { if (data.get('clinical_' + key) !== '') clinical[key] = Number(data.get('clinical_' + key)); });
    booleans.forEach(([key]) => { const value = data.get('clinical_' + key); if (value) clinical[key] = value === 'yes'; });
    if (Object.keys(clinical).length) body.clinical_indicators = clinical;
    const digest = JSON.stringify(body);
    if (attempt.current.digest !== digest) attempt.current = { digest, id: crypto.randomUUID() };
    body.request_id = attempt.current.id;
    setBusy(true); setError(''); setSavedRecord(null); setPhase(complete ? 'Assessing…' : 'Saving…');
    try {
      if (!complete) { await api('/patients/me/health-records', { method: 'POST', body }); navigate('/patient/history'); return; }
      let result = await api('/patients/me/complete-assessment', { method: 'POST', body });
      let carePlanError;
      if (data.get('care_plan_consent') === 'on') {
        setPhase('Preparing care plan…');
        try { result = await api(`/patients/me/assessments/${result.id}/care-plan`, { method: 'POST', body: { consent: true, language }, timeoutMs: 60000 }); }
        catch (err) { carePlanError = err.message; }
      }
      navigate('/patient/assessments/' + result.health_record_id, { state: { carePlanError } });
    } catch (err) { setError(err.message); setSavedRecord(err.details?.health_record_id || null); }
    finally { setBusy(false); }
  }
  return <div className="card stack"><div className="workspace-heading"><div><span className="eyebrow">{t('One clear health record')}</span><h1 className="!text-3xl">{t('Add health observations')}</h1>
    <p className="muted">{t('Enter actual measured values. Faint ranges show model coverage, not normal clinical ranges.')}</p></div><Link className="button secondary" to="/patient/history">{t('View health history')}<Icon name="arrow" size={16} /></Link></div>
    <form className="stack" onSubmit={submit}>
      <div className="unit-controls"><label>{t('Glucose unit')}<select value={glucoseUnit} onChange={e => changeUnit('glucose_mmol_l', e.target.value)} disabled={busy}><option>mg/dL</option><option>mmol/L</option></select></label>
        <label>{t('Temperature unit')}<select value={temperatureUnit} onChange={e => changeUnit('temperature_c', e.target.value)} disabled={busy}><option>°F</option><option>°C</option></select></label></div>
      <div className="grid-form">{basic.map(([key, original, min, max, step]) => {
        const label = key === 'glucose_mmol_l' ? `Blood glucose (${glucoseUnit})` : key === 'temperature_c' ? `Body temperature (${temperatureUnit})` : original;
        const range = capabilities.data?.assessment_ranges?.[key] || [min, max];
        return <label key={key}>{t(label)}<input name={key} type="number" required min={displayValue(key, min)} max={displayValue(key, max)} step={step} placeholder={hint(range.map(v => displayValue(key, v)))} value={values[key] ?? ''} disabled={busy} onChange={e => setValues(v => ({ ...v, [key]: e.target.value }))} /></label>;
      })}</div>
      {durationOutsidePE && <aside className="service-note" role="status"><strong>{t('Pregnancy duration and screening')}</strong>
        <p>{t('Your pregnancy duration is saved as entered. Maternal screening uses your other measurements; pregnancy weeks are not an input to that model.')}</p>
        <p>{t('The PE model supports pregnancy duration from')} {peWeeks.minimum}–{peWeeks.maximum} {t('weeks')}. {t('Outside that coverage, no PE category is generated. This is not a LOW result; discuss your observations with your clinician.')}</p>
      </aside>}
      <details className="explanation antenatal-inputs"><summary>{t('Antenatal and laboratory measurements')}</summary>
        <p className="muted text-sm">{t('Enter known measurements for the PE stage. Leave unknown results empty; the system will ask for missing inputs if screening is triggered.')}</p>
        <div className="grid-form">{extra.map(([key, label, min, max, step]) => {
          const field = capabilities.data?.pe_input_fields?.find(f => f.name === key);
          return <label key={key}>{t(label)}<input type="number" name={'clinical_' + key} min={min} max={max} step={step} disabled={busy} placeholder={field ? hint([field.minimum, field.maximum]) : ''} /></label>;
        })}{booleans.map(([key, label]) => <label key={key}>{t(label)}<select name={'clinical_' + key} disabled={busy} defaultValue=""><option value="">{t('Unknown / not recorded')}</option><option value="yes">{t('Yes')}</option><option value="no">{t('No')}</option></select></label>)}</div>
      </details>
      <label className="check-label"><input name="care_plan_consent" type="checkbox" disabled={busy} />{t('Also prepare my care guide. I agree to send these measurements and screening results to Groq; my name and email are excluded.')}</label>
      <div className="action-row"><button type="submit" name="action" value="assess" disabled={busy || !capabilities.data?.pregnancy_model_ready}>{busy ? t(phase) : t('Run complete assessment')}<Icon name="arrow" size={16} /></button>
        <button type="submit" name="action" value="save" className="secondary" disabled={busy}>{t('Save health record')}</button></div>
      {error && <p role="alert" className="error">{error}{savedRecord && <> <Link to={'/patient/assessments/' + savedRecord}>{t('Open the saved record')}</Link></>}</p>}
      {capabilities.data && !capabilities.data.pregnancy_model_ready && <p className="service-note">{t('New assessments are currently unavailable. You can still save actual observations.')}</p>}
      {capabilities.error && <p className="error" role="alert">{capabilities.error}<button className="secondary" type="button" onClick={capabilities.retry}>{t('Retry')}</button></p>}
    </form></div>;
}
