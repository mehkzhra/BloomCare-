import { useRef, useState } from 'react';
import { api } from './api.js';
import { t } from './i18n.js';
import { ResourceStatus, useResource } from './pages.jsx';
import { Icon } from './ui.jsx';

const prompts = [
  ['Prepare for a visit', 'Help me prepare questions for my next appointment.'],
  ['Understand my readings', 'Explain how to read my blood pressure record.'],
  ['Organise my records', 'Help me organise the records for my doctor visit.'],
];

export function AssistantPage() {
  const status = useResource('/patients/me/assistant/status');
  const [question, setQuestion] = useState('');
  const [selectedContext, setSelectedContext] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyRevision, setHistoryRevision] = useState(0);
  const questionInput = useRef(null);
  const retry = useRef(null);

  async function ask(event) {
    event.preventDefault();
    if (busy || !status.data?.configured || !event.currentTarget.checkValidity()) return;
    const data = new FormData(event.currentTarget);
    const body = {
      question: data.get('question'),
      context: data.getAll('context'),
      consent: data.get('consent') === 'on',
      language: document.documentElement.lang === 'ur' ? 'ur' : 'en',
    };
    const key = JSON.stringify(body);
    if (!retry.current || retry.current.key !== key) {
      retry.current = { key, request_id: crypto.randomUUID() };
    }
    setBusy(true); setError('');
    try {
      const result = await api('/patients/me/assistant', {
        method: 'POST', body: { ...body, request_id: retry.current.request_id },
      });
      setReply({ question: body.question, answer: result.answer });
      retry.current = null;
      setHistoryRevision(value => value + 1);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  function choosePrompt(prompt) {
    setQuestion(t(prompt).trim());
    questionInput.current?.focus();
  }

  return <div className="stack assistant-page">
    <header className="page-intro"><div><span className="eyebrow">{t('A LITTLE MORE CLARITY')}</span><h1>{t('BloomCare assistant')}</h1><p className="muted">{t('A space for your questions, at your own pace.')}</p></div><span className="page-emblem"><Icon name="chat" size={29} /></span></header>
    {status.loading ? <p role="status">{t('Opening your assistant…')}</p> : <ResourceStatus resource={status} />}
    {status.data && !status.data.configured && <p className="banner">{t('The assistant is currently unavailable. Please contact your care administrator.')}</p>}
    <section className="card assistant-composer"><div className="section-heading"><div><span className="eyebrow">{t('LET’S TALK')}</span><h2>{t('What would you like to understand?')}</h2></div><span className="assistant-label"><Icon name="chat" size={14} />{t('Question support')}</span></div>
      <div className="prompt-ideas"><span>{t('Try asking')}</span><div>{prompts.map(([label, prompt]) => <button key={label} type="button" className="prompt-chip" onClick={() => choosePrompt(prompt)} disabled={busy}>{t(label)}<Icon name="arrow" size={13} /></button>)}</div></div>
      <form className="stack assistant-form" onSubmit={ask}>
        <div className="question-field"><div className="question-label"><label htmlFor="assistant-question">{t('Your question')}</label><span aria-hidden="true">{question.length}/1500</span></div><textarea ref={questionInput} id="assistant-question" name="question" required minLength={2} maxLength={1500} value={question} onChange={event => setQuestion(event.target.value)} disabled={busy} placeholder={t('Ask about your records or prepare for a care visit…').trim()} /></div>
        <details className="assistant-context"><summary><Icon name="plus" size={16} />{t('Optional record context')}<span>{selectedContext.length ? <>{t('Selected categories:')}{selectedContext.length}</> : t('You choose what to include')}</span></summary><fieldset disabled={busy}><legend className="sr-only">{t('Optional record context')}</legend>{['observations', 'symptoms', 'medications'].map(scope => <label key={scope}><input type="checkbox" name="context" value={scope} checked={selectedContext.includes(scope)} onChange={event => setSelectedContext(previous => event.target.checked ? [...previous, scope] : previous.filter(value => value !== scope))} />{t(scope)}</label>)}</fieldset></details>
        <div className="assistant-consent"><label className="check-label"><input type="checkbox" name="consent" required disabled={busy} />{t('I agree to send my question and selected records to Groq.')}</label><p>{t('No records are sent unless selected. The assistant explains records and cannot diagnose or change treatment.')}</p></div>
        <div className="assistant-submit"><span><Icon name="shield" size={15} />{t('Your context. Your choice.')}</span><button disabled={busy || !status.data?.configured}>{busy ? t('Asking…') : t('Ask assistant')}<Icon name="arrow" size={16} /></button></div>
      </form>
    </section>
    {busy && <p className="assistant-working" role="status"><span className="working-dot" />{t('The assistant is preparing your reply.')}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {reply && <section className="card assistant-answer" aria-live="polite"><div className="section-heading"><div><span className="eyebrow">{t('A LITTLE MORE CLARITY')}</span><h2>{t('Assistant reply')}</h2></div><span className="feature-icon"><Icon name="chat" /></span></div><div className="answered-question"><span>{t('Your question')}</span><p>{reply.question}</p></div><p className="note-body">{reply.answer}</p></section>}
    <section className={'card assistant-history' + (historyOpen ? ' is-open' : '')} aria-label={t('Question history').trim()}>
      <button type="button" className="history-toggle" aria-label={t('Question history').trim()} aria-expanded={historyOpen} aria-controls="assistant-history-content" onClick={() => setHistoryOpen(open => !open)}><span className="history-icon"><Icon name="clock" size={21} /></span><span className="history-toggle-copy"><strong>{t('Question history')}</strong><small>{t('Your earlier questions, when you need them.')}</small></span><span className="history-toggle-action">{historyOpen ? t('Close history') : t('Open history')}<Icon name="chevron" size={16} /></span></button>
      <div id="assistant-history-content" hidden={!historyOpen}>{historyOpen && <AssistantHistory key={historyRevision} />}</div>
    </section>
  </div>;
}

function AssistantHistory() {
  const history = useResource('/patients/me/assistant/history');
  const [search, setSearch] = useState('');
  const [opened, setOpened] = useState(null);
  const rows = Array.isArray(history.data) ? history.data : [];
  const query = search.trim().toLocaleLowerCase();
  const filtered = rows.filter(row => `${row.question} ${row.answer}`.toLocaleLowerCase().includes(query));

  return <div className="history-content stack">
    {history.loading ? <p role="status">{t('Loading your questions…')}</p> : <ResourceStatus resource={history} />}
    {!history.loading && !history.error && <>
      <div className="history-toolbar"><label>{t('Search your questions')}<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder={t('Find a word in a question or reply').trim()} /></label><button type="button" className="secondary" onClick={history.retry}>{t('Refresh history')}</button></div>
      {rows.length === 50 && <p className="history-limit">{t('Showing the latest 50 saved questions.')}</p>}
      {rows.length === 0 ? <div className="history-empty"><Icon name="chat" size={25} /><p>{t('Your saved conversations will appear here.')}</p></div> : filtered.length === 0 ? <p className="muted">{t('No saved questions match your search.')}</p> : <div className="history-list">{filtered.map(row => {
        const expanded = opened === row.id;
        const date = row.created_at ? new Date(row.created_at) : null;
        return <article className={'history-item' + (expanded ? ' is-open' : '')} key={row.id}>
          <h3><button type="button" aria-expanded={expanded} aria-controls={`assistant-answer-${row.id}`} onClick={() => setOpened(current => current === row.id ? null : row.id)}><span>{date && !Number.isNaN(date.getTime()) && <time dateTime={row.created_at}>{date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}</time>}<span className="history-question">{row.question}</span></span><Icon name="chevron" size={16} /></button></h3>
          <div id={`assistant-answer-${row.id}`} hidden={!expanded}>{expanded && <div className="history-answer"><span>{t('Assistant reply')}</span><p className="note-body">{row.answer}</p></div>}</div>
        </article>;
      })}</div>}
    </>}
  </div>;
}
