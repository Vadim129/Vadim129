// src/whisper.js — слова трека на устройстве: Whisper (ONNX) через transformers.js.
//
// Ничего не улетает на сервер: библиотека, wasm-движок ONNX и модель лежат внутри
// приложения (папки vendor/ и models/). Интернет не нужен вообще.
//
// Что даёт: слова с точным временем → из них собирается сценарий (см. wordsToScript).

const V3 = '3.3.3', V2 = '2.17.2';

// ── что уже лежит внутри приложения ─────────────────────────────────────────
const HERE = typeof import.meta !== 'undefined' && import.meta.url ? import.meta.url : location.href;
export const LOCAL = {
  lib: new URL('../vendor/transformers/transformers.js', HERE).href,
  ort: new URL('../vendor/ort/', HERE).href,
  modelsDir: new URL('../models/', HERE).href,
};

// проверяем, скачана ли модель внутрь (файл конфига — самый мелкий)
let localModels = null;
export async function checkLocalModels() {
  if (localModels !== null) return localModels;
  localModels = {};
  for (const key of Object.keys(WHISPER_MODELS)) {
    const dir = WHISPER_MODELS[key].local;
    if (!dir) continue;
    try {
      const r = await fetch(new URL(`${dir}/config.json`, LOCAL.modelsDir));
      localModels[key] = !!r.ok;
    } catch { localModels[key] = false; }
  }
  return localModels;
}

const SOURCES = [
  { url: LOCAL.lib, kind: 'v3', repo: 'onnx-community', local: true },
];

let lib = null, src = null, pipe = null, pipeKey = '';

// _timestamped-версии обучены отдавать время по каждому слову (нужны для «слово → сцена»)
export const WHISPER_MODELS = {
  tiny: { v3: 'onnx-community/whisper-tiny_timestamped', local: 'whisper-tiny', mb: 44, label: 'встроенная (44 МБ, уже внутри приложения)' },
};

export function whisperLoaded() { return !!pipe; }

// освободить память (на телефоне это главная причина вылетов)
export async function releaseWhisper() {
  try { if (pipe && pipe.dispose) await pipe.dispose(); } catch {}
  pipe = null; pipeKey = '';
}

// ── библиотека ──────────────────────────────────────────────────────────────
export async function loadLib(onStatus = () => {}) {
  if (lib) return lib;
  let lastErr = null;
  for (const s of SOURCES) {
    try {
      onStatus(s.local ? 'поднимаю Whisper из самого приложения…' : `загружаю библиотеку Whisper (${new URL(s.url).host})…`);
      lib = await import(/* @vite-ignore */ s.url);
      src = s;
      try { lib.env.allowRemoteModels = false; } catch {}   // никаких скачиваний: только файлы внутри приложения
      try { lib.env.allowLocalModels = true; } catch {}
      if (s.local) { try { lib.env.localModelPath = LOCAL.modelsDir; } catch {} }
      try {
        const ort = lib.env.backends.onnx;          // инициализирует ORT: он ставит свой путь к wasm
        if (ort && ort.wasm) {
          ort.wasm.wasmPaths = LOCAL.ort;           // …переставляем на локальный (файлы внутри приложения)
          ort.wasm.numThreads = 1;
        }
      } catch {}
      src.device = 'wasm';
      if (s.kind === 'v3' && typeof navigator !== 'undefined' && navigator.gpu) {
        // спрашиваем адаптер честно: в некоторых браузерах navigator.gpu есть, а адаптера нет
        try {
          const ad = await navigator.gpu.requestAdapter();
          if (ad) {
            src.device = 'webgpu';
            try { lib.env.backends.onnx.wasm.proxy = false; } catch {}
          }
        } catch { src.device = 'wasm'; }
      }
      return lib;
    } catch (e) { lastErr = e; lib = null; }
  }
  throw new Error('не удалось загрузить библиотеку Whisper — нет интернета? ' + (lastErr ? lastErr.message : ''));
}

// ── звук: привести к 16 кГц моно (Whisper так обучен) ────────────────────────
export function to16k(buffer) {
  const sr = buffer.sampleRate, n = buffer.length;
  const ch0 = buffer.getChannelData(0);
  const ch1 = buffer.numberOfChannels > 1 ? buffer.getChannelData(1) : null;
  const outLen = Math.floor(n * 16000 / sr);
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const t = i * sr / 16000;
    const i0 = Math.floor(t), frac = t - i0, i1 = Math.min(n - 1, i0 + 1);
    const a = ch1 ? (ch0[i0] + ch1[i0]) / 2 : ch0[i0];
    const b = ch1 ? (ch0[i1] + ch1[i1]) / 2 : ch0[i1];
    out[i] = a + (b - a) * frac;
  }
  return out;
}

// ── распознавание ───────────────────────────────────────────────────────────
export async function transcribe(buffer, o = {}) {
  // o.keep — не освобождать модель после распознавания
  const onStatus = o.onStatus || (() => {});
  const onProgress = o.onProgress || (() => {});
  const L = await loadLib(onStatus);
  const model = WHISPER_MODELS[o.model || 'tiny'] || WHISPER_MODELS.tiny;
  const localMap = await checkLocalModels();
  const useLocal = src.local && model.local && localMap[o.model || 'tiny'];
  if (!useLocal) throw new Error('встроенная модель не найдена — файлы models/whisper-tiny должны лежать рядом с приложением');
  const repo = useLocal ? model.local : (src.kind === 'v3' ? model.v3 : model.v2);
  const key = `${repo}:${src.device}`;

  if (pipeKey !== key || !pipe) {
    onStatus('загружаю встроенную модель в память…');
    const seen = new Map();
    const cb = p => {
      if (!p || !p.file) return;
      seen.set(p.file, p);
      let total = 0, loaded = 0;
      for (const q of seen.values()) { if (q.total) { total += q.total; loaded += q.loaded || 0; } }
      const frac = total ? loaded / total : (p.progress ? p.progress / 100 : 0);
      const mb = (loaded / 1048576).toFixed(1);
      onProgress(frac, `скачано ${mb} МБ из ~${model.mb} МБ · ${p.file}`);
      onStatus(p.status === 'ready' ? 'модель готова, слушаю трек…' : `готовлю модель: ${p.file}`);
    };
    const opts = { dtype: 'q8', progress_callback: cb };
    if (src.kind === 'v3') opts.device = src.device;
    try {
      pipe = await L.pipeline('automatic-speech-recognition', repo, opts);
    } catch (e) {
      if (src.device === 'webgpu') {          // запасной путь: на wasm
        onStatus('WebGPU не осилил — считаю на процессоре…');
        src.device = 'wasm';
        opts.device = 'wasm';
        pipe = await L.pipeline('automatic-speech-recognition', repo, opts);
      } else throw e;
    }
    pipeKey = `${repo}:${src.device}`;
  }

  const audio = o.audio16k || to16k(buffer);
  const mins = (audio.length / 16000 / 60).toFixed(1);
  onStatus(`слушаю трек (${mins} мин) — считаю слова…`);
  const params = {
    task: 'transcribe',
    return_timestamps: 'word',
    chunk_length_s: 30,
    stride_length_s: 5,
  };
  if (o.language && o.language !== 'auto') params.language = o.language;
  const res = await pipe(audio, params);
  if (!o.keep) await releaseWhisper();     // по умолчанию освобождаем память сразу

  const chunks = Array.isArray(res.chunks) ? res.chunks : [];
  const words = chunks
    .map(c => ({ text: (c.text || '').trim(), t0: c.timestamp ? c.timestamp[0] : null, t1: c.timestamp ? c.timestamp[1] : null }))
    .filter(w => w.text && w.t0 !== null && w.t0 !== undefined);
  return { text: (res.text || '').trim(), words, device: src.device, model: o.model || 'tiny', local: !!useLocal };
}

// ── слова → сценарий ────────────────────────────────────────────────────────
// Словарь: услышали слово — поставили сцену. Это не ИИ, просто словарь,
// зато мгновенно и бесплатно. Умный разбор (LLM) — следующий шаг.
export const WORD_SCENES = [
  { id: 'window_rain', w: ['дождь', 'дожд', 'капает', 'лужа', 'rain', 'ливень', 'шторм'] },
  { id: 'coffee', w: ['кофе', 'чай', 'утро', 'завтрак', 'кружка', 'coffee', 'tee'] },
  { id: 'city_night', w: ['город', 'город', 'улиц', 'фонар', 'машин', 'асфальт', 'city', 'night'] },
  { id: 'stars', w: ['звезд', 'звёзд', 'неб', 'космос', 'созвезд', 'star'] },
  { id: 'snow', w: ['снег', 'снеж', 'зим', 'мороз', 'снежин', 'snow', 'cold'] },
  { id: 'fire', w: ['костёр', 'костер', 'огон', 'пламя', 'тепл', 'жар', 'fire'] },
  { id: 'road', w: ['дорог', 'поехали', 'поехать', 'шоссе', 'трасс', 'дорог', 'road', 'drive'] },
  { id: 'stretch', w: ['проснул', 'встал', 'вставать', 'потянул', 'солнц', 'тёпл', 'доброе утро'] },
  { id: 'cat_sleep', w: ['кот', 'кошк', 'мурлык', 'мурлыч', 'cat'] },
  { id: 'heart', w: ['сердц', 'любл', 'люб', 'сердце', 'love', 'heart', 'целую'] },
  { id: 'boat', w: ['море', 'лодк', 'корабл', 'волн', 'прибой', 'sea', 'boat'] },
  { id: 'balloon', w: ['шарик', 'шары', 'лети', 'лететь', 'boltals', 'balloon'] },
  { id: 'flowers', w: ['цвет', 'цветы', 'садж', 'сад', 'растёт', 'расти', 'flower'] },
  { id: 'tree_swing', w: ['дерев', 'качел', 'листь', 'двор', 'tree'] },
  { id: 'bicycle', w: ['велосипед', 'велик', 'кручу', 'педал', 'bike'] },
  { id: 'music', w: ['музык', 'песн', 'нот', 'звук', 'наушник', 'music', 'song'] },
  { id: 'dance', w: ['танец', 'танцу', 'танц', 'пляс', 'dance'] },
  { id: 'todo', w: ['дел', 'сделаю', 'список', 'успе', 'план', 'todo', 'work'] },
  { id: 'cake', w: ['торт', 'праздн', 'день рожден', 'свеч', 'cake', 'birthday'] },
  { id: 'pillow', w: ['спат', 'спать', 'сон', 'засну', 'ноч', 'тихо', 'sleep'] },
];

// импульсы: с этими словами сцена режется на части (акцент на слог)
export const HIT_WORDS = ['да', 'нет', 'не', 'я', 'ты', 'мы', 'всё', 'все', 'ещё', 'еще', 'можно', 'здесь', 'сейчас', 'one', 'two', 'go'];

const norm = s => s.toLowerCase().replace(/[^a-zа-яё0-9 ]/gi, '').trim();

export function wordSceneFor(text) {
  const w = norm(text);
  if (!w) return null;
  for (const row of WORD_SCENES) {
    for (const k of row.w) if (w.includes(k)) return row.id;
  }
  return null;
}

// слова -> строки сценария. Время округляется к ближайшей доле трека.
export function wordsToScript(words, o = {}) {
  const analysis = o.analysis;
  const dur = o.duration || (analysis && analysis.duration) || 60;
  const beats = analysis && analysis.beats && analysis.beats.length ? analysis.beats : null;
  const round1 = t => Math.max(0, Math.round(t * 10) / 10);
  const snap = t => {
    if (!beats || !beats.length) return round1(t);
    // за пределами сетки долей притягивать не к чему — оставляем как услышали
    if (t <= beats[0] || t >= beats[beats.length - 1]) return round1(t);
    let best = t, d = 1e9;
    for (let i = 0; i < beats.length; i++) { const e = Math.abs(beats[i] - t); if (e < d) { d = e; best = beats[i]; } }
    return round1(best);
  };
  const minGap = Math.min(6, Math.max(2.2, (dur || 60) / 22));   // длинный трек — реже меняем сцены
  const lines = [];
  let lastId = '', lastT = -99;
  for (const wd of words) {
    const id = wordSceneFor(wd.text);
    if (!id) continue;
    const t = snap(wd.t0);
    if (id === lastId && t - lastT < minGap * 2.5) continue;   // не повторяем одну сцену подряд
    if (lines.length && t < lines[lines.length - 1].t + minGap) continue;
    lines.push({ id, t, word: wd.text });
    lastId = id; lastT = t;
    if (lines.length >= (o.maxLines || 26)) break;
  }
  const fmt = t => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
  const body = lines.map(l => `${l.id} ${fmt(l.t)}`).join('\n');
  return {
    lines,
    text: body,
    summary: lines.length ? `${lines.length} сцен по словам` : 'подходящих слов не нашлось — попробуй модель побольше или трек с вокалом',
    hint: o.duration ? `клип ${Math.round(o.duration)} с` : '',
  };
}

// стихи-акценты: слова-импульсы пригодятся сценам (пока только в отчёте)
export function hitTimes(words) {
  const out = [];
  for (const w of words) if (HIT_WORDS.includes(norm(w.text))) out.push(w.t0);
  return out;
}
