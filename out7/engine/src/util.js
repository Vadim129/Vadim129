// util.js — математика, случайность и геометрия.
// Всё детерминировано по seed: любой кадр можно перерисовать с любого момента времени.
export const TAU = Math.PI * 2;
export const PI = Math.PI;

export const clamp = (v, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, t) => a + (b - a) * t;
export const L2 = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t)];
export const inv = (a, b, v) => (b === a ? 0 : (v - a) / (b - a));
export const ss = (a, b, t) => { const k = clamp(inv(a, b, t)); return k * k * (3 - 2 * k); };   // плавный вход-выход
export const bump = (t, a, b, c, d) => ss(a, b, t) * (1 - ss(c, d, t));                          // вспышка между a..d
export const easeOut = t => 1 - (1 - clamp(t)) ** 3;
export const easeIn = t => clamp(t) ** 3;
export const easeIO = t => { const k = clamp(t); return k < .5 ? 4 * k * k * k : 1 - (-2 * k + 2) ** 3 / 2; };
export const sin01 = (t, ph = 0) => .5 + .5 * Math.sin(TAU * (t + ph));

export const hash = n => { const s = Math.sin(n * 12.9898 + 78.233) * 43758.5453; return s - Math.floor(s); };
export const vn = x => { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return lerp(hash(i), hash(i + 1), u); };   // 1D value noise
export const mulberry = seed => { let a = (seed >>> 0) || 1; return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; };
export const R01 = (R, a, b) => a + R() * (b - a);
export const Rint = (R, a, b) => Math.floor(a + R() * (b - a + 1));
export const pick = (R, arr) => arr[Math.min(arr.length - 1, Math.floor(R() * arr.length))];
export const seedFromString = s => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; };

export const add = (a, b) => [a[0] + b[0], a[1] + b[1]];
export const sub = (a, b) => [a[0] - b[0], a[1] - b[1]];
export const mul = (a, k) => [a[0] * k, a[1] * k];
export const nrm = a => { const l = Math.hypot(a[0], a[1]) || 1; return [a[0] / l, a[1] / l]; };
export const rot = (a, r) => [a[0] * Math.cos(r) - a[1] * Math.sin(r), a[0] * Math.sin(r) + a[1] * Math.cos(r)];
export const len = a => Math.hypot(a[0], a[1]);
export const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

export function bbox(pts) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const p of pts) { if (p[0] < x0) x0 = p[0]; if (p[0] > x1) x1 = p[0]; if (p[1] < y0) y0 = p[1]; if (p[1] > y1) y1 = p[1]; }
  return [x0, y0, x1, y1];
}
export function pathLen(pts) { let L = 0; for (let i = 1; i < pts.length; i++) L += dist(pts[i - 1], pts[i]); return L; }

export function resample(pts, step = 6) {   // точки через равные расстояния
  const out = [pts[0]]; let acc = 0;
  for (let i = 1; i < pts.length; i++) {
    let a = pts[i - 1], b = pts[i], d = dist(a, b);
    while (acc + d >= step) { const t = (step - acc) / d; a = L2(a, b, t); out.push(a); acc = 0; d = dist(a, b); }
    acc += d;
  }
  const last = pts[pts.length - 1];
  if (dist(out[out.length - 1], last) > step * .35) out.push(last);
  return out;
}
export function resampleN(pts, n) {
  if (n < 2 || pts.length < 2) return pts.slice();
  const L = [0]; for (let i = 1; i < pts.length; i++) L.push(L[i - 1] + dist(pts[i - 1], pts[i]));
  const T = L[L.length - 1] || 1, out = []; let j = 1;
  for (let k = 0; k < n; k++) {
    const d = T * k / (n - 1);
    while (j < pts.length - 1 && L[j] < d) j++;
    const u = (d - L[j - 1]) / ((L[j] - L[j - 1]) || 1);
    out.push(L2(pts[j - 1], pts[j], clamp(u)));
  }
  return out;
}

// Сплайн Катмулла-Рома: гладкая линия через точки (рука ведёт плавно, но с лёгким «кипением»)
export function catmull(pts, seg = 8, closed = false) {
  const p = pts.slice(); if (closed) p.push(pts[0]);
  const out = [];
  const at = i => p[clamp(i, 0, p.length - 1)];
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = at(i - 1), p1 = at(i), p2 = at(i + 1), p3 = at(i + 2);
    for (let s = 0; s < seg; s++) {
      const t = s / seg, t2 = t * t, t3 = t2 * t;
      out.push([
        .5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
        .5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3),
      ]);
    }
  }
  out.push(p[p.length - 1]);
  return out;
}

export function smoothPath(pts, amp = 0, seed = 0, seg = 8) {   // сгладить + добавить дрожь руки
  const c = catmull(pts, seg);
  if (!amp) return c;
  return c.map((q, i) => [q[0] + (vn(seed + i * .13) - .5) * 2 * amp, q[1] + (vn(seed * 2.7 + i * .11) - .5) * 2 * amp]);
}

export function offsetPath(pts, d) {   // сдвиг по нормали: для двойной линии, бороздки, тени штриха
  return pts.map((p, i) => {
    const a = pts[Math.max(i - 1, 0)], b = pts[Math.min(i + 1, pts.length - 1)], n = nrm([-(b[1] - a[1]), b[0] - a[0]]);
    return [p[0] + n[0] * d, p[1] + n[1] * d];
  });
}

export function arcPts(cx, cy, rx, ry, a0, a1, n = 28) {
  const out = []; for (let i = 0; i <= n; i++) { const a = lerp(a0, a1, i / n); out.push([cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]); } return out;
}

export function circlePts(cx, cy, rx, ry, seed = 0, o = {}) {   // замкнутый круг «от руки» с перехлёстом
  const over = o.over ?? .28, n = o.n ?? 40;
  return arcPts(cx, cy, rx, ry, o.a0 ?? -.35, (o.a0 ?? -.35) + TAU + over, n);
}

export function rectPts(x, y, w, h, r = 0, seed = 0) {
  if (r <= 0) return [[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y], [x + w * .04, y]];
  const out = [];
  const c = [[x + r, y + r], [x + w - r, y + r, -PI / 2], [x + w - r, y + h - r, 0], [x + r, y + h - r, PI / 2], [x + r, y + r, PI]];
  for (let i = 0; i < 4; i++) {
    const [cx, cy, a0 = 0] = c[i];
    for (let k = 0; k <= 6; k++) out.push([cx + Math.cos(a0 + k / 6 * PI / 2) * r, cy + Math.sin(a0 + k / 6 * PI / 2) * r]);
  }
  out.push(out[0]);
  return out;
}

export function wobbleLine(x1, y1, x2, y2, amp = 1.4, seed = 0, n = 9) {
  const a = [x1, y1], b = [x2, y2], d = nrm(sub(b, a)), N = [-d[1], d[0]], out = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, w = Math.sin(PI * t);
    const o = (vn(seed * 3.1 + i * .7) - .5) * 2 * amp * (.4 + w);
    out.push([lerp(a[0], b[0], t) + N[0] * o, lerp(a[1], b[1], t) + N[1] * o]);
  }
  return out;
}

export function wavePts(x0, x1, y, amp = 12, waves = 3, seed = 0, n = 60) {
  const out = []; for (let i = 0; i <= n; i++) { const t = i / n, x = lerp(x0, x1, t); out.push([x, y + Math.sin(t * TAU * waves + seed) * amp]); } return out;
}

export function fan(from, a0, a1, r0, r1, n = 6, seed = 0) {   // пучок линий (лучи, трава, ресницы)
  const out = []; for (let i = 0; i < n; i++) { const a = lerp(a0, a1, n === 1 ? .5 : i / (n - 1)), r = lerp(r0, r1, vn(seed + i * .37)); out.push([from, [from[0] + Math.cos(a) * r, from[1] + Math.sin(a) * r]]); } return out;
}

export function starPts(cx, cy, r, R, points = 5, rot0 = -PI / 2, jit = 0, seed = 0) {
  const out = [];
  for (let i = 0; i < points * 2; i++) {
    const a = rot0 + i * PI / points, rr = (i % 2 ? R : r) * (1 + (vn(seed + i * .5) - .5) * jit);
    out.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]);
  }
  return smoothPath(out, 0, 0, 3);
}

export function heartPts(cx, cy, s, n = 44) {
  const out = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n * TAU;
    const x = 16 * Math.sin(t) ** 3;
    const y = 13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t);
    out.push([cx + x * s / 16, cy - y * s / 16]);
  }
  return out;
}

export function leafPts(x, y, s, ang, seed = 0) {
  const p = [[x, y]];
  for (let i = 1; i <= 10; i++) { const t = i / 10; p.push([x + Math.cos(ang) * s * t + Math.sin(t * PI) * s * .18 * Math.cos(ang - PI / 2), y + Math.sin(ang) * s * t + Math.sin(t * PI) * s * .18 * Math.sin(ang - PI / 2)]); }
  for (let i = 9; i >= 1; i--) { const t = i / 10; p.push([x + Math.cos(ang) * s * t - Math.sin(t * PI) * s * .18 * Math.cos(ang - PI / 2), y + Math.sin(ang) * s * t - Math.sin(t * PI) * s * .18 * Math.sin(ang - PI / 2)]); }
  p.push([x, y]);
  return p;
}

export function cloudPts(cx, cy, s, seed = 0, o = {}) {   // облако/подушка: замкнутый волнистый контур
  const n = o.n ?? 26, out = [];
  for (let i = 0; i < n; i++) {
    const a = i / n * TAU;
    const k = 1 + .22 * Math.sin(a * 5 + seed) + .12 * Math.sin(a * 3 - seed * 1.7) + (vn(seed * 2 + i * .4) - .5) * .1;
    out.push([cx + Math.cos(a) * s * 1.5 * k, cy + Math.sin(a) * s * .62 * k]);
  }
  out.push(out[0]);
  return smoothPath(out, 0, 0, 4).slice(0, -3);
}

export function spiralPts(cx, cy, r0, r1, turns, a0 = 0, n = 70) {
  const out = []; for (let i = 0; i <= n; i++) { const t = i / n, a = a0 + t * TAU * turns, r = lerp(r0, r1, t); out.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); } return out;
}

export function zigzag(x0, y0, x1, y1, n = 6, amp = 6, seed = 0) {
  const out = [], d = nrm(sub([x1, y1], [x0, y0])), N = [-d[1], d[0]];
  for (let i = 0; i <= n; i++) { const t = i / n, o = (i % 2 ? .5 : -.5) * amp * (.6 + vn(seed + i) * .8); out.push([lerp(x0, x1, t) + N[0] * o, lerp(y0, y1, t) + N[1] * o]); }
  return out;
}

export function humps(x0, x1, y, n, h, seed = 0) {   // «bumps»: неровная линия из дуг (пена, кусты, мыло)
  const out = [], w = (x1 - x0) / n;
  for (let i = 0; i < n; i++) {
    const a = x0 + i * w, hh = h * (.6 + vn(seed + i * .7) * .8);
    for (let k = 0; k <= 8; k++) { const t = k / 8; out.push([a + w * t, y - Math.sin(t * PI) * hh]); }
  }
  return out;
}

export function wrapV(a, lo, hi) { const s = hi - lo; return lo + (((a - lo) % s) + s) % s; }
export function lerpA(a, b, t) {   // кратчайшая интерполяция углов
  let d = wrapV(b - a, -PI, PI); return a + d * t;
}
export function mirrorPts(pts, about = 540) { return pts.map(p => [2 * about - p[0], p[1]]); }

// двухзвенная обратная кинематика: плечо S -> цель T (рука тянется к предмету)
export function ik(S, T, l1, l2, bend = 1) {
  const d = Math.min(dist(S, T), (l1 + l2) * .999);
  if (d < .0001) return [S, [S[0], S[1] + l1], T];
  const a = Math.acos(Math.max(-1, Math.min(1, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d))));
  const base = Math.atan2(T[1] - S[1], T[0] - S[0]);
  return [S, [S[0] + Math.cos(base + a * bend) * l1, S[1] + Math.sin(base + a * bend) * l1], T];
}
