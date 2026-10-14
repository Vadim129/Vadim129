// materials.js — «чем рисуем». Ядро картинки: штрих, нажим, зерно, заливка.
// Один и тот же рисунок, нарисованный разными материалами, выглядит совершенно по-разному.
import { TAU, PI, clamp, lerp, L2, hash, vn, mulberry, bbox, nrm, sub, dist, resample, catmull, R01, pick } from './util.js';

// ---------- текстуры ----------
export function grainCanvas(size = 256, seed = 77, amount = 1) {   // зерно бумаги: пропуски шарика, поры карандаша
  const c = document.createElement('canvas'); c.width = c.height = size;
  const g = c.getContext('2d'), R = mulberry(seed);
  for (let k = 0; k < size * size / 26 * amount; k++) {
    const x = R() * size, y = R() * size;
    g.fillStyle = `rgba(0,0,0,${(.3 + R() * .7).toFixed(3)})`;
    g.beginPath(); g.ellipse(x, y, .5 + R() * 1.7, .35 + R() * .8, R() * PI, 0, TAU); g.fill();
  }
  return c;
}

// ---------- материалы ----------
// pass — сколько раз проходим по линии (сухие материалы «набирают» тон)
// grain — сколько зерна выбиваем из слоя (рвёт штрих, как бумага)
// wob — дрожь руки, taper — сход на конце, blob — клякса в начале
export const MAT = {
  pen:    { color: '#1d38a6', w: 3.2, pass: 1, alpha: 1, textAlpha: 1.6,    wob: 1.0, grain: .42, blob: .8, taper: .55, ink: 1 },
  liner:  { color: '#26262e', w: 2.5, pass: 1, alpha: .93,  wob: .9,  grain: .30, blob: .5, taper: .5,  ink: 1 },
  pencil: { color: '#4a4a56', w: 2.7, pass: 3, alpha: .26, textAlpha: .85,  wob: 1.8, grain: .78, blob: 0,  taper: .45, dry: 1 },
  colored:{ color: '#b23b2e', w: 3.1, pass: 3, alpha: .30, textAlpha: .85,  wob: 2.0, grain: .88, blob: 0,  taper: .4,  dry: 1 },
  marker: { color: '#e0a12f', w: 12,  pass: 1, alpha: .22, textAlpha: 1,  wob: .6,  grain: .14, blob: 0,  taper: .2,  halo: 1.4, bleed: 1 },
  chalk:  { color: '#f6f3ea', w: 5.2, pass: 2, alpha: .40, textAlpha: 1.1,  wob: 2.3, grain: .55, blob: 0,  taper: .35, dry: 1 },
  white:  { color: '#ffffff', w: 5,   pass: 1, alpha: .8,   wob: 1.0, grain: .1,  blob: 0,  taper: .3 },
  crayon: { color: '#8a6a4a', w: 9.5, pass: 2, alpha: .42,  wob: 2.4, grain: .62, blob: 0,  taper: .3,  dry: 1, wax: 1 },
  gouache:{ color: '#2f5f9f', w: 7.5, pass: 1, alpha: .80,  wob: .8,  grain: .10, blob: 0,  taper: .18, gouache: 1 },
};

// палитры: цветные карандаши / фломастеры
export const PALETTES = {
  warm:  ['#c0392b', '#e08a2e', '#e6c34a', '#5b8f5a', '#2f6f8f', '#7d4f8c', '#8a6a44'],
  cool:  ['#2f6f8f', '#3f8f8a', '#5b8f5a', '#7d6fae', '#2d4f8f', '#4a9aa8', '#a86f9a'],
  bright:['#e2402f', '#f2a52b', '#f4dd3b', '#43a35f', '#2f8fd0', '#8a5bd0', '#e052a0'],
  mute:  ['#8a5a4a', '#a8845a', '#7d8a5a', '#5a7d78', '#5a6a8a', '#7a5f7a', '#6a6a62'],
  night: ['#4a5f9e', '#2f4a7a', '#6a5f9e', '#3f6a8a', '#24507a', '#8a6a9e', '#2a3a5a'],
};

// профиль: чем именно рисуется «главная линия», «заливка» и «акцент».
// Сцена говорит только роль (main/fill/accent) и цвет — профиль решает, как это выглядит.
export const PROFILES = {
  pencil: { id: 'pencil', name: 'Простой карандаш',   mono: 1, layers: ['pencil', 'liner'],
    main: { mat: 'pencil', color: '#4a4a56' }, fill: { mat: 'pencil', color: '#6b6b78' }, accent: { mat: 'liner', color: '#3a3a44' } },
  color:  { id: 'color', name: 'Цветные карандаши',  mono: 0, layers: ['colored', 'liner'],
    main: { mat: 'liner', color: '#3a3a44' }, fill: { mat: 'colored' }, accent: { mat: 'colored' } },
  marker: { id: 'marker', name: 'Фломастеры',         mono: 0, layers: ['marker', 'liner'],
    main: { mat: 'liner', color: '#26262e' }, fill: { mat: 'marker' }, accent: { mat: 'marker' } },
  pen:    { id: 'pen', name: 'Шариковая ручка',       mono: 1, layers: ['pen'],
    main: { mat: 'pen', color: '#1d38a6' }, fill: { mat: 'pen', color: '#1d38a6', fillStyle: 'hatch', lighter: 1 }, accent: { mat: 'pen', color: '#1d38a6' } },
  mixed:  { id: 'mixed', name: 'Смешанная техника',   mono: 0, layers: ['colored', 'marker', 'liner'],
    main: { mat: 'liner', color: '#22222a' }, fill: { mat: 'colored' }, accent: { mat: 'marker' } },
  chalk:  { id: 'chalk', name: 'Мел',                 mono: 1, layers: ['chalk'], paper: 'dark',
    main: { mat: 'chalk', color: '#f6f3ea' }, fill: { mat: 'chalk', color: '#cfd8e8', fillStyle: 'hatch' }, accent: { mat: 'chalk', color: '#ffe9a8' } },
  crayon: { id: 'crayon', name: 'Восковые мелки',      mono: 0, layers: ['crayon', 'liner'],
    main: { mat: 'crayon', color: '#6a4a2a' }, fill: { mat: 'crayon' }, accent: { mat: 'crayon', color: '#8a5a2a' } },
  gouache:{ id: 'gouache', name: 'Гуашь',              mono: 0, layers: ['gouache', 'liner'],
    main: { mat: 'liner', color: '#2b2b33' }, fill: { mat: 'gouache' }, accent: { mat: 'gouache', color: '#c0392b' } },
  felt:   { id: 'felt', name: 'Цветные фломастеры',    mono: 0, layers: ['marker', 'liner'],
    main: { mat: 'marker', wScale: .62 }, fill: { mat: 'marker' }, accent: { mat: 'marker', wScale: .5 }, paper: 'plain' },
};

// ---------- нажим ----------
// [x,y] -> [x,y,p]: дрожь руки, неровный нажим, клякса в начале и сход на конце
export function press(pts, seed = 0, o = {}) {
  const n = pts.length, out = [], wob = o.wob ?? 1.1, base = o.p ?? .7;
  for (let i = 0; i < n; i++) {
    const a = pts[Math.max(i - 1, 0)], b = pts[Math.min(i + 1, n - 1)], d = nrm(sub(b, a));
    const off = (vn(seed * 3.7 + i * .09) - .5) * 2 * wob;
    let p = base + .42 * (vn(seed * 1.3 + i * .12) - .5) * 2 + .12 * (vn(seed * 5.1 + i * .6) - .5);
    if (o.blob !== false) p += .45 * Math.max(0, 1 - i / 3);
    if (o.taper !== false) p *= .45 + .55 * Math.min(1, (n - 1 - i) / 7);
    out.push([pts[i][0] - d[1] * off, pts[i][1] + d[0] * off, clamp(p, .1, 1.5)]);
  }
  return out;
}

// ---------- штрих ----------
export function drawStroke(g, pts, mat, o = {}) {
  const frac = o.frac === undefined ? 1 : o.frac;
  if (frac <= 0 || pts.length < 2) return;
  const wBase = (o.w ?? 1) * mat.w * (mat.dry ? .95 : 1);
  const color = o.color || mat.color;
  const passes = o.pass ?? mat.pass;
  const alpha = (o.alpha ?? mat.alpha) * (o.alphaScale ?? 1);
  const n = pts.length;
  const m = frac * (n - 1), last = Math.min(n - 1, Math.floor(m));

  g.strokeStyle = color; g.fillStyle = color; g.lineCap = 'round'; g.lineJoin = 'round';
  if (mat.bleed && g.shadowBlur !== undefined) { g.shadowColor = color; g.shadowBlur = mat.w * .5; }

  for (let pass = 0; pass < passes; pass++) {
    const ox = passes > 1 ? (hash(o.seed * 7.1 + pass * 3.3) - .5) * mat.wob * 2.6 : 0;
    const oy = passes > 1 ? (hash(o.seed * 11.7 + pass * 5.1) - .5) * mat.wob * 2.6 : 0;
    g.globalAlpha = clamp(alpha * (passes > 1 ? 1 / (1 + pass * .55) : 1), .015, 1);
    let q = -1; g.beginPath(); g.moveTo(pts[0][0] + ox, pts[0][1] + oy);
    for (let i = 1; i <= last + 1 && i < n; i++) {
      let b = pts[i];
      if (i > last) { const f = m - last, a = pts[last]; if (f <= 0) break; b = [lerp(a[0], b[0], f), lerp(a[1], b[1], f), b[2]]; }
      const p = pts[i - 1][2] === undefined ? .7 : pts[i - 1][2];
      const taper = o.taper === false ? 1 : 1 - (mat.taper ?? .4) * Math.max(0, 1 - (n - i) / Math.min(9, n - 1));
      const qq = Math.round(clamp(wBase * (.55 + .78 * p) * taper, .12, 90) * 4) / 4;
      if (qq !== q && q >= 0) { g.stroke(); g.beginPath(); g.moveTo(pts[i - 1][0] + ox, pts[i - 1][1] + oy); }
      g.lineWidth = q = qq; g.lineTo(b[0] + ox, b[1] + oy);
    }
    g.stroke();
  }
  g.globalAlpha = 1; g.shadowBlur = 0;
  if (mat.blob && (o.blob ?? true) && frac > .02) {   // клякса/жирная точка в начале
    g.globalAlpha = clamp(alpha, 0, 1);
    g.beginPath(); g.ellipse(pts[0][0], pts[0][1], wBase * .8 * mat.blob, wBase * .68 * mat.blob, hash(o.seed) * PI, 0, TAU); g.fill();
    g.globalAlpha = 1;
  }
}

// штрих «мокрым» фломастером: широкий ореол + плотная середина (растекание по волокнам)
export function drawBleed(g, pts, mat, o = {}) {
  drawStroke(g, pts, { ...mat, w: mat.w * (mat.halo ?? 1.4), alpha: mat.alpha * .30, pass: 1, blob: 0, taper: .1 }, { ...o, pass: 1, seed: (o.seed || 0) + 4.4 });
  drawStroke(g, pts, mat, o);
  drawStroke(g, pts, { ...mat, w: mat.w * .55, alpha: mat.alpha * .5 }, { ...o, seed: (o.seed || 0) + 9.1 });
}

// ---------- заливка ----------
// path — точки замкнутого контура. mode: 'hatch' (штриховка) | 'scribble' (каляки) | 'solid' (фломастер)
export function fillShape(g, path, mat, o = {}) {
  const i = 0;   // no-op, чтобы линтер не ругался: держим сигнатуру
  const mode = o.mode || (mat.gouache || mat.bleed ? 'solid' : mat.dry ? (o.scribble ? 'scribble' : 'hatch') : 'hatch');
  const box = o.box || bbox(path);
  const seed = o.seed ?? 7, R = mulberry(Math.floor(seed * 1000) + 17);
  const reveal = o.reveal || (() => 1);

  g.save();
  g.beginPath();
  path.forEach((q, k) => (k ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1])));
  g.closePath();
  g.clip();

  if (mode === 'solid') {
    g.globalAlpha = clamp(mat.alpha * 2.1, .05, .95); g.fillStyle = o.color || mat.color; g.fill();
    g.globalAlpha = clamp(mat.alpha * 3.2, .05, 1); g.strokeStyle = o.color || mat.color; g.lineWidth = mat.w * 1.5;
    g.beginPath(); path.forEach((q, k) => (k ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]))); g.stroke();
    g.globalAlpha = 1;
  } else if (mode === 'scribble') {
    const ang = o.angle ?? (R() - .5) * 1.2, sp = Math.max(6, (o.spacing ?? 9));
    let y = box[1] - sp;
    const dir = Math.cos(ang) >= 0 ? 1 : -1;
    const lines = [];
    while (y < box[3] + sp) { y += sp; lines.push(y); }
    lines.forEach((_, k) => {
      const f = reveal(k, lines.length); if (f <= 0) return;
      const pts = [];
      const n = 7;
      for (let s = 0; s <= n; s++) {
        const x = lerp(box[0] - 6, box[2] + 6, dir > 0 ? s / n : 1 - s / n);
        pts.push([x, lines[k] + (vn(seed + k * 3.3 + s * .8) - .5) * sp * .9]);
      }
      drawStroke(g, press(pts, seed + k, { wob: mat.wob * .6, taper: false, blob: false }), mat,
        { frac: f, seed: seed + k, pass: o.pass ?? 1, w: o.w ?? .9, color: o.color });
    });
    g.globalAlpha = 1;
  } else {
    const ang = (o.angle ?? -PI / 5) + (o.skew ?? 0);
    const sp = Math.max(6, o.spacing ?? (mat.w * 4.6));
    const diag = dist([box[0], box[1]], [box[2], box[3]]) + (box[2] - box[0]) * .6;
    const mid = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2];
    const count = Math.ceil(diag / sp) + 2;
    const angs = o.cross ? [ang, ang + PI / 3.4] : [ang];
    angs.forEach((A, ai) => {
      const D = nrm([Math.cos(A), Math.sin(A)]);
      for (let k = -count; k <= count; k++) {
        const f = reveal(k + count, count * 2, ai); if (f <= 0) continue;
        const off = k * sp + (vn(seed * 2 + k * .6 + ai * 9) - .5) * sp * .55;
        const c = [mid[0] - D[1] * off, mid[1] + D[0] * off];
        const halfL = spanAlong(box, D);
        const a = [c[0] - D[0] * halfL, c[1] - D[1] * halfL], b = [c[0] + D[0] * halfL, c[1] + D[1] * halfL];
        const raw = [a, b];
        const pts = press(wobble(raw, seed + k * 1.7, mat.wob), seed + k, { wob: mat.wob * .5, taper: false, blob: false });
        drawStroke(g, pts, mat, { frac: f, seed: seed + k * 3.1 + ai * 5, color: o.color, w: o.w ?? 1, pass: o.pass ?? (o.pass === 0 ? 1 : Math.min(mat.pass, 2)), alphaScale: (o.alphaScale ?? .5) * (.7 + .6 * vn(seed + k * .7)) });
      }
    });
  }
  g.restore();
}
function spanAlong(box, D) {   // насколько длинной должна быть линия вдоль направления D, чтобы пройти фигуру
  let mn = Infinity, mx = -Infinity;
  for (const [x, y] of [[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]]]) {
    const t = x * D[0] + y * D[1];
    if (t < mn) mn = t; if (t > mx) mx = t;
  }
  return (mx - mn) / 2 + 6;
}
function wobble(a, seed, amp) {
  const d = nrm(sub(a[1], a[0])), N = [-d[1], d[0]], out = [];
  const n = 5;
  for (let i = 0; i <= n; i++) { const t = i / n; const o = (vn(seed + i * .9) - .5) * 2 * amp * Math.sin(PI * t); out.push([lerp(a[0][0], a[1][0], t) + N[0] * o, lerp(a[0][1], a[1][1], t) + N[1] * o]); }
  return out;
}

// ---------- слои ----------
// Каждый материал живёт в своём слое: в конце кадр «пробивается» зерном бумаги и умножается на бумагу.
export const LAYER_ORDER = ['colored', 'marker', 'pencil', 'chalk', 'white', 'liner', 'pen'];

export class Paint {
  constructor(W, H, grain) { this.W = W; this.H = H; this.grain = grain; this.m = new Map(); this.used = new Set(); }
  layer(key) {
    let L = this.m.get(key);
    if (!L) { const c = document.createElement('canvas'); c.width = this.W; c.height = this.H; L = { c, g: c.getContext('2d') }; this.m.set(key, L); }
    this.used.add(key);
    return L.g;
  }
  clear() { for (const L of this.m.values()) { L.g.setTransform(1, 0, 0, 1, 0, 0); L.g.globalAlpha = 1; L.g.globalCompositeOperation = 'source-over'; L.g.clearRect(0, 0, this.W, this.H); } this.used.clear(); }
  // наложить слои на target: зерно выбивается в координатах бумаги (cm), чтобы не «ползло» при движении камеры
  compose(target, cm, only = null, mode = 'multiply') {
    const keys = only || LAYER_ORDER;
    const M = new DOMMatrix(cm);
    for (const key of keys) {
      const L = this.m.get(key); if (!L) continue;
      if (!this.used.has(key)) continue;    // в этом кадре слой не трогали — не тратим время
      const g = L.g;
      const pat = g.createPattern(this.grain, 'repeat');
      if (pat) { try { pat.setTransform(M.scale(.8)); } catch (e) {} g.globalCompositeOperation = 'destination-out'; g.globalAlpha = (MAT[key] && MAT[key].grain) || .3; g.fillStyle = pat; g.fillRect(0, 0, this.W, this.H); g.globalAlpha = 1; g.globalCompositeOperation = 'source-over'; }
      target.save(); target.setTransform(1, 0, 0, 1, 0, 0);
      target.globalCompositeOperation = mode;
      target.drawImage(L.c, 0, 0);
      target.globalCompositeOperation = 'source-over'; target.restore();
    }
  }
}

export const hex2rgb = h => { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
export const shade = (h, k) => {   // k<0 темнее, k>0 светлее
  const [r, g, b] = hex2rgb(h);
  const f = v => Math.round(clamp(k < 0 ? v * (1 + k) : v + (255 - v) * k, 0, 255));
  return `rgb(${f(r)},${f(g)},${f(b)})`;
};
