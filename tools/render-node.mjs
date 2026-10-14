// render-node.mjs — рендер клипа InkClip в Node, без браузера.
// Рисует тем же движком (src/*.js) на @napi-rs/canvas, звук анализирует analyzeBuffer,
// кадры гонит в ffmpeg → готовый mp4 со звуком.
//
//   node tools/render-node.mjs --script clips/surfer.txt --audio track.mp3 --out clip.mp4
//   node tools/render-node.mjs --script clips/surfer.txt --audio track.mp3 --out test.mp4 \
//       --size 540x960 --from 0 --to 12 --no-audio
import { createCanvas, DOMMatrix as NapiMatrix } from '@napi-rs/canvas';
import { spawn, spawnSync } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// ── шимы браузера ────────────────────────────────────────────────────────────
function guardCtx(g) {
  // нативный canvas падает на NaN (браузер молча пропускает) — отсекаем заранее
  for (const m of ['ellipse', 'arc']) {
    const raw = g[m].bind(g);
    g[m] = (...a) => {
      for (const v of a) if (typeof v === 'number' && !Number.isFinite(v)) return;
      return raw(...a);
    };
  }
  return g;
}
function shimCanvas(w, h) {
  const c = createCanvas(w, h);
  const rawGet = c.getContext.bind(c);
  c.getContext = (...a) => guardCtx(rawGet(...a));
  return c;
}
globalThis.document = {
  createElement: tag => {
    if (tag === 'canvas') return shimCanvas(8, 8);
    throw new Error('unsupported element: ' + tag);
  },
  getElementById: () => null,
};
globalThis.DOMMatrix = NapiMatrix;

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const { analyzeBuffer } = await import('../src/audio.js');
const { parseScript } = await import('../src/script.js');
const { buildTimeline } = await import('../src/timeline.js');
const { Renderer } = await import('../src/render.js');
const { SCENES_A } = await import('../src/scenes1.js');
const { SCENES_B } = await import('../src/scenes2.js');
const { SCENES_C } = await import('../src/scenes3.js');
const { SCENES_D } = await import('../src/scenes4.js');

const SCENES = [...SCENES_A, ...SCENES_B, ...SCENES_C, ...SCENES_D];
const byId = Object.fromEntries(SCENES.map(s => [s.id, s]));

// ── аргументы ───────────────────────────────────────────────────────────────
const args = {};
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (a.startsWith('--')) {
    const k = a.slice(2);
    const v = process.argv[i + 1] && !process.argv[i + 1].startsWith('--') ? process.argv[++i] : '1';
    args[k] = v;
  }
}
const need = ['script', 'audio', 'out'];
for (const k of need) if (!args[k]) { console.error(`нужен --${k}`); process.exit(1); }

const [W, H] = (args.size || '720x1280').split('x').map(Number);
const FPS = Number(args.fps || 30);
const tFrom = Number(args.from || 0);
const tTo = args.to !== undefined ? Number(args.to) : null;
const withAudio = !args['no-audio'];

function ffmpegBin() {
  if (args.ffmpeg && existsSync(args.ffmpeg)) return args.ffmpeg;
  const r = spawnSync('python3', ['-c', 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'], { encoding: 'utf8' });
  const p = r.stdout ? r.stdout.trim() : '';
  if (p && existsSync(p)) return p;
  return 'ffmpeg';
}
const FF = ffmpegBin();

// ── звук: декодировать и проанализировать ────────────────────────────────────
console.log('звук:', args.audio);
let pcm;
{
  const r = spawnSync(FF, ['-hide_banner', '-loglevel', 'error', '-i', args.audio, '-ac', '1', '-ar', '44100', '-f', 'f32le', '-'], { maxBuffer: 512 * 1024 * 1024 });
  if (r.status !== 0) { console.error('ffmpeg decode failed'); process.exit(1); }
  pcm = new Float32Array(r.stdout.buffer, r.stdout.byteOffset, Math.floor(r.stdout.length / 4));
}
const SR = 44100;
const fakeBuf = { sampleRate: SR, length: pcm.length, numberOfChannels: 1, getChannelData: () => pcm, duration: pcm.length / SR };
console.log('анализ трека...');
const analysis = analyzeBuffer(fakeBuf);
console.log(`темп: ${analysis.bpm.toFixed(1)} BPM, доля: ${analysis.beatLen.toFixed(3)} c, ударов: ${analysis.onsets.length}, длина: ${analysis.duration.toFixed(1)} c`);

// ── сценарий и таймлайн ─────────────────────────────────────────────────────
await registerAssetScenes(byId, collectImgs(process.argv));   // --img до разбора сценария
const scriptText = readFileSync(args.script, 'utf8');
const parsed = parseScript(scriptText, byId);
for (const w of parsed.warnings) console.log('сценарий:', w);
const duration = analysis.duration;
const TRMAP = { 'листать': 'flip', 'встык': 'cut', 'авто': 'auto', flip: 'flip', cut: 'cut', auto: 'auto' };
const tl = buildTimeline({
  duration, analysis, scenesById: byId,
  script: { entries: parsed.entries },
  profile: parsed.profile || 'marker', paper: parsed.paper || 'plain',
  palette: parsed.palette || 'bright', mood: parsed.mood || 'evening',
  dens: parsed.dens || 1, transition: TRMAP[parsed.transition] || 'auto',
  seed: parsed.seed ?? 7,
});
tl.scenesById = byId;
console.log(`стиль: ${tl.profile} / ${tl.paper} / ${tl.palette} / ${tl.mood}, сцен: ${tl.segments.length}`);
for (const s of tl.segments) console.log(`  ${s.t0.toFixed(1)}–${s.t1.toFixed(1)}  ${s.id}  (${s.transition})`);

// ── рендер ──────────────────────────────────────────────────────────────────
const canvas = createCanvas(W, H);
const renderer = new Renderer(canvas, { profile: tl.profile, paper: tl.paper, palette: tl.palette, mood: tl.mood });
renderer.setStyle({ profile: tl.profile, paper: tl.paper, palette: tl.palette, mood: tl.mood });

const start = tFrom, end = tTo === null ? duration : Math.min(tTo, duration);
const N = Math.max(1, Math.round((end - start) * FPS));
console.log(`кадры: ${N} (${W}x${H}@${FPS}, ${start.toFixed(1)}–${end.toFixed(1)} c) → ${args.out}`);

const ffArgs = ['-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${W}x${H}`, '-framerate', String(FPS), '-i', '-'];
if (withAudio) ffArgs.push('-ss', String(start), '-t', String(end - start), '-i', args.audio);
ffArgs.push('-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-preset', 'veryfast');
if (withAudio) ffArgs.push('-c:a', 'aac', '-b:a', '160k', '-shortest');
ffArgs.push('-movflags', '+faststart', args.out);
const ff = spawn(FF, ffArgs, { stdio: ['pipe', 'inherit', 'inherit'] });

function writePixels(buf) {
  return new Promise((res, rej) => {
    if (!ff.stdin.write(buf)) ff.stdin.once('drain', res);
    else res();
  });
}

const t0 = Date.now();
const g = canvas.getContext('2d');
for (let i = 0; i < N; i++) {
  const T = Math.min(start + i / FPS, duration - 1e-3);
  renderer.frame(T, tl);
  const img = g.getImageData(0, 0, W, H);
  await writePixels(Buffer.from(img.data.buffer, img.data.byteOffset, img.data.byteLength));
  if ((i + 1) % Math.max(1, Math.round(FPS * 5)) === 0 || i === N - 1) {
    const el = (Date.now() - t0) / 1000, fps = (i + 1) / el;
    console.log(`  ${i + 1}/${N}  ${(T).toFixed(1)}c  ${fps.toFixed(1)} fps`);
  }
}
ff.stdin.end();
await new Promise((res, rej) => { ff.on('close', c => (c === 0 ? res() : rej(new Error('ffmpeg exit ' + c)))); });
console.log('готово:', args.out);
