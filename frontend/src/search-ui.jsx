import { useRef } from 'react';
import { t } from './i18n.js';

export function RecordFilters({ onChange, clinical = false, person = false }) {
  const form = useRef(null);
  function submit(event) {
    event.preventDefault(); const data = new FormData(event.currentTarget), params = new URLSearchParams();
    for (const key of ['q', 'risk', 'review_status']) if (data.get(key)) params.set(key, data.get(key));
    if (data.get('from_date')) params.set('from_at', new Date(data.get('from_date') + 'T00:00:00').toISOString());
    if (data.get('to_date')) { const end = new Date(data.get('to_date') + 'T00:00:00'); end.setDate(end.getDate() + 1); params.set('to_at', end.toISOString()); }
    onChange(params.toString());
  }
  return <form className="record-filters" ref={form} onSubmit={submit}>
    <label>{t(person ? 'Search name or email' : 'Find a recorded measurement')}<input type="search" name="q" maxLength={80} /></label>
    {clinical && <><label>{t('Risk category')}<select name="risk"><option value="">{t('All categories')}</option>{['LOW', 'MEDIUM', 'HIGH'].map(v => <option key={v}>{v}</option>)}</select></label>
      <label>{t('Review status')}<select name="review_status"><option value="">{t('All reviews')}</option><option value="PENDING">{t('Awaiting review')}</option><option value="REVIEWED">{t('Reviewed')}</option><option value="URGENT_FOLLOW_UP">{t('Urgent follow-up')}</option></select></label></>}
    <label>{t('From date')}<input name="from_date" type="date" /></label><label>{t('To date')}<input name="to_date" type="date" /></label>
    <div className="action-row"><button className="secondary">{t('Apply filters')}</button><button className="secondary" type="button" onClick={() => { form.current.reset(); onChange(''); }}>{t('Clear')}</button></div>
  </form>;
}
