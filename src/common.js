// common.js — общие кирпичи для сцен: настроения, звёзды, искры, эквалайзер, декорации.
import * as U from './util.js';
import { PAGE } from './paper.js';

export const MOODS = {
  morning: { id: 'morning', name: 'Утро',   sky: 'morning', pal: 'warm',  sunY: .34, stars: 0, light: '#f2c14e' },
  day:     { id: 'day',     name: 'День',   sky: 'day',     pal: 'bright',sunY: .22, stars: 0, light: '#f6d76b' },
  evening: { id: 'evening', name: 'Вечер',  sky: 'evening', pal: 'warm',  sunY: .52, stars: .35, light: '#e08a4a' },
  night:   { id: 'night',   name: 'Ночь',   sky: 'night',   pal: 'night', sunY: .3, stars: 1, light: '#9fb4e8' },
};

// ── небо со звёздами ────────────────────────────────────────────────────────
export function skyStars(p, t, S, o = {}) {
  const n = Math.round((o.n ?? 26) * (S.mood === 'night' ? 1.4 : S.mood === 'evening' ? .8 : .4) * S.dens);
  const R = U.mulberry(4242 + (o.seed || 0));
  for (let i = 0; i < n; i++) {
    const x = U.lerp(o.x0 ?? PAGE.x0 - 60, o.x1 ?? PAGE.x1 + 60, R()), y = U.lerp(o.y0 ?? 240, o.y1 ?? 900, R());
    const r = U.lerp(2.5, 7.5, R() ** 2), tw = .55 + .45 * Math.sin(t * (1.1 + R() * 1.6) + i);
    p.ink([[x - r, y], [x, y - r * .2], [x + r, y], [x, y + r * .2], [x - r, y]], { w: .7, role: 'accent', c: o.c, alpha: .5 * tw, smooth: .4, ...p.seq(i, o.t0 ?? 0, .05, .5) });
    if (R() < .18) p.sparkle(x, y, r * 2.1, { w: .55, role: 'accent', c: o.c, alpha: .45 * tw, ...p.seq(i, o.t0 ?? 0, .05, .5) });
  }
}

// ── искры/брызги, летящие от точки (на удар) ────────────────────────────────
export function sparkBurst(p, x, y, t, o = {}) {
  const period = o.period ?? 1.6, life = o.life ?? 1.1;
  const phase = (t - (o.t0 ?? 0)) / period;
  const k = Math.floor(phase);
  if (k < 0) return;
  const a = (phase - k) * period / life;   // 0..1 внутри жизни
  if (a > 1) return;
  const R = U.mulberry(k * 977 + (o.seed || 0));
  const n = o.n ?? 7, fade = 1 - a;
  for (let i = 0; i < n; i++) {
    const ang = R() * U.TAU, r0 = (o.r0 ?? 12) * (.5 + R()), r1 = r0 + (o.r1 ?? 90) * (.5 + R()) * U.easeOut(a);
    const px = x + Math.cos(ang) * r1, py = y + Math.sin(ang) * r1 + a * a * 14;
    p.ink([[x + Math.cos(ang) * r0, y + Math.sin(ang) * r0], [px, py]], { w: .8, role: 'accent', c: o.c, alpha: fade * .9, raw: false });
    if (R() < .3) p.sparkle(px, py, 5 * fade + 2, { w: .5, role: 'accent', c: o.c, alpha: fade });
  }
}

// ── пылинки/снежинки в воздухе (цикл) ───────────────────────────────────────
export function dust(p, t, S, o = {}) {
  const n = Math.round((o.n ?? 16) * S.dens), R = U.mulberry(818 + (o.seed || 0));
  for (let i = 0; i < n; i++) {
    const sp = 8 + R() * 16, x = U.lerp(o.x0 ?? 120, o.x1 ?? 960, R()) + Math.sin(t * .5 + i) * 26;
    const span = (o.y1 ?? 1700) - (o.y0 ?? 300);
    const y = (o.y0 ?? 300) + ((R() * span + t * sp) % span);
    p.dot(x, y, 1.6 + R() * 2.4, { role: 'accent', c: o.c, alpha: .22 + .2 * Math.sin(t + i) });
  }
}

// ── листва: кластеры из дуг ─────────────────────────────────────────────────
export function foliage(p, cx, cy, rx, ry, n, o = {}) {
  const R = U.mulberry((o.seed || 0) + 55);
  for (let i = 0; i < n; i++) {
    const a = R() * U.TAU, rr = Math.sqrt(R());
    const x = cx + Math.cos(a) * rx * rr, y = cy + Math.sin(a) * ry * rr;
    const r = U.lerp(16, 34, R()) * (o.scale ?? 1);
    const pts = [];
    const seg = 6 + Math.round(R() * 3);
    for (let k = 0; k < seg; k++) {
      const aa = k / seg * U.TAU + R() * .3;
      pts.push([x + Math.cos(aa) * r * (.7 + R() * .5), y + Math.sin(aa) * r * (.6 + R() * .4)]);
    }
    pts.push(pts[0]);
    p.shape(pts, { ...o, closeShape: true, smooth: .4, t0: (o.t0 ?? 0) + i * (o.step ?? .06), t1: (o.t0 ?? 0) + i * (o.step ?? .06) + (o.dur ?? .5) });
  }
}

// ── кусты/деревья, уезжающие за кадр (параллакс) ─────────────────────────────
export function bushes(p, t, S, o = {}) {
  const speed = o.speed ?? 60, span = (o.x1 ?? 1200) - (o.x0 ?? -120);
  const R = U.mulberry(31 + (o.seed || 0));
  const n = Math.round((o.n ?? 7) * S.dens);
  for (let i = 0; i < n; i++) {
    const base = R() * span;
    const x = (o.x0 ?? -120) + ((base - t * speed) % span + span) % span;
    const s = U.lerp(.7, 1.35, R()) * (o.scale ?? 1);
    const h = 60 * s, y = o.y ?? 1440;
    const pts = [];
    for (let k = 0; k <= 10; k++) pts.push([x - h * .9 + k / 10 * h * 1.8, y - Math.sin(k / 10 * Math.PI) * h * (.6 + R() * .3)]);
    p.shape(pts.concat([[x + h * .9, y], [x - h * .9, y]]), { ...o, closeShape: true, fill: o.fill, stroke: 'main', w: .85, smooth: .4 });
  }
}

// ── эквалайзер из штрихованных столбиков ────────────────────────────────────
export function equalizer(p, t, S, o = {}) {
  const n = o.n ?? 14, x0 = o.x0 ?? 200, x1 = o.x1 ?? 880, y = o.y ?? 1560, hMax = o.h ?? 190;
  const beat = S.beat ? S.beat(t) : (t * (S.bpm / 60)) % 1;
  for (let i = 0; i < n; i++) {
    const x = U.lerp(x0, x1, n === 1 ? .5 : i / (n - 1));
    const v = U.clamp(.25 + .75 * Math.abs(Math.sin(i * 1.7 + t * 2.2 + beat * 2)), 0, 1) * (o.gain ?? 1);
    const hh = hMax * (.25 + v * .75);
    p.shade(x - 9, y - hh, 18, hh, { ...o, spacing: 7, angle: -U.PI / 2, w: .8, t0: o.t0 ?? 0, t1: (o.t0 ?? 0) + .6 });
  }
}

// ── летящие ноты ────────────────────────────────────────────────────────────
export function notesFlying(p, t, S, o = {}) {
  const n = o.n ?? 5, R = U.mulberry(66 + (o.seed || 0));
  for (let i = 0; i < n; i++) {
    const life = 3.2, ph = ((t + i * life / n) % life) / life;
    const x = (o.x ?? 540) + Math.sin(ph * 5 + i) * (o.wob ?? 90) + (o.dx ?? 0) * ph;
    const y = (o.y ?? 1300) - ph * (o.rise ?? 620);
    p.note(x, y, (o.size ?? 34) * (.8 + R() * .4), { role: 'accent', alpha: U.clamp((1 - ph) * 1.4), t0: 0, t1: .001, color: o.color });
  }
}

// ── «нечитаемый» рукописный текст: волнистая строка ─────────────────────────
export function scribbleText(p, x, y, w, o = {}) {
  const pts = [];
  const n = Math.max(3, Math.round(w / 26));
  for (let i = 0; i <= n; i++) {
    const k = i / n, xx = x + w * k;
    pts.push([xx, y + Math.sin(k * 7 + (o.seed || 0)) * 5 + (U.vn(i * 1.3 + (o.seed || 0)) - .5) * 7]);
  }
  p.ink(pts, { ...o, w: o.w ?? .95, smooth: .6 });
}

// ── человек по суставам ─────────────────────────────────────────────────────
// J: {hip, sho, head, eL, hL, eR, hR, kL, fL, kR, fR, headR}
// Так можно посадить фигуру на велосипед, качели или уложить под одеяло.
export function person(p, J, o = {}) {
  const w = o.w ?? 1, t0 = o.t0 ?? 0, step = o.step ?? .1, dur = o.dur ?? .5;
  const seg = (i, a, b, extra = {}) => { if (a && b) p.ink([a, b], { ...o, w: (extra.w ?? 1) * w, ...p.seq(i, t0, step, dur) }); };
  const mid = (a, b, k = .5) => [U.lerp(a[0], b[0], k), U.lerp(a[1], b[1], k)];
  // дальние конечности
  seg(0, J.hip, J.kR || J.hip); seg(1, J.kR, J.fR);
  if (J.skirt) {   // платье-трапеция: от плеч до подола со фестонами
    const f = J.headR ? J.headR / .083 : 300;
    const w2 = J.skirt * (o.bell ?? 1), len = J.skirtLen ?? f * .2;
    const up = [J.sho[0] - J.hip[0], J.sho[1] - J.hip[1]];
    const nrm = Math.hypot(up[0], up[1]) || 1;
    const side = [up[1] / nrm, -up[0] / nrm];   // перпендикуляр вдоль пояса
    const off = v => [J.hip[0] + side[0] * v, J.hip[1] + side[1] * v];
    const hemL = off(-w2), hemR = off(w2);
    const path = [J.sho, [J.sho[0] + side[0] * f * .085, J.sho[1] + side[1] * f * .085],
      [J.hip[0] + side[0] * f * .09, J.hip[1] + side[1] * f * .09], hemR];
    for (let i = 1; i <= 5; i++) {   // фестоны по подолу
      const k = i / 5, xx = U.lerp(hemR[0], hemL[0], k), yy = U.lerp(hemR[1], hemL[1], k) + Math.sin(k * Math.PI * 5) * len * .08;
      path.push([xx, yy]);
    }
    path.push(hemL, [J.hip[0] - side[0] * f * .09, J.hip[1] - side[1] * f * .09], [J.sho[0] - side[0] * f * .085, J.sho[1] - side[1] * f * .085]);
    p.shape(path, { closeShape: true, fill: o.fill, stroke: 'main', w: w * 1.2, smooth: .45, ...p.seq(2, t0, step, dur), ...o });
  } else seg(2, J.hip, J.sho, { w: 1.15 });
  seg(3, J.hip, J.kL || J.hip); seg(4, J.kL, J.fL);
  // руки
  seg(5, J.sho, J.eR); seg(6, J.eR, J.hR);
  seg(7, J.sho, J.eL); seg(8, J.eL, J.hL);
  // шея, голова, лицо
  const head = J.head || [J.sho[0], J.sho[1] - (J.headR || 30) * 1.4];
  const headR = J.headR || 30;
  seg(9, J.sho, mid(J.sho, head, .72));
  p.circle(head[0], head[1], headR, { ...o, ...p.seq(9, t0, step, dur), over: .35, w: w * 1.15 });
  if (o.face !== false) {
    const eo = headR * .34, ey = head[1] - headR * .05;
    const F = p.seq(10, t0, 0, .3);
    if (o.eyes === 'closed') {
      p.ink(U.arcPts(head[0] - eo, ey, headR * .2, headR * .14, U.PI * 1.1, U.PI * 1.9, 8), { ...o, w: .7, ...F });
      p.ink(U.arcPts(head[0] + eo, ey, headR * .2, headR * .14, U.PI * 1.1, U.PI * 1.9, 8), { ...o, w: .7, ...F });
    } else { p.dot(head[0] - eo, ey, headR * .1, { ...o, ...F }); p.dot(head[0] + eo, ey, headR * .1, { ...o, ...F }); }
    if (o.mouth !== false) p.ink(U.arcPts(head[0], head[1] + headR * .3, headR * .22, headR * .16, U.PI * .15, U.PI * .85, 10), { ...o, w: .65, ...F });
  }
  // волосы прядями
  const hl = o.hairLen ?? 1.3, hq = o.hairQ ?? 4;
  for (let i = 0; i < hq; i++) {
    const a = U.PI * (.16 + i * .22), r = headR * (1 + U.vn(i * 3.7 + p.seed) * .18);
    const tip = [head[0] - Math.cos(a) * headR * hl * (.5 + i * .3) * (o.wind ?? 1), head[1] - Math.sin(a) * headR * .3 + headR * (hl * .7 + i * .12)];
    p.curve([[head[0] + Math.cos(a) * r * .7, head[1] + Math.sin(a) * r * .5], [head[0] + Math.cos(a) * r * .95, head[1] + Math.sin(a) * r * .95], tip],
      { ...o, w: .75, ...p.seq(11 + i, t0, step * .6, dur * .9) });
  }
  // ступни
  for (const [k, foot] of [[0, J.fL], [1, J.fR]]) {
    if (!foot || !o.feet) continue;
    const kn = k ? J.kR : J.kL; if (!kn) continue;
    const a = Math.atan2(foot[1] - kn[1], foot[0] - kn[0]);
    p.ink([[foot[0] - Math.cos(a) * 22, foot[1] - Math.sin(a) * 22], [foot[0] + Math.cos(a) * 20, foot[1] + Math.sin(a) * 20]], { ...o, w: w * .9, ...p.seq(12 + k, t0, step, dur) });
  }
}
