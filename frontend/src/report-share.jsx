import { useEffect, useRef, useState } from 'react';
import { api } from './api.js';
import { t } from './i18n.js';
import { Icon } from './ui.jsx';

export const WHATSAPP_URL = 'https://wa.me/?text=' + encodeURIComponent('I am sharing a medical report from BloomCare. Please see the attached file.');

export function ReportShareDialog({ report, onClose }) {
  const dialog = useRef(null);
  const [prepared, setPrepared] = useState(null);
  const [error, setError] = useState('');
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  useEffect(() => {
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog.current?.querySelector('button')?.focus();
    function keyboard(event) {
      if (event.key === 'Escape') onClose();
      if (event.key === 'Tab') {
        const controls = [...dialog.current.querySelectorAll('button:not(:disabled), a, input')];
        const first = controls[0], last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }
    window.addEventListener('keydown', keyboard);
    return () => { document.body.style.overflow = overflow; window.removeEventListener('keydown', keyboard); if (previous?.isConnected) previous.focus(); };
  }, [onClose]);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl;
    api(`/patients/me/reports/${report.id}/download`, { responseType: 'blob', signal: controller.signal })
      .then(blob => {
        if (controller.signal.aborted) return;
        const extension = { 'application/pdf': 'pdf', 'image/png': 'png', 'image/jpeg': 'jpg' }[report.media_type];
        if (!extension) throw new Error('This report file type cannot be shared.');
        const file = new File([blob], `BloomCare-report.${extension}`, { type: report.media_type });
        objectUrl = URL.createObjectURL(file);
        setPrepared({ file, url: objectUrl });
      }).catch(err => { if (!controller.signal.aborted) setError(err.message); });
    return () => { controller.abort(); if (objectUrl) setTimeout(() => URL.revokeObjectURL(objectUrl), 1000); };
  }, [report.id, report.media_type]);
  let nativeAvailable = false;
  try { nativeAvailable = Boolean(prepared && navigator.share && navigator.canShare?.({ files: [prepared.file] })); } catch { /* use download fallback */ }
  function downloadCopy() {
    if (!prepared || !consent) return;
    const link = document.createElement('a');
    link.href = prepared.url;
    link.download = prepared.file.name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setNotice('Report downloaded. Attach it in WhatsApp before sending.');
  }
  function openWhatsApp() {
    downloadCopy();
    window.open(WHATSAPP_URL, '_blank', 'noopener,noreferrer');
  }
  async function shareFile() {
    if (!prepared || !consent || busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await navigator.share({ files: [prepared.file], title: 'BloomCare medical report' });
      setNotice('Report handed to your selected app. Confirm the recipient and send it there.');
    } catch (err) {
      if (err.name === 'AbortError') setNotice('Sharing cancelled.');
      else setError('File sharing is unavailable here. Download the report and attach it in WhatsApp.');
    } finally { setBusy(false); }
  }
  return <div className="share-overlay"><section ref={dialog} className="card share-dialog" role="dialog" aria-modal="true" aria-labelledby="share-report-title"><div className="section-heading"><div><span className="eyebrow">{t('A COPY, SHARED BY YOU')}</span><h2 id="share-report-title">{t('Share via WhatsApp')}</h2></div><button className="icon-button" aria-label={t('Close share dialog').trim()} onClick={onClose}><Icon name="close" /></button></div>
    <p className="report-name"><Icon name="report" size={17} /> {report.title}</p>
    <p className="muted">{t(nativeAvailable ? 'Choose WhatsApp from your device’s share menu, then review the recipient before sending.' : 'Download the file, open WhatsApp and attach the downloaded report before sending.')}</p>
    <label><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />{t('I choose to share a copy of this report outside BloomCare.')}</label>
    <p className="muted text-sm">{t('A copy sent outside BloomCare cannot be recalled here.')}</p>
    {!prepared && !error && <p role="status">{t('Preparing your report…')}</p>}
    {error && <p className="error" role="alert">{t(error)}</p>}
    {notice && <p className="success" role="status">{t(notice)}</p>}
    <div className="share-actions">{nativeAvailable && <button disabled={!consent || busy} onClick={shareFile}><Icon name="chat" size={17} />{t('Choose WhatsApp')}</button>}
      <button className={nativeAvailable ? 'secondary' : ''} disabled={!prepared || !consent || busy} onClick={openWhatsApp}>{t('Download & open WhatsApp')}<Icon name="arrow" size={16} /></button>
      <button className="secondary" disabled={!prepared || !consent || busy} onClick={downloadCopy}>{t('Download only')}</button></div>
    {notice && <p><a href={WHATSAPP_URL} target="_blank" rel="noopener noreferrer">{t('Open WhatsApp')} ↗</a></p>}
  </section></div>;
}
