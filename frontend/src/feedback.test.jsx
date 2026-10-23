import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AssessmentRemoval, RemovedAssessments } from './assessment-removal.jsx';
import { InformationPage, PortalNavigation } from './ui.jsx';
import { PEScreeningStage } from './pe-screening.jsx';
import { ServiceSettingsPage } from './service-configuration.jsx';
import { VideoReadiness } from './video-readiness.jsx';
import { setLanguage } from './i18n.js';

const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
const mount = node => render(<MemoryRouter>{node}</MemoryRouter>);
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); setLanguage('en'); });

it.each([
  ['patient', 'Your records, your choices.', 'Manage family access', '/patient/family'],
  ['doctor', 'Patient trust, clear boundaries.', 'Open shared assessments', '/doctor/cases'],
  ['admin', 'Access you can account for.', 'Review connected services', '/admin/services'],
])('shows relevant privacy responsibilities and controls for the %s role', (role, heading, action, target) => {
  mount(<InformationPage kind="privacy" role={role} />);
  expect(screen.getByRole('heading', { level: 1, name: heading })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: action })).toHaveAttribute('href', target);
  if (role !== 'patient') expect(screen.queryByRole('link', { name: 'Manage family access' })).not.toBeInTheDocument();
});
it('shows public privacy information without pretending there is a patient session', () => {
  mount(<InformationPage kind="privacy" />);
  expect(screen.getByRole('link', { name: 'Sign in to your account' })).toHaveAttribute('href', '/login');
  expect(screen.queryByRole('link', { name: 'Manage assessments' })).not.toBeInTheDocument();
});
it('renders the role-specific privacy page in Urdu', () => {
  setLanguage('ur'); mount(<InformationPage kind="privacy" role="doctor" />);
  expect(screen.getByRole('heading', { level: 1, name: 'مریض کا اعتماد، واضح حدود۔' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'شیئر کیے گئے جائزے کھولیں' })).toHaveAttribute('href', '/doctor/cases');
});
it('uses doctor-specific sharing copy in the sidebar', () => {
  mount(<PortalNavigation role="doctor" />);
  expect(screen.getByText('Access follows each patient’s active sharing choices.')).toBeInTheDocument();
  expect(screen.queryByText('You decide which records to share with your care team.')).not.toBeInTheDocument();
});
it('requires a deletion reason, can cancel with Escape and does not submit on opening', () => {
  vi.stubGlobal('fetch', vi.fn()); mount(<AssessmentRemoval assessmentId="a1" />);
  const trigger = screen.getByRole('button', { name: 'Delete assessment' });
  trigger.focus(); fireEvent.click(trigger);
  expect(screen.getByRole('textbox', { name: 'Reason for deletion' })).toHaveFocus();
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.keyDown(screen.getByRole('alertdialog'), { key: 'Escape' });
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});
it('deletes with explicit confirmation and the entered reason, then reports success', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ id: 'a1', removed_at: '2026-10-17T00:00:00Z' })));
  const removed = vi.fn(); mount(<AssessmentRemoval assessmentId="a1" onRemoved={removed} />);
  fireEvent.click(screen.getByRole('button', { name: 'Delete assessment' }));
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Blood pressure entered incorrectly' } });
  fireEvent.submit(screen.getByRole('alertdialog'));
  expect(await screen.findByRole('status')).toHaveTextContent('Assessment deleted from active history.');
  expect(removed).toHaveBeenCalledTimes(1);
  const [url, options] = fetch.mock.calls[0];
  expect(url).toBe('/api/patients/me/assessments/a1'); expect(options.method).toBe('DELETE');
  expect(JSON.parse(options.body)).toEqual({ reason: 'Blood pressure entered incorrectly' });
});
it('keeps a failed deletion reviewable and makes no success claim', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ detail: 'Database busy; retry' }, 503)));
  mount(<AssessmentRemoval assessmentId="a1" />);
  fireEvent.click(screen.getByRole('button', { name: 'Delete assessment' }));
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Incorrect temperature entry' } });
  fireEvent.submit(screen.getByRole('alertdialog'));
  expect(await screen.findByRole('alert')).toHaveTextContent('Database busy; retry');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  expect(screen.getByRole('textbox')).toHaveValue('Incorrect temperature entry');
});
it('loads the deletion log only when opened and includes no active result cards', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response([{ id: 'a1', reason: 'Incorrect reading', removed_at: '2026-10-17T00:00:00Z', created_at: '2026-10-16T00:00:00Z' }])));
  mount(<RemovedAssessments version={1} />);
  expect(fetch).not.toHaveBeenCalled(); fireEvent.click(screen.getByText('Deleted assessment log'));
  expect(await screen.findByText('Incorrect reading')).toBeInTheDocument();
  expect(screen.queryByText('Run assessment')).not.toBeInTheDocument();
});
it('explains unsupported PE values without claiming a diagnosis or blaming missing inputs', () => {
  mount(<PEScreeningStage assessment={{ id: 'a1', health_record_id: 'r1', observations: { systolic_mmhg: 150 }, pe_status: 'OUTSIDE_COVERAGE', pe_input_issues: [{ name: 'systolic_mmhg', label: 'Systolic blood pressure', unit: 'mmHg', value: 150, minimum: 90, maximum: 130 }] }} capabilities={{ pe_model_ready: true }} viewerRole="doctor" />);
  expect(screen.getByText('Doctor review needed')).toBeInTheDocument();
  expect(screen.getByText('150 mmHg')).toBeInTheDocument();
  expect(screen.getByText('90–130 mmHg')).toBeInTheDocument();
  expect(screen.getByText('No PE category was generated. This message does not confirm or rule out pre-eclampsia.')).toBeInTheDocument();
  expect(screen.queryByText('The patient has not completed the additional PE measurements.')).not.toBeInTheDocument();
});
it('shows operational availability while keeping setup commands and variables out of admin pages', async () => {
  const writeText = vi.fn(async () => {}); vi.stubGlobal('navigator', { clipboard: { writeText } });
  vi.stubGlobal('fetch', vi.fn(async () => response({ services: { whatsapp: { status: 'NOT_CONFIGURED', label: 'Automatic alerts off', summary: 'Manual PDF sharing is available.', missing: ['TWILIO_AUTH_TOKEN'], command: 'scripts\\configure-whatsapp.cmd' } } })));
  mount(<ServiceSettingsPage />);
  expect(await screen.findByText('Automatic alerts off')).toBeInTheDocument();
  expect(screen.queryByText('TWILIO_AUTH_TOKEN')).not.toBeInTheDocument();
  expect(screen.queryByText(/configure-whatsapp/)).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Copy command' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByText('How to check this service'));
  expect(screen.getByText(/Manual sharing is available/)).toBeInTheDocument();
  expect(writeText).not.toHaveBeenCalled();
});
it('checks local devices only on demand and releases all tracks when closed', async () => {
  const stop = vi.fn(); const getUserMedia = vi.fn(async () => ({ getTracks: () => [{ stop }] }));
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } });
  vi.stubGlobal('RTCPeerConnection', function Peer() {});
  vi.stubGlobal('fetch', vi.fn(async () => response({ status: 'DIRECT_ONLY', label: 'Direct connection mode', summary: 'Calls can use direct connections.' })));
  const view = mount(<VideoReadiness />);
  expect(await screen.findByText('Check before joining')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Check this device'));
  const button = await screen.findByRole('button', { name: 'Check camera & microphone' });
  expect(getUserMedia).not.toHaveBeenCalled(); fireEvent.click(button);
  expect(await screen.findByRole('status')).toHaveTextContent('Camera and microphone opened.');
  view.unmount(); expect(stop).toHaveBeenCalledTimes(1);
});
it('releases a late camera stream after a pending device check was cancelled', async () => {
  const stop = vi.fn(); let grant;
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia: () => new Promise(resolve => { grant = resolve; }) } });
  vi.stubGlobal('RTCPeerConnection', function Peer() {});
  vi.stubGlobal('fetch', vi.fn(async () => response({ status: 'DIRECT_ONLY', label: 'Direct connection mode', summary: 'Calls can use direct connections.' })));
  mount(<VideoReadiness />); await screen.findByText('Check before joining');
  fireEvent.click(screen.getByText('Check this device'));
  fireEvent.click(await screen.findByRole('button', { name: 'Check camera & microphone' }));
  fireEvent.click(screen.getByRole('button', { name: 'Cancel device check' }));
  grant({ getTracks: () => [{ stop }] });
  await waitFor(() => expect(stop).toHaveBeenCalledTimes(1));
  expect(within(screen.getByText('Check this device').parentElement).queryByText(/Camera and microphone opened/)).not.toBeInTheDocument();
});
