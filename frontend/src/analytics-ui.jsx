import { useState } from 'react';
import { Link } from 'react-router-dom';
import { t } from './i18n.js';
import { useResource, ResourceStatus } from './resources.jsx';
import { RecordFilters } from './search-ui.jsx';
import { reviewLabel } from './clinical-ui.jsx';

const colors = ['#184c85', '#007e87', '#7055b8', '#a14723', '#475569'];
const categoryColor = key => ({ LOW: '#146d49', MEDIUM: '#985d0b', HIGH: '#b42338', PENDING: '#985d0b', REVIEWED: '#146d49', URGENT_FOLLOW_UP: '#b42338' })[key] || 'var(--accent)';
export function CategoryChart({ data, title }) {
  const entries = Object.entries(data || {}).filter(([, value]) => typeof value === 'number');
  const largest = Math.max(...entries.map(([, value]) => value), 1);
  return <figure className="category-chart"><figcaption>{t(title)}</figcaption>{entries.length ? <svg viewBox={`0 0 510 ${entries.length * 49 + 8}`} role="img" aria-label={`${t(title)}: ${entries.map(([k, n]) => `${k} ${n}`).join(', ')}`}>
    {entries.map(([key, count], i) => <g key={key} transform={`translate(0,${i * 49})`}><text x="0" y="20" fontSize="12" fill="#304e49">{t(key.replaceAll('_', ' '))}</text><rect x="175" y="7" width="285" height="22" rx="5" fill="#edf1eb" /><rect x="175" y="7" width={count / largest * 285} height="22" rx="5" fill={categoryColor(key)} /><text x="475" y="23" fontSize="14" fill="#24423c">{count}</text></g>)}
  </svg> : <p className="muted">{t('No records in this view yet.')}</p>}</figure>;
}

export function DoctorCaseWorkspace() {
  const [filters, setFilters] = useState(''), [offset, setOffset] = useState(0);
  const analytics = useResource('/doctors/me/analytics');
  const cases = useResource(`/doctors/me/cases?offset=${offset}${filters ? '&' + filters : ''}`);
  return <div className="stack"><section className="card"><h2>{t('Your care analytics')}</h2><p className="muted">{t('Only active appointments and patient-selected records are included.')}</p><ResourceStatus resource={analytics} />
    {analytics.data && <div className="chart-grid"><CategoryChart data={analytics.data.risk_categories} title="Maternal screening categories" /><CategoryChart data={analytics.data.review_statuses} title="Review progress" /></div>}</section>
    <section className="card stack"><h2>{t('Find a patient assessment')}</h2><RecordFilters person clinical onChange={query => { setFilters(query); setOffset(0); }} /><ResourceStatus resource={cases} />
      {cases.data?.length === 0 && <p>{t('No matching shared assessments.')}</p>}
      {cases.data?.map(row => <article className="record case-row" key={row.assessment.id}><div><h3>{row.patient_name}</h3><p className="muted text-sm">{row.patient_email} · {new Date(row.assessment.created_at).toLocaleString()}</p><span className={`risk-badge risk-${row.assessment.maternal_risk.toLowerCase()}`}>{row.assessment.maternal_risk}</span> <span className="subtle-tag">{reviewLabel(row.assessment.clinical_review?.status || 'PENDING')}</span></div><Link className="button secondary" to={`/doctor/appointments/${row.appointment_id}`}>{t('Open assessment review')}</Link></article>)}
      <div className="action-row"><button className="secondary" disabled={!offset || cases.loading} onClick={() => setOffset(n => n - 50)}>{t('Previous')}</button><button className="secondary" disabled={cases.loading || cases.data?.length !== 50} onClick={() => setOffset(n => n + 50)}>{t('Next')}</button></div>
    </section></div>;
}

function TrendChart({ rows, fields, title, unit }) {
  const usable = [...rows].reverse().filter(r => fields.every(f => Number.isFinite(r.observations[f.key])));
  if (!usable.length) return <section><h3>{t(title)}</h3><p className="muted">{t('Save observations to see your recorded trend.')}</p></section>;
  const values = usable.flatMap(r => fields.map(f => r.observations[f.key] * (f.factor || 1)));
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const x = i => usable.length === 1 ? 240 : 40 + i * 410 / (usable.length - 1);
  const y = value => 150 - (value - min) / span * 110;
  return <figure className="trend-chart"><figcaption>{t(title)} <span className="muted">({unit})</span></figcaption>
    <svg viewBox="0 0 490 192" role="img" aria-label={t(title)}><line x1="40" x2="450" y1="150" y2="150" stroke="#d5dfd6" />
      <text x="4" y="45" fontSize="10" fill="#5e756a">{max.toFixed(1)}</text><text x="4" y="154" fontSize="10" fill="#5e756a">{min.toFixed(1)}</text>
      {fields.map((f, k) => <g key={f.key}><polyline fill="none" stroke={colors[k]} strokeWidth="2.5" points={usable.map((r, i) => `${x(i)},${y(r.observations[f.key] * (f.factor || 1))}`).join(' ')} />{usable.map((r, i) => <circle key={r.id} cx={x(i)} cy={y(r.observations[f.key] * (f.factor || 1))} r="3.5" fill={colors[k]} />)}</g>)}
      <text x="40" y="178" fontSize="10" fill="#5e756a">{new Date(usable[0].created_at).toLocaleDateString()}</text><text x="450" y="178" textAnchor="end" fontSize="10" fill="#5e756a">{new Date(usable.at(-1).created_at).toLocaleDateString()}</text>
    </svg><p className="chart-legend">{fields.map((f, k) => <span key={f.key}><i style={{ background: colors[k] }} />{t(f.label)}</span>)}</p>
    <details className="explanation"><summary>{t('See recorded values')}</summary><div className="table-scroll"><table><thead><tr><th>{t('Saved')}</th>{fields.map(f => <th key={f.key}>{t(f.label)}</th>)}</tr></thead><tbody>{usable.map(row => <tr key={row.id}><td>{new Date(row.created_at).toLocaleString()}</td>{fields.map(f => <td key={f.key}>{(row.observations[f.key] * (f.factor || 1)).toFixed(2)} {unit}</td>)}</tr>)}</tbody></table></div></details>
  </figure>;
}

export function PregnancyTracker() {
  const tracker = useResource('/patients/me/pregnancy-tracker');
  const history = useResource('/patients/me/health-records?offset=0');
  const data = tracker.data;
  return <div className="stack"><section className="card stack"><div className="section-heading"><div><span className="eyebrow">{t('YOUR PREGNANCY JOURNEY')}</span><h2>{t('Pregnancy milestones')}</h2></div><Link className="text-link" to="/patient/profile">{t('Update due date')}</Link></div><ResourceStatus resource={tracker} />
    {data && <>{data.estimated_weeks !== null ? <><div className="pregnancy-progress"><strong>{data.estimated_weeks}<small>{t('weeks')}</small></strong><div><p>{t('Trimester')}{data.trimester}</p><progress max="40" value={Math.min(data.estimated_weeks, 40)} aria-label={t('Estimated pregnancy progress')} /></div></div><p className="muted text-sm">{t(data.source === 'due_date' ? 'Estimated from your saved due date.' : 'Estimated from the pregnancy week in your latest health record.')}</p></> : <p className="banner">{t(data.needs_date_update ? 'Please update your pregnancy dates to show the current stage.' : 'Add your due date or a recorded pregnancy week to personalize this tracker.')}</p>}
      {data.guidance && <p className="journey-guidance">{t(data.guidance)}</p>}
      <ol className="milestone-list">{data.milestones.map(item => <li key={item.week} className={data.estimated_weeks !== null && data.estimated_weeks >= item.week ? 'milestone-passed' : ''}><span className="milestone-week">{t('Week')}{item.week}</span><div><h3>{t(item.title)}</h3><p>{t(item.detail)}</p></div></li>)}</ol>
      <p className="muted text-sm">{t(data.notice)} <a href={data.source_url} target="_blank" rel="noreferrer">{t('Week-by-week information')}</a></p></>}
  </section><section className="card stack"><h2>{t('Your recorded health trends')}</h2><p className="muted">{t('Up to 30 recent saved observations. Lines connect recorded values and do not define normal ranges.')}</p><ResourceStatus resource={history} />
    {history.data && <div className="chart-grid"><TrendChart rows={history.data.slice(0, 30)} fields={[{ key: 'systolic_mmhg', label: 'Systolic' }, { key: 'diastolic_mmhg', label: 'Diastolic' }]} title="Blood pressure trend" unit="mmHg" /><TrendChart rows={history.data.slice(0, 30)} fields={[{ key: 'glucose_mmol_l', label: 'Blood glucose', factor: 18 }]} title="Blood glucose trend" unit="mg/dL" /></div>}
  </section></div>;
}

export function ClinicalOversight() {
  const [open, setOpen] = useState(false);
  return <details className="card explanation" onToggle={e => setOpen(e.currentTarget.open)}><summary>{t('Clinical review and follow-up oversight')}</summary>{open && <ReviewOversightList />}</details>;
}
function ReviewOversightList() {
  const [query, setQuery] = useState(''), [status, setStatus] = useState('URGENT_FOLLOW_UP'), [offset, setOffset] = useState(0);
  const resource = useResource(`/admin/clinical-reviews?offset=${offset}${query ? '&q=' + encodeURIComponent(query) : ''}${status ? '&status=' + status : ''}`);
  return <div className="stack"><form className="record-filters" onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget); setQuery(data.get('q')); setStatus(data.get('status')); setOffset(0); }}>
    <label>{t('Search name or email')}<input type="search" name="q" maxLength={80} /></label><label>{t('Review status')}<select name="status" defaultValue="URGENT_FOLLOW_UP"><option value="">{t('All reviews')}</option>{['PENDING', 'REVIEWED', 'URGENT_FOLLOW_UP'].map(v => <option key={v} value={v}>{reviewLabel(v)}</option>)}</select></label><button className="secondary">{t('Apply filters')}</button></form>
    <ResourceStatus resource={resource} />{resource.data?.length === 0 && <p>{t('No matching clinical reviews.')}</p>}
    {resource.data?.map(row => <article className="record" key={row.id}><h3>{row.patient}</h3>{row.assessment_removed && <p className="subtle-tag">{t('Assessment deleted — review retained for audit')}</p>}<p>{row.doctor} · {reviewLabel(row.status)}</p>{row.follow_up_at && <p>{t('Follow-up requested:')}{new Date(row.follow_up_at).toLocaleString()}</p>}<p className="muted text-sm">{new Date(row.updated_at).toLocaleString()}</p></article>)}
    <div className="action-row"><button className="secondary" disabled={!offset || resource.loading} onClick={() => setOffset(n => n - 50)}>{t('Previous')}</button><button className="secondary" disabled={resource.loading || resource.data?.length !== 50} onClick={() => setOffset(n => n + 50)}>{t('Next')}</button></div>
  </div>;
}
