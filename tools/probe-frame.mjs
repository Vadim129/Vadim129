// probe-frame.mjs — покадровый поиск падения: валидирует ellipse/arc, печатает первый плохой вызов.
import { createCanvas, DOMMatrix as NapiMatrix } from '@napi-rs/canvas';

let badCount = 0;
function wrapCtx(g, tag) {
  for (const m of ['ellipse', 'arc']) {
    const raw = g[m].bind(g);
    g[m] = (...a) => {
      const ok = a.every(v => typeof v !== 'number' || Number.isFinite(v));
      if (!ok) {
        badCount++;
        if (badCount <= 3) {
          console.log(`BAD ${m} [${tag}]:`, JSON.stringify(a));
          console.log(new Error('trace').stack.split('\n').slice(1, 8).join('\n'));
        }
        return;
      }
      return raw(...a);
    };
  }
  return g;
}
const _createCanvas = (w, h) => {
  const c = createCanvas(w, h);
  const rawGet = c.getContext.bind(c);
  c.getContext = (...a) => wrapCtx(rawGet(...a), `${w}x${h}`);
  return c;
};

globalThis.document = {
  createElement: tag => {
    if (tag === 'canvas') return _createCanvas(8, 8);
    throw new Error('unsupported element: ' + tag);
  },
  getElementById: () => null,
};
globalThis.DOMMatrix = NapiMatrix;

const { registerFonts } = await import('./fonts.mjs');
registerFonts();
const { collectImgs, registerAssetScenes } = await import('./asset.mjs');
const { silentAnalysis } = await import('../src/audio.js');
const { Renderer } = await import('../src/render.js');
const { SCENES_D } = await import('../src/scenes4.js');
const byId = Object.fromEntries(SCENES_D.map(s => [s.id, s]));
await registerAssetScenes(byId, collectImgs(process.argv));

const rest = process.argv.slice(2).filter(a => a !== '--img' && !a.endsWith('.png') && !a.endsWith('.jpg') && !a.endsWith('.jpeg'));
const sceneId = rest.find(a => !a.startsWith('--')) || 'surf_stand';
const sc = byId[sceneId];
const analysis = silentAnalysis(30, 94);
const seg = {
  id: sceneId, t0: 0, t1: sc.dur, index: 0, transition: 'cut', dur: sc.dur, seed: 777,
  cam: { a: { nx: 0, ny: 0, z: 1.1, r: 0 }, b: { nx: .1, ny: -.1, z: 1.15, r: .005 } },
};
seg.local = t => Math.max(0, Math.min(seg.dur, t - seg.t0));
const tl = { segments: [seg], duration: sc.dur, profile: 'marker', paper: 'plain', palette: 'bright', mood: 'evening', dens: 1.2, analysis, scenesById: byId };

const canvas = _createCanvas(540, 960);
const renderer = new Renderer(canvas, { profile: 'marker', paper: 'plain', palette: 'bright', mood: 'evening' });
const N = Math.round(sc.dur * 10);
for (let i = 0; i <= N; i++) {
  const T = i / 10;
  renderer.frame(T, tl);
  if (i % 30 === 0) console.log(`frame T=${T.toFixed(1)} ok (bad so far: ${badCount})`);
}
console.log(`DONE ${sceneId}: bad ellipse/arc calls = ${badCount}`);
