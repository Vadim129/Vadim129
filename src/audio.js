// audio.js — слушаем трек: биты, удары, энергия. Всё на устройстве, без интернета и без ИИ.
import { clamp, lerp, ss } from './util.js';

export function analyzeBuffer(buffer, o = {}) {
  const sr = buffer.sampleRate, len = buffer.length;
  const ch = buffer.numberOfChannels;
  const mono = new Float32Array(len);
  for (let c = 0; c < ch; c++) {
    const d = buffer.getChannelData(c);
    for (let i = 0; i < len; i++) mono[i] += d[i] / ch;
  }
  const win = 1024, hop = 512;
  const frames = Math.max(1, Math.floor((len - win) / hop));
  const fft = new FFT(win);
  const re = new Float32Array(win), im = new Float32Array(win);
  const nBins = win / 2;
  let prev = new Float32Array(nBins);
  const flux = new Float32Array(frames);
  const rms = new Float32Array(frames);
  for (let f = 0; f < frames; f++) {
    const off = f * hop;
    for (let i = 0; i < win; i++) {
      const w = .5 - .5 * Math.cos(2 * Math.PI * i / win);
      re[i] = mono[off + i] * w; im[i] = 0;
    }
    fft.run(re, im);
    let s = 0, r2 = 0;
    for (let b = 0; b < nBins; b++) {
      const mag = Math.hypot(re[b], im[b]);
      const d = mag - prev[b];
      if (d > 0) s += d;
      prev[b] = mag;
    }
    flux[f] = s / nBins;
    for (let i = 0; i < win; i += 4) r2 += mono[off + i] * mono[off + i];
    rms[f] = Math.sqrt(r2 / (win / 4));
  }
  // сглаживание и нормализация
  const fSm = smooth(flux, 3);
  const fNorm = norm(fSm);
  const rNorm = norm(smooth(rms, 8));

  // темп: автокорреляция потока ударов
  const fps = sr / hop;
  let bestLag = 0, bestV = -1;
  for (let lag = Math.round(.30 * fps); lag <= Math.round(1.1 * fps); lag++) {
    let v = 0;
    for (let i = lag; i < frames; i += 2) v += fNorm[i] * fNorm[i - lag];
    v /= (frames - lag);
    const score = v * (1 - Math.abs(lag / fps - .5) * .25);
    if (score > bestV) { bestV = score; bestLag = lag; }
  }
  let bpm = bestLag ? 60 * fps / bestLag : 120;
  while (bpm < 70) bpm *= 2;
  while (bpm > 180) bpm /= 2;
  const beatLen = 60 / bpm;

  // фаза сетки: подбираем смещение, чтобы доли попадали на удары
  let bestPh = 0, bestS = -1;
  const nPh = 32;
  for (let k = 0; k < nPh; k++) {
    const ph = k / nPh * beatLen;
    let s = 0, n = 0;
    for (let t = ph; t < len / sr; t += beatLen) { s += fNorm[Math.min(frames - 1, Math.round(t * fps))]; n++; }
    s /= Math.max(1, n);
    if (s > bestS) { bestS = s; bestPh = ph; }
  }
  const dur = len / sr;
  const beats = [];
  for (let t = bestPh; t < dur; t += beatLen) beats.push(t);

  // сильные удары (для акцентов)
  const onsets = [];
  const thr = .32;
  for (let f = 2; f < frames - 2; f++) {
    if (fNorm[f] > thr && fNorm[f] >= fNorm[f - 1] && fNorm[f] > fNorm[f + 1] && fNorm[f] > fNorm[f - 2] * 1.15) {
      const t = f * hop / sr;
      if (!onsets.length || t - onsets[onsets.length - 1] > .12) onsets.push(t);
    }
  }

  const energyAt = t => {
    const f = clamp(Math.round(t * fps), 0, frames - 1);
    let a = 0; for (let i = Math.max(0, f - 12); i < Math.min(frames, f + 12); i++) a = Math.max(a, rNorm[i]);
    return a;
  };
  const beatDur = () => beatLen;
  const beat = t => { const k = (t - bestPh) / beatLen; return k - Math.floor(k); };
  const pulse = t => {   // 0..1 — насколько свежий удар (для подпрыгиваний и качания камеры)
    const k = (t - bestPh) / beatLen;
    const ph = k - Math.floor(k);
    return (1 - ph) ** 3;
  };
  return { bpm, beatLen, beats, onsets, flux: fNorm, rms: rNorm, duration: dur, energyAt, beatDur, beat, pulse, fps, empty: false };
}

// если музыки нет — ровная сетка 120 BPM
export function silentAnalysis(duration = 60, bpm = 120) {
  const beatLen = 60 / bpm, beats = [];
  for (let t = 0; t < duration; t += beatLen) beats.push(t);
  return {
    bpm, beatLen, beats, onsets: beats.filter((_, i) => i % 4 === 0), duration,
    energyAt: t => .5 + .25 * Math.sin(t * .5), beatDur: () => beatLen,
    beat: t => { const k = t / beatLen; return k - Math.floor(k); },
    pulse: t => (1 - (t / beatLen) % 1) ** 3, empty: true,
  };
}

export function analyzeFile(file, ac) {
  return file.arrayBuffer().then(ab => ac.decodeAudioData(ab)).then(buf => ({ buffer: buf, analysis: analyzeBuffer(buf) }));
}

function smooth(a, n) {
  const out = new Float32Array(a.length);
  for (let i = 0; i < a.length; i++) {
    let s = 0, c = 0;
    for (let k = -n; k <= n; k++) { const j = i + k; if (j >= 0 && j < a.length) { s += a[j]; c++; } }
    out[i] = s / c;
  }
  return out;
}
function norm(a) {
  let m = 0; for (const v of a) m = Math.max(m, v);
  const out = new Float32Array(a.length);
  for (let i = 0; i < a.length; i++) out[i] = m ? a[i] / m : 0;
  return out;
}

// компактное БПФ (radix-2)
export class FFT {
  constructor(n) { this.n = n; this.rev = new Uint32Array(n); let bits = Math.log2(n) | 0; for (let i = 0; i < n; i++) { let r = 0; for (let b = 0; b < bits; b++) if (i & (1 << b)) r |= 1 << (bits - 1 - b); this.rev[i] = r; } }
  run(re, im) {
    const n = this.n, rev = this.rev;
    for (let i = 0; i < n; i++) { const j = rev[i]; if (j > i) { let t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; } }
    for (let size = 2; size <= n; size <<= 1) {
      const half = size >> 1, step = -2 * Math.PI / size;
      for (let i = 0; i < n; i += size) {
        for (let j = i, k = 0; j < i + half; j++, k++) {
          const a = step * k, wr = Math.cos(a), wi = Math.sin(a);
          const xr = re[j + half] * wr - im[j + half] * wi, xi = re[j + half] * wi + im[j + half] * wr;
          re[j + half] = re[j] - xr; im[j + half] = im[j] - xi;
          re[j] += xr; im[j] += xi;
        }
      }
    }
  }
}
