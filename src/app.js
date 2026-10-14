// app.js — сам «станок»: собирает клип из сцен, играет, рендерит и сохраняет.
import * as U from './util.js';
import { SCENES_A } from './scenes1.js';
import { SCENES_B } from './scenes2.js';
import { SCENES_C, makePhotoScene, makeTraceScene } from './scenes3.js';
import { analyzeBuffer, silentAnalysis } from './audio.js';
import { parseScript } from './script.js';
import { buildTimeline, segmentAt } from './timeline.js';
import { Renderer } from './render.js';
import { PROFILES } from './materials.js';
import { loadImageFromFile, toCanvas, traceImage, shadingStrokes } from './image.js';
import { recordClip, download } from './export.js';
import { wordsToScript } from './whisper.js';
import { saveBlob, isNative } from './native.js';

const SCENES = [...SCENES_A, ...SCENES_B, ...SCENES_C, ...SCENES_D];
const byId = Object.fromEntries(SCENES.map(s => [s.id, s]));

const state = {
  words: [],
  profile: 'pencil', paper: 'notebook', palette: 'warm', mood: 'day',
  dens: 1, seed: 42, transition: 'auto', mode: 'auto', script: '',
  quality: '720x1280', asset: null, caption: 'этот день', shade: true, trKeep: .32, trMode: 'auto',
};
const audio = { buffer: null, analysis: silentAnalysis(64, 120), name: '', ctx: null };
const words = { list: [], text: '', busy: false, model: 'tiny', lang: 'auto' };
let tl = null, renderer = null, T = 0, playing = false, rafId = 0;
let audioSrc = null, audioT0 = 0, clk0 = 0;
let previewScene = null;

const $ = id => document.getElementById(id);
const canvas = $('stage');

// ── размер холста ───────────────────────────────────────────────────────────
function setSize(w, h) {
  canvas.width = w; canvas.height = h;
  renderer = new Renderer(canvas, { profile: state.profile, paper: state.paper, palette: state.palette, mood: state.mood });
  applyStyle();
}
function applyStyle() { renderer.setStyle({ profile: state.profile, paper: state.paper, palette: state.palette, mood: state.mood }); }

// ── сборка клипа ────────────────────────────────────────────────────────────
function build() {
  if (typeof invalidateClip === 'function') invalidateClip();
  if (!state.keepPreview) previewScene = null;      // настройки и сценарий всегда собирают клип целиком
  state.keepPreview = false;
  const duration = audio.buffer ? audio.buffer.duration : 64;
  const parsed = parseScript(state.script, byId);
  let profile = state.profile, paper = state.paper, palette = state.palette, mood = state.mood, dens = state.dens;
  const warn = [];
  if (state.mode === 'script') {
    profile = parsed.profile || profile; paper = parsed.paper || paper;
    palette = parsed.palette || palette; mood = parsed.mood || mood;
    if (parsed.dens) dens = parsed.dens;
    if (parsed.seed !== null && parsed.seed !== undefined) state.seed = parsed.seed;
    warn.push(...parsed.warnings);
    for (const e of parsed.entries) if (!state.asset && (e.id === 'my_photo' || e.id === 'my_trace')) warn.push('сцена «' + e.id + '» есть в сценарии, но картинка не загружена');
  }
  if (previewScene) {
    const sc = previewScene;
    tl = {
      segments: [{ id: sc.id, t0: 0, t1: sc.dur, cam: { a: { nx: 0, ny: .15, z: 1.12, r: -.004 }, b: { nx: .12, ny: -.1, z: 1.22, r: .006 } }, params: {}, seed: state.seed * 77, index: 0, transition: 'cut', dur: sc.dur }],
      duration: sc.dur, profile, paper, palette, mood, dens, analysis: audio.analysis, scenesById: byId,
    };
    tl.segments[0].local = t => U.clamp(t, 0, sc.dur);
  } else {
    tl = buildTimeline({
      duration, analysis: audio.analysis, scenesById: byId,
      script: state.mode === 'script' ? parsed : { entries: [] },
      profile, paper, palette, mood, dens, transition: state.transition, seed: state.seed,
    });
    tl.scenesById = byId;
  }
  state.profile = profile; state.paper = paper; state.palette = palette; state.mood = mood; state.dens = dens;
  state.warn = warn;
  applyStyle();
  renderer.setStyle({ paper });
  paintUI();
  seek(T);
}

// ── воспроизведение ─────────────────────────────────────────────────────────


// ── Whisper: слова трека → сценарий ─────────────────────────────────────────
// Распознавание идёт в отдельном потоке (worker): если модель не влезет в память
// телефона — упадёт поток, а приложение продолжит работать.
let whWorker = null;

const escapeHtml = t => String(t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// слова с временем: чипсы, клик — перейти к этому месту
function paintWords(list) {
  const box = $('whWords');
  if (!box) return;
  if (!list.length) { box.innerHTML = ''; return; }
  box.innerHTML = list.slice(0, 300).map(w => {
    const t = w.t0 != null ? `${Math.floor(w.t0 / 60)}:${String(Math.floor(w.t0 % 60)).padStart(2, '0')}` : '';
    return `<span class="chip" style="margin:2px;font-size:12px;padding:3px 7px;cursor:pointer" data-t="${w.t0 != null ? w.t0 : ''}" title="${t}">${escapeHtml(w.text)}${t ? ' <b style="opacity:.6">' + t + '</b>' : ''}</span>`;
  }).join('');
  box.querySelectorAll('[data-t]').forEach(el => {
    el.onclick = () => { const t = parseFloat(el.dataset.t); if (!isNaN(t)) { pause(); seek(t); } };
  });
}

function stopWhisperWorker() {
  if (whWorker) { try { whWorker.terminate(); } catch (e) {} whWorker = null; }
}

function runWhisperInWorker(audio16k, { model, language, keep, onStatus, onProgress }) {
  return new Promise((resolve, reject) => {
    stopWhisperWorker();
    let w;
    try {
      w = new Worker(new URL('./whisper-worker.js', import.meta.url), { type: 'module' });
    } catch (e) { return reject(new Error('браузер не дал запустить отдельный поток: ' + e.message)); }
    whWorker = w;
    let finished = false;
    w.onmessage = ev => {
      const m = ev.data || {};
      if (m.type === 'status') onStatus(m.text);
      else if (m.type === 'progress') onProgress(m.frac, m.text);
      else if (m.type === 'done') { finished = true; if (!m.result.kept) stopWhisperWorker(); resolve(m.result); }
      else if (m.type === 'error') { finished = true; stopWhisperWorker(); reject(new Error(m.text)); }
    };
    w.onerror = e => { if (!finished) { stopWhisperWorker(); reject(new Error('распознавание упало: ' + (e.message || 'не хватило памяти'))); } };
    w.onmessageerror = () => { if (!finished) { stopWhisperWorker(); reject(new Error('поток не смог передать ответ')); } };
    const buf = audio16k.buffer.slice(0);
    w.postMessage({ type: 'transcribe', audio: buf, model, language, keep }, [buf]);
  });
}

async function runWhisper() {
  if (words.busy) return;
  if (!audio.buffer) { $('whStatus').textContent = 'сначала загрузи трек в панели «Музыка» — слова нужны из твоего вокала.'; return; }
  words.busy = true;
  const btn = $('btnWhisper'); btn.disabled = true; btn.textContent = 'слушаю…';
  $('whInfo').textContent = ''; $('whBar').style.width = '0%';
  const t0 = Date.now();
  try {
    const { to16k } = await import('./whisper.js');
    $('whStatus').textContent = 'готовлю звук (16 кГц, моно)…';
    const mono = to16k(audio.buffer);
    const keep = !!($('whKeep') && $('whKeep').checked);
    const res = await runWhisperInWorker(mono, {
      model: $('whModel').value, language: $('whLang').value, keep,
      onStatus: t => { $('whStatus').textContent = t; },
      onProgress: (f, msg) => { $('whBar').style.width = Math.round(Math.min(1, f) * 100) + '%'; if (msg) $('whStatus').textContent = msg; },
    });
    $('whBar').style.width = '100%';
    words.list = res.words; words.text = res.text;
    paintWords(res.words);
    const secs = ((Date.now() - t0) / 1000).toFixed(0);
    $('whStatus').textContent = res.words.length
      ? `готово за ${secs} с · слов: ${res.words.length}${res.kept ? ' · модель осталась в памяти' : ' · память освобождена'}`
      : `готово за ${secs} с · слов не разобрал — попробуй трек с ясным вокалом`;
    $('whInfo').innerHTML = res.text ? `<b>текст:</b> ${escapeHtml(res.text.slice(0, 600))}` : '';
    $('btnWhisperScript').disabled = !res.words.length;
    state.words = res.words;
  } catch (e) {
    $('whStatus').textContent = 'не вышло: ' + (e && e.message ? e.message : e);
    $('whBar').style.width = '0%';
  } finally {
    words.busy = false; btn.disabled = false; btn.textContent = 'распознать слова';
  }
}

function scriptFromWords() {
  if (!state.words || !state.words.length) return;
  const dur = audio.buffer ? audio.buffer.duration : 64;
  const res = wordsToScript(state.words, { analysis: audio.analysis, duration: dur });
  if (!res.lines.length) { $('whInfo').textContent = res.summary; return; }
  const head = `стиль: ${state.profile}\nбумага: ${state.paper}\nпалитра: ${state.palette}\nнастроение: ${state.mood}\nплотность: ${state.dens}\nвариант: ${state.seed}\n\n`;
  state.mode = 'script';
  // финал добавляем только если после последней сцены осталось место
  const last = res.lines.length ? res.lines[res.lines.length - 1].t : 0;
  const tail = (dur - last) > 11 ? '\nфинал' : '';
  state.script = head + res.text + tail;
  $('scriptBox').value = state.script;
  document.querySelectorAll('[data-mode]').forEach(b => b.classList.toggle('on', b.dataset.mode === 'script'));
  build(); paintUI(); paintClock(); seek(0);
  $('whInfo').innerHTML = `<b>${res.summary}</b> — в списке сцен: ${res.lines.map(l => l.id).join(', ')}. Можно править руками в «Сценарии».`;
}

function seek(t) {
  T = U.clamp(t, 0, tl.duration);
  if (renderer && tl) renderer.frame(T, tl);
  paintClock();
}
function play() {
  if (playing) return;
  playing = true; $('btnPlay').textContent = '❚❚';
  const ac = getCtx();
  clk0 = ac.currentTime; audioT0 = T;
  if (audio.buffer) {
    audioSrc = ac.createBufferSource(); audioSrc.buffer = audio.buffer;
    audioSrc.connect(ac.destination); audioSrc.start(0, T % audio.buffer.duration);
  }
  const loop = () => {
    if (!playing) return;
    const ac2 = getCtx();
    T = audioT0 + (ac2.currentTime - clk0);
    if (T >= tl.duration) {
      T = 0; audioT0 = 0; clk0 = ac2.currentTime;
      if (audioSrc) { try { audioSrc.stop(); } catch (e) {} audioSrc = null; }
      if (audio.buffer) { audioSrc = ac2.createBufferSource(); audioSrc.buffer = audio.buffer; audioSrc.connect(ac2.destination); audioSrc.start(0, 0); }
    }
    try { renderer.frame(T, tl); paintClock(); }
    catch (e) { if (softError('кадр', e)) { playing = false; return; } }
    rafId = requestAnimationFrame(loop);
  };
  rafId = requestAnimationFrame(loop);
}
function pause() {
  playing = false;
  const b = $('btnPlay'); if (b) b.textContent = '▶';
  cancelAnimationFrame(rafId); rafId = 0;
  if (audioSrc) { try { audioSrc.stop(); } catch (e) {} try { audioSrc.disconnect(); } catch (e) {} audioSrc = null; }
}
function stopPlayback() {
  pause();
  T = 0; audioT0 = 0;
  if (renderer && tl) renderer.frame(0, tl);
  paintClock();
}
function getCtx() {
  if (!audio.ctx) audio.ctx = new (window.AudioContext || window.webkitAudioContext)();
  if (audio.ctx.state === 'suspended') audio.ctx.resume();
  return audio.ctx;
}

// ── интерфейс ───────────────────────────────────────────────────────────────
function paintClock() {
  $('clock').textContent = `${clock(T)} / ${clock(tl.duration)}`;
  $('bar').style.width = `${(T / tl.duration * 100).toFixed(1)}%`;
  $('segInfo').textContent = previewScene ? `сцена: ${byId[previewScene.id].name}` : `сцен: ${tl.segments.length} · ${audio.name || 'без музыки'}`;
}
const clock = t => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
function paintUI() {
  document.querySelectorAll('[data-profile]').forEach(b => b.classList.toggle('on', b.dataset.profile === state.profile));
  $('selPaper').value = state.paper; $('selPalette').value = state.palette; $('selMood').value = state.mood;
  $('selDens').value = state.dens; $('densVal').textContent = (+state.dens).toFixed(2);
  $('seedVal').textContent = state.seed;
  $('warn').textContent = (state.warn && state.warn.length) ? '⚠ ' + state.warn.join(' · ') : '';
  const list = tl.segments.map(s => `${clock(s.t0)} ${byId[s.id] ? byId[s.id].name : s.id}`).join('\n');
  $('plan').textContent = previewScene ? 'одиночная сцена' : list;
}

// ── кадр PNG ────────────────────────────────────────────────────────────────
function saveFrame() {
  renderer.frame(T, tl);
  canvas.toBlob(b => download(b, `кадр-${clock(T).replace(':', '-')}.png`), 'image/png');
}

// ── экспорт клипа ───────────────────────────────────────────────────────────
let clipBusy = false;
let lastClip = null;               // готовый клип: {url, name, mb}

function paintClipButtons() {
  const top = $('btnSaveClip'), panel = $('btnExport');
  const ready = !!lastClip;
  if (top) {
    top.disabled = clipBusy;
    top.textContent = clipBusy ? '⏳ пишу клип…' : (ready ? '⬇ Скачать клип (mp4)' : '🎬 Сделать клип (mp4)');
  }
  if (panel) {
    panel.disabled = clipBusy;
    panel.textContent = panel.dataset.plain === '1'
      ? (clipBusy ? 'запись…' : (ready ? '⬇ Скачать клип' : '🎬 Сделать клип'))
      : (clipBusy ? '⏳ пишу клип…' : (ready ? '⬇ Скачать клип (mp4)' : '🎬 Сделать клип (mp4)'));
  }
  if ($('saveHint')) {
    $('saveHint').textContent = ready
      ? `клип готов: ${lastClip.mb} МБ · ${lastClip.name} · нажми «сделать заново», если поменял настройки`
      : 'запись идёт в реальном времени: клип на 1 минуту пишется примерно минуту, вкладку не закрывай';
  }
}

function downloadLastClip() {
  if (!lastClip) return false;
  const a = document.createElement('a');
  a.href = lastClip.url; a.download = lastClip.name;
  document.body.appendChild(a); a.click(); a.remove();
  return true;
}

// любая смена настроек/сценария отменяет готовый клип: он теперь не про эти настройки
function invalidateClip() {
  if (lastClip) { try { URL.revokeObjectURL(lastClip.url); } catch (e) {} }
  lastClip = null;
  if ($('saveBox')) $('saveBox').innerHTML = '';
  if ($('videoOut')) $('videoOut').innerHTML = '';
  if ($('exportInfo')) $('exportInfo').textContent = '';
  paintClipButtons();
}

function onClipButton() {
  if (lastClip) downloadLastClip();      // клип есть — скачиваем
  else exportClip();                     // клипа нет — делаем
}

async function exportClip() {
  if (clipBusy) return;
  pause();
  clipBusy = true;
  const prev = { w: canvas.width, h: canvas.height };
  const [ew, eh] = state.quality.split('x').map(Number);
  setSize(ew, eh);
  paintClipButtons();
  $('exportInfo').textContent = 'запись… идёт в реальном времени, не закрывай вкладку';
  const ac = getCtx();
  try {
    const { blob, ext } = await recordClip({
      canvas, audioCtx: ac, buffer: audio.buffer, duration: tl.duration, fps: 30,
      renderFrame: t => { renderer.frame(t, tl); },
      onProgress: p => { $('bar').style.width = `${(p * 100).toFixed(1)}%`; $('clock').textContent = `рендер ${(p * 100) | 0}%`; },
    });
    const name = `клип-${state.profile}-${state.seed}.${ext}`;
    const saved = await saveBlob(blob, name);
    const url = URL.createObjectURL(blob);
    const mb = (blob.size / 1048576).toFixed(1);
    // большая кнопка «сохранить» — на первом плане
    $('exportInfo').innerHTML = `готово: <b>${name}</b> (${mb} МБ) — ${saved.where}`
      + `<br><span class="hint">${saved.path}</span>`;
    $('saveBox').innerHTML = '';
    const save = document.createElement('a');
    save.href = url; save.download = name; save.className = 'primary';
    save.style.cssText = 'display:inline-block;padding:12px 18px;border-radius:10px;text-decoration:none;font-weight:600';
    save.textContent = `💾 Сохранить клип ещё раз (${mb} МБ)`;
    const open = document.createElement('a');
    open.href = url; open.target = '_blank'; open.rel = 'noopener';
    open.className = 'ghost';
    open.style.cssText = 'display:inline-block;margin-left:8px;padding:12px 18px;border-radius:10px;text-decoration:none';
    open.textContent = 'открыть в новой вкладке';
    const tip = document.createElement('div');
    tip.className = 'hint'; tip.style.marginTop = '6px';
    tip.innerHTML = 'если файл не появился в загрузках — значит скачивание блокирует окно предпросмотра: открой приложение отдельной вкладкой (или поставь APK) и нажми кнопку снова';
    $('saveBox').append(save, open, tip);
    $('videoOut').innerHTML = '';
    const v = document.createElement('video'); v.controls = true; v.playsInline = true; v.src = url;
    $('videoOut').appendChild(v);
    lastClip = { url, name, mb, ext };
    paintClipButtons();
  } catch (e) {
    $('exportInfo').textContent = 'не получилось: ' + e.message + '. Попробуй открыть страницу в новой вкладке и запустить снова.';
  }
  clipBusy = false;
  paintClipButtons();
  setSize(prev.w, prev.h);
  seek(0);
}

// ── свои картинки ───────────────────────────────────────────────────────────
async function handleImage(file) {
  if (!file) return;
  const info = $('imgInfo');
  info.textContent = 'читаю картинку…';
  try {
    const { img } = await loadImageFromFile(file);
    const c = toCanvas(img, 380);
    const trace = traceImage(c, { keep: state.trKeep, mode: state.trMode, minPath: 12, maxStrokes: 420, blur: 1.4 });
    const shading = state.shade ? shadingStrokes(c, { block: 8, min: .44, angle: -.62 }).slice(0, 900) : [];
    state.lastFile = file;
    state.asset = { canvas: c, w: trace.w, h: trace.h, strokes: trace.strokes, shading, name: file.name, caption: () => state.caption };
    byId.my_photo = makePhotoScene(state.asset);
    byId.my_trace = makeTraceScene(state.asset);
    addChip(byId.my_photo); addChip(byId.my_trace);
    const prev = $('imgPreview');
    prev.innerHTML = '';
    c.style.width = '96px'; c.style.height = 'auto'; c.style.borderRadius = '6px';
    prev.appendChild(c);
    $('btnPhotoPreview').disabled = false; $('btnTracePreview').disabled = false;
    $('btnPhotoAdd').disabled = false; $('btnTraceAdd').disabled = false;
    info.textContent = `${file.name} · ${c.width}×${c.height} · режим: ${trace.mode === 'lines' ? 'линии' : 'края'} · линий: ${trace.count} · штрихов тени: ${shading.length}`;
  } catch (e) {
    info.textContent = 'не получилось: ' + e.message;
  }
}
function addChip(scene) {
  if (document.querySelector(`#scenes [data-id="${scene.id}"]`)) return;
  const b = document.createElement('button');
  b.className = 'chip'; b.dataset.id = scene.id; b.textContent = scene.name;
  b.onclick = () => { state.keepPreview = true; previewScene = scene; $('btnClearPreview').style.display = 'inline-block'; build(); T = 0; play(); };
  $('scenes').appendChild(b);
}

// ── запуск ──────────────────────────────────────────────────────────────────
function boot() {
  setSize(540, 960);
  build();
  seek(0);

  document.querySelectorAll('[data-profile]').forEach(b => b.onclick = () => {
    state.profile = b.dataset.profile;
    const pr = PROFILES[state.profile];
    if (pr.paper) { state.paper = pr.paper; $('selPaper').value = state.paper; }
    build();
  });
  $('selPaper').onchange = e => { state.paper = e.target.value; build(); };
  $('selPalette').onchange = e => { state.palette = e.target.value; build(); };
  $('selMood').onchange = e => { state.mood = e.target.value; build(); };
  $('selDens').oninput = e => { state.dens = +e.target.value; $('densVal').textContent = state.dens.toFixed(2); build(); };
  $('selQuality').onchange = e => { state.quality = e.target.value; if ($('selQualityTop')) $('selQualityTop').value = state.quality; };
  if ($('selQualityTop')) $('selQualityTop').onchange = e => { state.quality = e.target.value; $('selQuality').value = state.quality; };
  $('btnSaveClip').onclick = () => onClipButton();
  document.querySelectorAll('[data-trans]').forEach(b => b.onclick = () => { state.transition = b.dataset.trans; document.querySelectorAll('[data-trans]').forEach(x => x.classList.toggle('on', x === b)); build(); });
  document.querySelectorAll('[data-mode]').forEach(b => b.onclick = () => { state.mode = b.dataset.mode; document.querySelectorAll('[data-mode]').forEach(x => x.classList.toggle('on', x === b)); $('scriptBox').style.display = state.mode === 'script' ? 'block' : 'none'; build(); });
  $('scriptBox').value = state.script;
  $('scriptBox').oninput = e => { state.script = e.target.value; if (state.mode === 'script') build(); };
  $('btnPlay').onclick = () => playing ? pause() : play();
  $('btnStop').onclick = () => stopPlayback();
  $('btnFrame').onclick = saveFrame;
  $('btnExport').dataset.plain = '1';
  $('btnExport').onclick = () => onClipButton();
  paintClipButtons();
  $('btnSeed').onclick = () => { state.seed = Math.floor(Math.random() * 99999); build(); };
  $('btnClearPreview').onclick = () => { previewScene = null; $('btnClearPreview').style.display = 'none'; build(); seek(0); };
  $('imgFile').onchange = e => handleImage(e.target.files[0]);
  $('imgShade').onchange = e => { state.shade = e.target.checked; if (state.lastFile) handleImage(state.lastFile); };
  $('imgCaption').value = state.caption;
  $('imgCaption').oninput = e => { state.caption = e.target.value.replace(/\n/g, ' '); if (state.asset) build(); };
  $('trKeep').oninput = e => { state.trKeep = +e.target.value; $('trKeepVal').textContent = state.trKeep.toFixed(2); };
  $('trKeep').onchange = () => { if (state.lastFile) handleImage(state.lastFile); };
  $('trMode').onchange = e => { state.trMode = e.target.value; if (state.lastFile) handleImage(state.lastFile); };
  $('btnPhotoPreview').onclick = () => { if (!state.asset) return; state.keepPreview = true; previewScene = byId.my_photo; $('btnClearPreview').style.display = 'inline-block'; build(); T = 0; play(); };
  $('btnTracePreview').onclick = () => { if (!state.asset) return; state.keepPreview = true; previewScene = byId.my_trace; $('btnClearPreview').style.display = 'inline-block'; build(); T = 0; play(); };
  $('btnPhotoAdd').onclick = () => { if (!state.asset) return; addScriptLine('картинка: ' + (state.caption || 'этот день')); };
  $('btnTraceAdd').onclick = () => { if (!state.asset) return; addScriptLine('обводка 0:00'); };
  $('mrFile').onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    $('mrInfo').textContent = `читаю ${f.name}…`;
    try {
      const ac = getCtx();
      const ab = await f.arrayBuffer();
      const buf = await ac.decodeAudioData(ab);
      audio.buffer = buf; audio.name = f.name;
      audio.analysis = analyzeBuffer(buf);
      $('mrInfo').textContent = `${f.name} · ${clock(buf.duration)} · ${Math.round(audio.analysis.bpm)} BPM · ударов: ${audio.analysis.onsets.length}`;
      build(); seek(0);
    } catch (err) {
      audio.buffer = null; audio.name = ''; audio.analysis = silentAnalysis(64, 120);
      $('mrInfo').textContent = `не смог прочитать «${f.name}» — этот формат браузер не понял. Попробуй mp3, wav или m4a.`;
      build();
    }
  };
  canvas.onclick = () => playing ? pause() : play();
  $('btnWhisper').onclick = () => runWhisper();
  $('btnWhisperScript').onclick = () => scriptFromWords();

  SCENES.forEach(s => {
    const b = document.createElement('button');
    b.className = 'chip'; b.dataset.id = s.id; b.textContent = s.name; b.title = s.id;
    b.onclick = () => { state.keepPreview = true; previewScene = s; $('btnClearPreview').style.display = 'inline-block'; build(); T = 0; play(); };
    $('scenes').appendChild(b);
  });
  $('legend').textContent = SCENES.map(s => `${s.id} — ${s.name}`).join('\n')
    + '\nmy_photo — моё фото в кадре (нужна загрузка)\nmy_trace — обводка моей картинки (нужна загрузка)';
  if (isNative()) $('platformNote').textContent = 'приложение Android: клип сохраняется в «Документы»';
  // на телефоне по умолчанию 540p: 1080p может не хватить памяти и приложение вылетит
  const mem = navigator.deviceMemory || 0, mobile = isNative() || /Android|iPhone|iPad/i.test(navigator.userAgent);
  if ((mem && mem <= 4) || mobile) {
    state.quality = '540x960';
    if ($('selQuality')) $('selQuality').value = state.quality;
    if ($('selQualityTop')) $('selQualityTop').value = state.quality;
    if ($('saveHint')) $('saveHint').textContent = 'на телефоне по умолчанию 540p — так быстрее и без вылетов; больше — в списке качества';
  }
  paintClipButtons();
}
function addScriptLine(line) {
  state.mode = 'script';
  document.querySelectorAll('[data-mode]').forEach(x => x.classList.toggle('on', x.dataset.mode === 'script'));
  $('scriptBox').style.display = 'block';
  const add = (line.split(':')[0] === 'картинка') ? `картинка: ${state.caption}` : line;
  state.script = (state.script ? state.script.replace(/\s*$/, '\n') : '') + add + '\n';
  $('scriptBox').value = state.script;
  build();
}
// ── предохранители: приложение не должно «вылетать» молча ───────────────────
let softErrors = 0;
function softError(where, e) {
  softErrors++;
  const msg = (e && e.message) ? e.message : String(e);
  try { $('warn').textContent = `⚠ ${where}: ${msg}`; } catch (_) {}
  console.warn('[inkclip]', where, e);
  if (softErrors > 25) {                 // что-то системно не так — останавливаемся, а не мигаем
    playing = false;
    try { $('warn').textContent = `⚠ ошибок слишком много (${where}). ${msg} — перезагрузи приложение`; } catch (_) {}
    return true;
  }
  return false;
}
window.addEventListener('error', e => { softError('ошибка', e.error || e); });
window.addEventListener('unhandledrejection', e => { softError('сбой', e.reason); });

document.addEventListener('DOMContentLoaded', boot);
window.INK = { state, audio, get tl() { return tl; }, build, seek, play, pause, stop: stopPlayback, get T() { return T; }, get playing() { return playing; }, renderer: () => renderer, setSize, byId, handleImage, addScriptLine, runWhisper, scriptFromWords, words };
, scriptFromWords, words };
