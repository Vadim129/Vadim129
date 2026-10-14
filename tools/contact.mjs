// contact.mjs — по одному кадру из каждой сцены (контроль композиции).
import { createCanvas, DOMMatrix as NapiMatrix } from '@napi-rs/canvas';
import { writeFileSync } from 'node:fs';
globalThis.document = { createElement: t => { if (t === 'canvas') return createCanvas(8, 8); throw new Error(t); }, getElementById: () => null };
globalThis.DOMMatrix = NapiMatrix;
const { silentAnalysis } = await import('../src/audio.js');
const { Renderer } = await import('../src/render.js');
const { SCENES_D } = await import('../src/scenes4.js');
const byId = Object.fromEntries(SCENES_D.map(s => [s.id, s]));
const analysis = silentAnalysis(30, 94);
const out = process.argv[2] || '/tmp/contact';
for (const sc of SCENES_D) {
  const seg = {
    id: sc.id, t0: 0, t1: sc.dur, index: 0, transition: 'cut', dur: sc.dur, seed: 777,
    cam: { a: { nx: 0, ny: 0, z: 1.08, r: 0 }, b: { nx: .08, ny: -.06, z: 1.14, r: .004 } },
  };
  seg.local = t => Math.max(0, Math.min(seg.dur, t - seg.t0));
  const tl = { segments: [seg], duration: sc.dur, profile: 'marker', paper: 'plain', palette: 'bright', mood: 'evening', dens: 1.2, analysis, scenesById: byId };
  const canvas = createCanvas(540, 960);
  const renderer = new Renderer(canvas, { profile: 'marker', paper: 'plain', palette: 'bright', mood: 'evening' });
  renderer.frame(sc.dur * .72, tl);
  writeFileSync(`${out}_${sc.id}.png`, canvas.toBuffer('image/png'));
  console.log('saved', sc.id);
}
