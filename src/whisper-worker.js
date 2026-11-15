// src/whisper-worker.js — распознавание в отдельном потоке.
//
// Зачем: модель и движок ONNX едят много памяти. Если телефон не потянет,
// падает только этот поток — приложение продолжает работать и показывает ошибку.

import { transcribe } from './whisper.js';

self.onmessage = async ev => {
  const d = ev.data || {};
  if (d.type !== 'transcribe') return;
  const say = (type, extra = {}) => { try { self.postMessage(Object.assign({ type }, extra)); } catch (e) {} };
  try {
    const audio = new Float32Array(d.audio);
    const res = await transcribe(null, {
      audio16k: audio,
      model: d.model || 'tiny',
      language: d.language || 'auto',
      keep: !!d.keep,
      onStatus: text => say('status', { text }),
      onProgress: (frac, text) => say('progress', { frac: frac || 0, text }),
    });
    say('done', {
      result: { text: res.text, words: res.words, kept: !!d.keep, device: res.device },
    });
  } catch (e) {
    say('error', { text: (e && e.message) ? e.message : String(e) });
  }
};
