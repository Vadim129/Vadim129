// timeline.js — раскладка клипа: автомат + сценарий, всё выравнивается по долям.
import { clamp, lerp, mulberry, ss, seedFromString, R01, pick } from './util.js';

export const CALM = ['cat_sleep', 'coffee', 'stars', 'boat', 'window_rain', 'tree_swing', 'flowers', 'pillow'];
export const ENERGY = ['dance', 'city_night', 'heart', 'music', 'cake', 'bicycle', 'balloon', 'todo', 'window_rain', 'flowers'];
const FINALE = 'pillow';

function beatsIn(analysis) { return analysis.beats && analysis.beats.length ? analysis.beats : null; }
function snap(t, analysis, dur) {   // притянуть время к ближайшей доле
  const B = beatsIn(analysis); if (!B) return t;
  let best = B[0], bd = Infinity;
  for (const b of B) { const d = Math.abs(b - t); if (d < bd) { bd = d; best = b; } }
  if (bd > (dur || .5)) return t;
  return best;
}

// Выбрать сцену по энергии момента
export function pickScene(energy, used, seed, dens) {
  const R = mulberry(seed);
  const hi = energy > .58, lo = energy < .3;
  const pool = hi ? ENERGY : lo ? CALM : CALM.concat(ENERGY);
  const banned = new Set(used.slice(-2));
  const options = pool.filter(id => !banned.has(id));
  const list = options.length ? options : pool;
  return pick(R, list);
}

// Построить всю раскладку клипа.
export function buildTimeline(o) {
  const { duration, analysis, script, scenesById, profile, paper, palette, mood, dens = 1, transition = 'auto', seed = 1 } = o;
  const beatLen = analysis.beatLen, segs = [];
  const used = [];
  const mk = (id, t0, t1, extra = {}) => {
    const R = mulberry(Math.floor(t0 * 977) + seed * 31 + seedFromString(id));
    const camA = { nx: R01(R, -.4, .4), ny: R01(R, -.32, .32), z: R01(R, 1.04, 1.2), r: R01(R, -.014, .014) };
    const camB = { nx: clamp(camA.nx + R01(R, -.35, .35), -1, 1), ny: clamp(camA.ny + R01(R, -.3, .3), -1, 1), z: R01(R, camA.z * .96, camA.z * 1.3), r: R01(R, -.02, .02) };
    const seg = { id, t0, t1, cam: { a: camA, b: camB }, params: extra.params || {}, seed: Math.floor(R() * 1e6) };
    segs.push(seg); used.push(id);
    return seg;
  };

  const entries = (script && script.entries) || [];
  const fillGaps = (placed) => {          // промежутки закрывает автомат
    let pos = 0;
    const fill = (from, to, prevId) => {
      let p = from, guard = 0;
      while (to - p > 3.2 && guard++ < 40) {
        const want = clamp(beatLen * 8 * (1 + Math.round(2 * mulberry(guard * 71 + p)())), 6, 16);
        const len = Math.min(want, to - p);
        const mid = p + len / 2;
        const id = pickScene(analysis.energyAt ? analysis.energyAt(mid) : .5, [prevId], seed + Math.floor(p * 13) + guard, dens);
        const t0 = snap(p, analysis, .4), t1r = snap(p + len, analysis, .4);
        mk(id, t0, t1r > t0 + 3 ? t1r : p + len);
        p += len;
      }
    };
    placed.forEach(e => { fill(pos, e.t0, used[used.length - 1]); mk(e.id, e.t0, e.t1, { params: e.params }); pos = e.t1; });
    if (duration - pos > 3) fill(pos, duration, used[used.length - 1]);
    return pos;
  };
  if (entries.length) {
    const placed = [];
    let cursor = 0;
    for (const e of entries) {
      const defDur = (scenesById[e.id] && scenesById[e.id].dur) || 12;
      let t0 = e.t0 === null || e.t0 === undefined ? null : snap(e.t0, analysis, .35);
      let t1 = e.t1 === null || e.t1 === undefined ? null : snap(e.t1, analysis, .35);
      if (t0 === null) { t0 = cursor; t1 = t0 + defDur; }
      else if (t1 === null) t1 = t0 + defDur;
      placed.push({ id: e.id, t0, t1, params: e.params });
      cursor = Math.max(cursor, t1);
    }
    placed.sort((a, b) => a.t0 - b.t0);
    for (let i = 0; i < placed.length; i++) {   // явное время побеждает: предыдущая сцена обрезается
      const p = placed[i], nx = placed[i + 1];
      p.t0 = clamp(p.t0, 0, Math.max(0, duration - 2.4));
      if (nx && p.t1 > nx.t0) p.t1 = Math.max(p.t0 + 2.4, nx.t0);
      p.t1 = clamp(p.t1, p.t0 + 2.4, duration);
    }
    fillGaps(placed);
  } else {
    // полный автомат
    let p = 0, guard = 0;
    while (duration - p > 2.5 && guard++ < 60) {
      const e = analysis.energyAt ? analysis.energyAt(p + 2) : .5;
      const bars = clamp(Math.round(2 + e * 3 + mulberry(guard * 37 + seed)() * 1.2), 2, 5);
      let len = beatLen * 4 * bars;
      if (duration - p - len < 4.5) len = duration - p;
      const id = pickScene(e, used, seed + Math.floor(p * 7) + guard, dens);
      mk(id, snap(p, analysis, .4), p + len);
      p += len;
    }
  }

  // финал: если осталось прилично времени и последняя сцена не финальная — ставим «подушку»
  const last = segs[segs.length - 1];
  if (last && last.id !== FINALE && scenesById[FINALE] && last.t1 - last.t0 > 9) {
    const cut = Math.max(last.t0 + 5, last.t1 - Math.min(15, (last.t1 - last.t0) * .55));
    mk(FINALE, snap(cut, analysis, .4), last.t1);
    last.t1 = Math.min(last.t1, segs[segs.length - 1].t0);
  }
  // переходы
  const mode = transition === 'auto' || !transition ? null : transition;
  segs.forEach((s, i) => {
    const prev = segs[i - 1];
    const gap = prev ? s.t0 - prev.t1 : 0;
    s.index = i;
    s.transition = i === 0 ? 'cut' : (mode ? mode : (gap > .02 || i % 2 === 0) ? 'flip' : 'cut');
    s.dur = s.t1 - s.t0;
    s.local = t => clamp(t - s.t0, 0, s.dur);
  });
  return { segments: segs, duration, profile, paper, palette, mood, dens, transition: mode || 'auto', analysis };
}

export function segmentAt(tl, T) {
  const S = tl.segments;
  for (let i = S.length - 1; i >= 0; i--) if (T >= S[i].t0) return S[i];
  return S[0];
}
