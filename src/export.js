// export.js — запись готового клипа прямо в браузере: canvas + звук -> mp4/webm.
import { clamp } from './util.js';

export function pickMime() {
  const list = [
    'video/mp4;codecs=avc1.42E01E,mp4a.40.2',
    'video/mp4;codecs=avc1,mp4a',
    'video/mp4',
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm',
  ];
  for (const m of list) { try { if (window.MediaRecorder && MediaRecorder.isTypeSupported(m)) return m; } catch (e) {} }
  return '';
}

// renderFrame(T) рисует кадр клипа на времени T; клип играет в реальном времени со звуком.
export async function recordClip({ canvas, audioCtx, buffer, duration, renderFrame, fps = 30, offset = .1, onProgress }) {
  const mime = pickMime();
  if (!mime) throw new Error('Этот браузер не умеет записывать видео (нет MediaRecorder)');
  const stream = canvas.captureStream(fps);
  let src = null, dst = null;
  if (buffer) {
    src = audioCtx.createBufferSource(); src.buffer = buffer;
    dst = audioCtx.createMediaStreamDestination();
    const gain = audioCtx.createGain(); gain.gain.value = 1;
    src.connect(gain); gain.connect(dst); gain.connect(audioCtx.destination);
    dst.stream.getAudioTracks().forEach(t => stream.addTrack(t));
  }
  const chunks = [];
  const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 12e6, audioBitsPerSecond: 192e3 });
  rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
  const stopped = new Promise(res => { rec.onstop = res; });
  await audioCtx.resume();
  const t0 = audioCtx.currentTime + offset;
  if (src) src.start(t0);
  rec.start(200);
  renderFrame(0);
  await new Promise(resolve => {
    const loop = () => {
      const T = clamp(audioCtx.currentTime - t0, 0, duration);
      renderFrame(T);
      if (onProgress) onProgress(T / duration);
      if (T >= duration) return resolve();
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  });
  await new Promise(r => setTimeout(r, 260));
  rec.stop();
  if (src) { try { src.stop(); } catch (e) {} }
  await stopped;
  const base = mime.split(';')[0];
  return { blob: new Blob(chunks, { type: base }), mime: base, ext: base.includes('mp4') ? 'mp4' : 'webm' };
}

export function download(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = name; a.rel = 'noopener';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 20000);
  return url;
}
