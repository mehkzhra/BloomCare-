import { t } from './i18n.js';

export function bloodPressureAction(values = {}) {
  const raw = [values.systolic_mmhg, values.diastolic_mmhg];
  if (raw.some(value => value === '' || value == null || typeof value === 'boolean')) return null;
  const [systolic, diastolic] = raw.map(Number);
  if (![systolic, diastolic].every(Number.isFinite) || systolic <= diastolic
    || systolic < 60 || systolic > 260 || diastolic < 30 || diastolic > 180) return null;
  if (systolic >= 160 || diastolic >= 110) return 'IMMEDIATE_MATERNITY_REVIEW';
  if (systolic >= 140 || diastolic >= 90) return 'SAME_DAY_MATERNITY_CONTACT';
  return null;
}

export function BloodPressureNotice({ observations = {}, saved = false }) {
  const action = bloodPressureAction(observations);
  if (!action) return null;
  const immediate = action === 'IMMEDIATE_MATERNITY_REVIEW';
  const weeks = observations.gestational_weeks;
  return <aside className={immediate ? 'error stack' : 'coverage-panel stack'} role="alert" aria-label={t('Blood pressure care guidance')}>
    <strong>{t(immediate ? 'Seek urgent maternity care now' : 'Contact your maternity team today')}</strong>
    <p>{t(saved ? 'Recorded blood pressure:' : 'Entered blood pressure:')} {observations.systolic_mmhg}/{observations.diastolic_mmhg} mmHg.</p>
    <p>{t(immediate ? 'If this is your current reading, seek urgent maternity or emergency care now. Do not wait for a model result or an online appointment.' : 'If this is your current reading, contact your maternity team today for assessment.')}</p>
    <p>{t('This is blood pressure guidance, not a PE prediction or diagnosis. A LOW screening category does not cancel this advice.')}</p>
    {weeks !== '' && weeks != null && Number.isFinite(Number(weeks)) && Number(weeks) < 20 && <p>{t('Before 20 weeks, high blood pressure still needs assessment; it does not establish pre-eclampsia.')}</p>}
    <p>{t('If this is an older reading already assessed, follow your clinician’s plan. Keep the recorded values unchanged.')}</p>
  </aside>;
}
