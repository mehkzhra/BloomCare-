import { useEffect, useRef, useState } from 'react';
import { t } from './i18n.js';
import { ResourceStatus, useResource } from './resources.jsx';
import { Icon } from './ui.jsx';

export function DeviceCheck() {
  const preview = useRef(null), stream = useRef(null), generation = useRef(0);
  const [busy, setBusy] = useState(false), [ready, setReady] = useState(false), [error, setError] = useState('');
  const supported = window.isSecureContext !== false && navigator.mediaDevices?.getUserMedia && window.RTCPeerConnection;
  useEffect(() => () => { generation.current++; stream.current?.getTracks().forEach(track => track.stop()); }, []);
  function stop() {
    generation.current++;
    stream.current?.getTracks().forEach(track => track.stop());
    stream.current = null;
    if (preview.current) preview.current.srcObject = null;
    setReady(false); setBusy(false);
  }
  async function check() {
    const token = ++generation.current;
    setBusy(true); setError('');
    try {
      const media = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      if (generation.current !== token) { media.getTracks().forEach(track => track.stop()); return; }
      stream.current = media;
      if (preview.current) preview.current.srcObject = media;
      setReady(true);
    } catch (err) {
      if (generation.current === token) setError(t(err.name === 'NotAllowedError' ? 'Allow camera and microphone in your browser’s site settings, then try again.' : err.name === 'NotFoundError' ? 'Connect a camera and microphone, then try again.' : 'The camera or microphone could not open. Close other apps using them and try again.'));
    } finally { if (generation.current === token) setBusy(false); }
  }
  return <div className="stack"><p>{t('This preview stays on your device and starts no consultation. Stop the check when finished.')}</p>{!supported && <p className="error" role="alert">{t('Open BloomCare on localhost or HTTPS in a browser with camera, microphone and WebRTC support.')}</p>}<video className="device-preview" ref={preview} autoPlay playsInline muted hidden={!ready} aria-label={t('Your local camera preview')} />{ready && <p className="success" role="status">{t('Camera and microphone opened. A two-device call is still needed to check the network.')}</p>}{error && <p className="error" role="alert">{error}</p>}<div>{busy || ready ? <button className="secondary" onClick={stop}>{t(busy ? 'Cancel device check' : 'Stop device check')}</button> : <button className="secondary" disabled={!supported} onClick={check}>{t('Check camera & microphone')}</button>}</div></div>;
}
export function VideoReadiness() {
  const [open, setOpen] = useState(false);
  const resource = useResource('/consultation-readiness');
  return <section className="card video-readiness stack"><div className="panel-heading"><div><span className="eyebrow">{t('BEFORE YOUR CALL')}</span><h2><Icon name="video" size={19} /> {t('Prepare for your video call')}</h2></div>{resource.data && <span className={'service-badge ' + (resource.data.status === 'INVALID' ? 'service-error' : 'service-neutral')}>{t(resource.data.status === 'INVALID' ? 'Connection needs attention' : 'Check before joining')}</span>}</div><ResourceStatus resource={resource} />{resource.data && <p>{t(resource.data.status === 'INVALID' ? 'Video calling needs attention. Contact your care administrator; you can still use appointment messages.' : 'Allow your camera and microphone, then join your accepted appointment when the doctor starts the call.')}</p>}<details className="explanation" onToggle={event => setOpen(event.currentTarget.open)}><summary>{t('Check this device')}</summary>{open && <DeviceCheck />}</details></section>;
}
