import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { AccountRecoveryPage } from './account-security.jsx';
import { setLanguage } from './i18n.js';

const token = 'T'.repeat(43);
const response = (data, status = 200, retry = null) => ({ ok: status < 400, status, json: async () => data, headers: { get: () => retry } });
function Address() { const location = useLocation(); return <span data-testid="address">{location.pathname + location.hash}</span>; }
function mount(mode, withToken = false, onReset) {
  render(<MemoryRouter initialEntries={['/account/' + mode + (withToken ? '#token=' + token : '')]}><AccountRecoveryPage mode={mode} onReset={onReset} /><Address /></MemoryRouter>);
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); setLanguage('en'); });

it('requests password recovery without disclosing an account or displaying a secret', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ message: 'If this address is eligible, an email will be sent. Check your inbox and spam folder and use the latest link.' }, 202)));
  mount('forgot');
  fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'patient@example.com' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send password-reset email' }));
  expect(await screen.findByRole('status')).toHaveTextContent('If this address is eligible');
  const [url, request] = fetch.mock.calls[0];
  expect(url).toBe('/api/auth/forgot-password');
  expect(JSON.parse(request.body)).toEqual({ email: 'patient@example.com' });
});

it('strips the verification token from history and requires a deliberate confirmation', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ message: 'Email verified. You can now sign in.' })));
  mount('verify', true);
  await waitFor(() => expect(screen.getByTestId('address')).toHaveTextContent('/account/verify'));
  expect(screen.getByTestId('address')).not.toHaveTextContent('#');
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Verify email address' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Email verified');
  expect(fetch.mock.calls[0][0]).toBe('/api/auth/verification/confirm');
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ token });
});

it('validates password confirmation, preserves the token in memory and clears session state after success', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ message: 'Password updated. Sign in again on each device.' })));
  const reset = vi.fn(); mount('reset', true, reset);
  fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'ReplacementPassword123!' } });
  fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'DifferentPassword123!' } });
  fireEvent.click(screen.getByRole('button', { name: 'Update password' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match');
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
  expect(screen.getByLabelText('New password')).toHaveAttribute('type', 'text');
  fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'ReplacementPassword123!' } });
  fireEvent.click(screen.getByRole('button', { name: 'Update password' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Sign in again');
  expect(reset).toHaveBeenCalledTimes(1);
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ token, password: 'ReplacementPassword123!' });
});

it('does not offer a reset submit form without a valid emailed link', () => {
  vi.stubGlobal('fetch', vi.fn()); mount('reset');
  expect(screen.queryByRole('button', { name: 'Update password' })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Request a new reset link' })).toHaveAttribute('href', '/account/forgot');
  expect(fetch).not.toHaveBeenCalled();
});

it('shows server rate-limit timing and offers resend after an invalid verification link', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ detail: 'Too many attempts. Please wait before trying again.' }, 429, '60')));
  mount('verify', true);
  fireEvent.click(screen.getByRole('button', { name: 'Verify email address' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('60 seconds');
  fireEvent.click(screen.getByRole('button', { name: 'Request verification email' }));
  expect(screen.getByLabelText('Email address')).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

it('renders the recovery form in Urdu', () => {
  setLanguage('ur'); mount('forgot');
  expect(screen.getByRole('heading')).toHaveTextContent('اپنا پاس ورڈ تبدیل کریں');
  expect(screen.getByRole('button')).toHaveTextContent('ای میل');
});
