import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { AssistantPage } from './assistant.jsx';
import { setLanguage } from './i18n.js';

const rows = [
  { id: 'q-1', question: 'How can I prepare for my appointment?', answer: 'First saved answer.\nThis is the complete final line.', created_at: '2026-10-15T09:00:00Z' },
  { id: 'q-2', question: 'Can you explain my records?', answer: 'Second saved answer with a unique phrase.', created_at: '2026-10-14T09:00:00Z' },
];
const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
let turns;
let failure;
beforeEach(() => {
  turns = [...rows]; failure = false;
  document.documentElement.lang = 'en'; document.documentElement.dir = 'ltr';
  vi.stubGlobal('fetch', vi.fn(async (url, options = {}) => {
    if (url.endsWith('/status')) return response({ configured: true });
    if (url.endsWith('/history')) return response(turns);
    if (options.method === 'POST') {
      if (failure) return response({ detail: 'Assistant temporarily unavailable.' }, 503);
      const body = JSON.parse(options.body);
      const turn = { id: 'new-turn', question: body.question, answer: 'A freshly saved answer.', created_at: '2026-10-15T10:00:00Z' };
      turns = [turn, ...turns]; return response(turn);
    }
    throw new Error('Unexpected test endpoint: ' + url);
  }));
});
afterEach(() => {
  cleanup(); setLanguage('en'); vi.unstubAllGlobals();
  document.documentElement.lang = 'en'; document.documentElement.dir = 'ltr';
});

function historyRequests() { return fetch.mock.calls.filter(([url]) => url.endsWith('/history')); }
function posts() { return fetch.mock.calls.filter(([, options]) => options.method === 'POST'); }
async function start() {
  render(<AssistantPage />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Ask assistant' })).toBeEnabled());
}
async function openHistory() {
  fireEvent.click(screen.getByRole('button', { name: 'Question history' }));
  await screen.findByRole('button', { name: /How can I prepare/ });
}
function compose() {
  fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'Help me prepare for my care visit.' } });
  fireEvent.click(screen.getByRole('checkbox', { name: /I agree to send/ }));
}

it('keeps history closed and does not fetch old answers until requested', async () => {
  await start();
  const toggle = screen.getByRole('button', { name: 'Question history' });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  expect(historyRequests()).toHaveLength(0);
  expect(screen.queryByText(rows[0].question)).not.toBeInTheDocument();
  await openHistory();
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  expect(historyRequests()).toHaveLength(1);
  expect(screen.queryByText(/complete final line/)).not.toBeInTheDocument();
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByText(rows[0].question)).not.toBeInTheDocument();
});

it('expands the complete reply for one selected question at a time', async () => {
  await start(); await openHistory();
  const first = screen.getByRole('button', { name: /How can I prepare/ });
  fireEvent.click(first);
  expect(first).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByText(/complete final line/).textContent).toBe(rows[0].answer);
  fireEvent.click(screen.getByRole('button', { name: /Can you explain my records/ }));
  expect(first).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByText(/complete final line/)).not.toBeInTheDocument();
  expect(screen.getByText(rows[1].answer)).toBeInTheDocument();
});

it('searches questions and full saved replies without sending a search request', async () => {
  await start(); await openHistory();
  fireEvent.change(screen.getByLabelText('Search your questions'), { target: { value: 'unique phrase' } });
  expect(screen.queryByRole('button', { name: /How can I prepare/ })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Can you explain my records/ })).toBeInTheDocument();
  expect(screen.queryByText(rows[1].answer)).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Search your questions'), { target: { value: 'no matching term' } });
  expect(screen.getByText('No saved questions match your search.')).toBeInTheDocument();
  expect(historyRequests()).toHaveLength(1);
});

it('fills a suggested question and focuses the draft without sending anything', async () => {
  await start();
  fireEvent.click(screen.getByRole('button', { name: 'Prepare for a visit' }));
  expect(screen.getByLabelText('Your question')).toHaveValue('Help me prepare questions for my next appointment.');
  expect(screen.getByLabelText('Your question')).toHaveFocus();
  expect(posts()).toHaveLength(0);
  expect(screen.getByRole('checkbox', { name: /I agree to send/ })).not.toBeChecked();
});

it('requires consent, sends only selected context and leaves closed history unloaded after saving', async () => {
  await start();
  fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'Help with my records.' } });
  fireEvent.click(screen.getByRole('button', { name: 'Ask assistant' }));
  expect(posts()).toHaveLength(0);
  fireEvent.click(screen.getByText('Optional record context', { selector: 'summary' }));
  fireEvent.click(screen.getByRole('checkbox', { name: 'observations' }));
  fireEvent.click(screen.getByText('Optional record context', { selector: 'summary' }));
  expect(screen.getByText('Optional record context', { selector: 'summary' })).toHaveTextContent('Selected categories: 1');
  fireEvent.click(screen.getByRole('checkbox', { name: /I agree to send/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Ask assistant' }));
  expect(await screen.findByText('A freshly saved answer.')).toBeInTheDocument();
  const body = JSON.parse(posts()[0][1].body);
  expect(body).toMatchObject({ question: 'Help with my records.', context: ['observations'], consent: true, language: 'en' });
  expect(body.request_id).toMatch(/^[0-9a-f-]{36}$/);
  expect(historyRequests()).toHaveLength(0);
});

it('refreshes an already open history after a successful question', async () => {
  await start(); await openHistory(); compose();
  fireEvent.click(screen.getByRole('button', { name: 'Ask assistant' }));
  const history = screen.getByRole('region', { name: 'Question history' });
  expect(await within(history).findByRole('button', { name: /Help me prepare for my care visit/ })).toBeInTheDocument();
  expect(historyRequests()).toHaveLength(2);
});

it('reuses the request ID for an unchanged retry and creates a new one for changed context', async () => {
  failure = true; await start(); compose();
  fireEvent.click(screen.getByRole('button', { name: 'Ask assistant' }));
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Ask assistant' }));
  await waitFor(() => expect(posts()).toHaveLength(2));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Ask assistant' })).toBeEnabled());
  fireEvent.click(screen.getByText('Optional record context', { selector: 'summary' }));
  fireEvent.click(screen.getByRole('checkbox', { name: 'symptoms' }));
  fireEvent.click(screen.getByRole('button', { name: 'Ask assistant' }));
  await waitFor(() => expect(posts()).toHaveLength(3));
  const bodies = posts().map(([, options]) => JSON.parse(options.body));
  expect(bodies[0].request_id).toBe(bodies[1].request_id);
  expect(bodies[2].request_id).not.toBe(bodies[1].request_id);
  expect(screen.queryByText('A freshly saved answer.')).not.toBeInTheDocument();
});

it('shows a recoverable history failure without removing the draft', async () => {
  const normal = fetch.getMockImplementation();
  fetch.mockImplementation((url, options) => url.endsWith('/history')
    ? Promise.resolve(response({ detail: 'History temporarily unavailable.' }, 503)) : normal(url, options));
  await start(); compose();
  fireEvent.click(screen.getByRole('button', { name: 'Question history' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('History temporarily unavailable.');
  fetch.mockImplementation(normal);
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByRole('button', { name: /How can I prepare/ })).toBeInTheDocument();
  expect(screen.getByLabelText('Your question')).toHaveValue('Help me prepare for my care visit.');
});

it('shows a useful empty state after opening history for a new account', async () => {
  turns = []; await start();
  fireEvent.click(screen.getByRole('button', { name: 'Question history' }));
  expect(await screen.findByText('Your saved conversations will appear here.')).toBeInTheDocument();
  expect(posts()).toHaveLength(0);
});

it('cancels a history read when the user closes the panel', async () => {
  const normal = fetch.getMockImplementation();
  let complete; let signal;
  fetch.mockImplementation((url, options) => url.endsWith('/history') ? new Promise(resolve => {
    complete = resolve; signal = options.signal;
  }) : normal(url, options));
  await start();
  const toggle = screen.getByRole('button', { name: 'Question history' });
  fireEvent.click(toggle);
  await waitFor(() => expect(signal).toBeDefined());
  fireEvent.click(toggle);
  expect(signal.aborted).toBe(true);
  await act(async () => { complete(response(rows)); });
  expect(screen.queryByText(rows[0].question)).not.toBeInTheDocument();
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
});

it('fills a translated suggested question without sending it in Urdu mode', async () => {
  setLanguage('ur'); document.documentElement.lang = 'ur'; document.documentElement.dir = 'rtl';
  render(<AssistantPage />);
  fireEvent.click(screen.getByRole('button', { name: 'معائنے کی تیاری' }));
  expect(screen.getByRole('textbox')).toHaveValue('اگلی اپائنٹمنٹ کے لیے سوالات تیار کرنے میں میری مدد کریں۔');
  expect(posts()).toHaveLength(0);
  expect(screen.getByRole('button', { name: 'سوالات کی تاریخ' })).toHaveAttribute('aria-expanded', 'false');
});
