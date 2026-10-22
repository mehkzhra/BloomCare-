import { useSyncExternalStore } from 'react';
import ur from './urdu.json';
let language = 'en';
try { language = localStorage.getItem('bloomcare-language') === 'ur' ? 'ur' : 'en'; } catch { /* private browser mode */ }
const listeners = new Set();
export function t(text) {
  if (typeof text !== 'string') return text;
  const value = language === 'ur' ? (ur[text.trim()] || text.trim()) : text.trim();
  return ` ${value} `;
}
export function setLanguage(next) {
  language = next === 'ur' ? 'ur' : 'en';
  try { localStorage.setItem('bloomcare-language', language); } catch { /* private browser mode */ }
  listeners.forEach(fn => fn());
}
export function useLanguage() {
  return useSyncExternalStore(fn => { listeners.add(fn); return () => listeners.delete(fn); }, () => language, () => 'en');
}
