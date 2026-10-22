import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import App from './App.jsx';
import { FamilyPage, RemindersPage, AssistantPage } from './extended.jsx';
import { ConsultationPage } from './consultation.jsx';
import { setLanguage } from './i18n.js';

const reply = data => ({ ok: true, status: 200, json: async () => data });
afterEach(() => { cleanup(); setLanguage('en'); localStorage.clear(); vi.unstubAllGlobals(); });
it('switches the account interface to Urdu and sets RTL', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 401, json: async () => ({}) })));
  render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText('Language'), { target: { value: 'ur' } });
  expect(await screen.findByRole('heading', { name: 'دوبارہ خوش آمدید' })).toBeInTheDocument();
  expect(document.documentElement.dir).toBe('rtl');
  expect(screen.getByLabelText('پاس ورڈ')).toHaveAttribute('type', 'password');
});
it('creates a consented invitation with only selected scopes', async () => {
  let body;
  vi.stubGlobal('fetch', vi.fn(async (url, opt = {}) => {
    if (opt.method === 'POST') { body = JSON.parse(opt.body); return reply({ invitation_code: 'demo-code-at-least-thirty-characters' }); }
    return reply({ owned: [], received: [] });
  }));
  render(<FamilyPage />);
  fireEvent.change(screen.getByLabelText('Family member email'), { target: { value: 'reader@example.com' } });
  fireEvent.click(screen.getByRole('checkbox', { name: 'symptoms' }));
  fireEvent.click(screen.getByRole('checkbox', { name: /I consent/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Create invitation' }));
  expect(await screen.findByLabelText('Invitation code')).toHaveValue('demo-code-at-least-thirty-characters');
  expect(body.scopes).toEqual(['symptoms']); expect(body.consent).toBe(true);
});
it('schedules an explicit medication reminder with timezone', async () => {
  let body;
  vi.stubGlobal('fetch', vi.fn(async (url, opt = {}) => {
    if (opt.method === 'POST') body = JSON.parse(opt.body);
    return reply(url.includes('medications') ? [{ id: 'm', name: 'Demo Medicine', active: true }] : []);
  }));
  render(<RemindersPage />);
  await screen.findByRole('option', { name: 'Demo Medicine' });
  fireEvent.change(screen.getByLabelText('Medication'), { target: { value: 'm' } });
  fireEvent.change(screen.getByLabelText('First reminder time'), { target: { value: '2026-10-13T10:00' } });
  fireEvent.click(screen.getByRole('button', { name: 'Schedule reminder' }));
  await waitFor(() => expect(body).toBeDefined());
  expect(body.due_at.endsWith('Z')).toBe(true); expect(body.period_hours).toBe(0);
});
it('does not enable the assistant without configured provider credentials', async () => {
  vi.stubGlobal('fetch', vi.fn(async url => reply(url.endsWith('/status') ? { configured: false } : [])));
  render(<AssistantPage />);
  expect(await screen.findByText(/The assistant is currently unavailable/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Ask assistant' })).toBeDisabled();
});
it('stops video tracks when ending a mocked consultation', async () => {
  const stop = vi.fn(); const close = vi.fn();
  const original = navigator.mediaDevices;
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn(async () => ({ getTracks: () => [{ stop }] })) } });
  vi.stubGlobal('RTCPeerConnection', class {
    constructor() { this.close = close; }
    addTrack() {} async createOffer() { return { type: 'offer', sdp: 'demo' }; }
    async setLocalDescription() {} async addIceCandidate() {}
  });
  vi.stubGlobal('fetch', vi.fn(async url => reply(url.includes('/signals?') ? [] : { id: 'call', ice_servers: [] })));
  try {
    render(<MemoryRouter initialEntries={['/a']}><Routes><Route path="/:appointmentId" element={<ConsultationPage role="doctor" />} /></Routes></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Start consultation' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'End consultation' })).not.toBeDisabled());
    fireEvent.click(screen.getByRole('button', { name: 'End consultation' }));
    expect(stop).toHaveBeenCalled(); expect(close).toHaveBeenCalled();
  } finally { Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: original }); }
});
