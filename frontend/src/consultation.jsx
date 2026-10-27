import { t } from "./i18n.js";
import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from './api.js';
export function ConsultationPage({
  role
}) {
  const {
    appointmentId
  } = useParams();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [joined, setJoined] = useState(false);
  const [status, setStatus] = useState('Ready');
  const runtime = useRef(null);
  const localVideo = useRef(null);
  const remoteVideo = useRef(null);
  function stopLocal() {
    const state = runtime.current;
    runtime.current = null;
    if (!state) return;
    state.closed = true;
    clearTimeout(state.timer);
    state.peer.close();
    state.stream.getTracks().forEach(track => track.stop());
  }
  useEffect(() => () => {
    const state = runtime.current;
    if (state) {
      state.closed = true;
      clearTimeout(state.timer);
      state.peer.close();
      state.stream.getTracks().forEach(track => track.stop());
      runtime.current = null;
    }
  }, [appointmentId]);
  async function join() {
    setError('');
    setBusy(true);
    let stream;
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.RTCPeerConnection) throw new Error('Video requires a supported browser on localhost or HTTPS.');
      const current = await api(`/appointments/${appointmentId}/consultation`);
      let call = current;
      if (role !== 'doctor' && !call.id) throw new Error('Wait for the doctor to start the consultation.');
      stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      if (role === 'doctor') {
        if (current.id) await api(`/consultations/${current.id}/end`, {
          method: 'POST'
        });
        call = await api(`/appointments/${appointmentId}/consultation`, {
          method: 'POST'
        });
      }
      const peer = new RTCPeerConnection({
        iceServers: call.ice_servers
      });
      const state = {
        id: call.id,
        peer,
        stream,
        after: 0,
        closed: false,
        candidates: [],
        pollFailures: 0
      };
      runtime.current = state;
      localVideo.current.srcObject = stream;
      stream.getTracks().forEach(track => peer.addTrack(track, stream));
      peer.ontrack = event => {
        if (!state.closed) remoteVideo.current.srcObject = event.streams[0];
      };
      peer.onconnectionstatechange = () => {
        if (!state.closed) {
          setStatus(peer.connectionState);
          if (peer.connectionState === 'failed') setError(t('The video could not connect. Check your internet connection and try joining again. Contact support if the problem continues.'));
        }
      };
      const signal = (kind, payload) => api(`/consultations/${state.id}/signals`, {
        method: 'POST',
        body: {
          kind,
          payload
        }
      });
      peer.onicecandidate = event => {
        if (event.candidate && !state.closed) signal('candidate', event.candidate.toJSON()).catch(err => setError(err.message));
      };
      if (role === 'doctor') {
        const offer = await peer.createOffer();
        await peer.setLocalDescription(offer);
        await signal('offer', offer);
      }
      async function poll() {
        if (state.closed) return;
        let items;
        try {
          items = await api(`/consultations/${state.id}/signals?after=${state.after}`);
        } catch (err) {
          if (state.closed) return;
          const transient = [429, 502, 503, 504].includes(err.status)
            || err.code === 'REQUEST_TIMEOUT' || err instanceof TypeError;
          state.pollFailures += 1;
          if (transient && state.pollFailures <= 4 && !(err.retryAfterSeconds > 60)) {
            setError(t('Connection interrupted. Reconnecting to the consultation…'));
            state.timer = setTimeout(poll, Math.max(
              3000 * 2 ** (state.pollFailures - 1), (err.retryAfterSeconds || 0) * 1000
            ));
            return;
          }
          setError(err.message);
          stopLocal();
          setJoined(false);
          return;
        }
        if (state.closed) return;
        if (state.pollFailures) setError('');
        state.pollFailures = 0;
        try {
          for (const item of items) {
            if (state.closed) return;
            if (item.kind === 'offer' && role === 'patient') {
              await peer.setRemoteDescription(item.payload);
              const answer = await peer.createAnswer();
              await peer.setLocalDescription(answer);
              await signal('answer', answer);
            } else if (item.kind === 'answer' && role === 'doctor') await peer.setRemoteDescription(item.payload);else if (item.kind === 'candidate') state.candidates.push(item.payload);
            if (peer.remoteDescription) {
              while (state.candidates.length) await peer.addIceCandidate(state.candidates.shift());
            }
            state.after = item.id;
          }
        } catch (err) {
          if (state.closed) return;
          setError(err.message);
          stopLocal();
          setJoined(false);
          return;
        }
        const configuredDelay = Number(import.meta.env.VITE_CALL_SIGNAL_POLL_MS);
        const delay = Number.isFinite(configuredDelay) && configuredDelay >= 1200
          ? Math.min(configuredDelay, 10000) : 3000;
        state.timer = setTimeout(poll, delay);
      }
      setJoined(true);
      setStatus('Waiting for participant');
      poll();
    } catch (err) {
      stream?.getTracks().forEach(track => track.stop());
      stopLocal();
      setError(err.name === 'NotAllowedError' ? t('Allow camera and microphone in your browser’s site settings, then try again.') : err.name === 'NotFoundError' ? t('Connect a camera and microphone, then try again.') : err.message);
      setJoined(false);
    } finally {
      setBusy(false);
    }
  }
  async function end() {
    const id = runtime.current?.id;
    stopLocal();
    setJoined(false);
    setStatus('Ended');
    if (id) {
      try {
        await api(`/consultations/${id}/end`, {
          method: 'POST'
        });
      } catch (err) {
        setError(err.message);
      }
    }
  }
  return <div className="stack"><h1>{t("Video consultation")}</h1><Link to={`/${role}/appointments`}>{t("Back to appointments")}</Link>
    <p className="banner">{t("Only the confirmed participants of an accepted, unexpired appointment can connect. Camera and microphone permission is requested when you join. No audio or video is recorded.")}</p>
    <p>{status}</p>{error && <p className="error" role="alert">{error}</p>}
    <div className="two-cols"><section className="card"><h2>{t("Your video")}</h2><video ref={localVideo} autoPlay playsInline muted className="call-video" /></section>
      <section className="card"><h2>{t("Remote video")}</h2><video ref={remoteVideo} autoPlay playsInline className="call-video" /></section></div>
    <div className="nav"><button disabled={busy || joined} onClick={join}>{role === 'doctor' ? t("Start consultation") : t("Join consultation")}</button>
      <button disabled={!joined} onClick={end}>{t("End consultation")}</button></div>
    <p className="muted">{t("Keep this page open during your consultation. Use a stable internet connection and allow camera and microphone access.")}</p>
  </div>;
}
