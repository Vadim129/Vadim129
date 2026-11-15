// scenes4.js — Эйси, кислотный сёрфер. Герой клипа «Beautiful Far Distance».
// Рисуется тем же пером, что остальные сцены: контур + фломастерные заливки.
// Палитра bright: 0 красный, 1 оранжевый, 2 жёлтый, 3 зелёный, 4 синий, 5 фиолет, 6 розовый.
import * as U from './util.js';
import { PAGE } from './paper.js';
import { sparkBurst, dust, equalizer, notesFlying, skyStars } from './common.js';

const TAU = U.TAU, PI = U.PI;
const INK = '#26262e';   // тёмный контур героя (поверх цветного по умолчанию)

// ── море и небо ─────────────────────────────────────────────────────────────
function seaBG(p, t, S, o = {}) {
  const hor = o.hor ?? 1180;
  if (!o.noSun) {
    const sunX = o.sunX ?? 200;
    p.sun(sunX, o.sunY ?? 430, o.sunR ?? 95, { t0: .2, t1: 1.4, c: 1, rays: 11 });
    // дорожка на воде
    for (let i = 0; i < 7; i++) {
      const y = hor + 60 + i * 62, w = 60 + i * 26 + Math.sin(t * 2 + i) * 12;
      p.ink([[sunX - w / 2, y], [sunX + w / 2, y]], { c: 1, w: 1.6, alpha: .5 - i * .05, t0: 1 + i * .1, t1: 2 + i * .1 });
    }
  }
  p.line(-30, hor, 1110, hor + 4, { w: 1.3, t0: .3, t1: 1, color: INK });
  p.waves(30, 1050, hor + 130, 16, 5, { t0: .8, t1: 2.4, c: 4, gap: 64, waves: 3 });
  p.waves(30, 1050, hor + 420, 22, 3, { t0: 1.2, t1: 2.8, c: 4, gap: 90, waves: 2 });
  for (let i = 0; i < 3; i++) {
    const bx = 650 + i * 120 + Math.sin(t * .4 + i) * 20;
    p.bird(bx, 560 + i * 60, 30, { t0: 2 + i * .3, t1: 3 + i * .3, color: INK });
  }
}

function portal(p, t, S, x, y, r, o = {}) {
  const pulse = o.pulse === false ? 0 : (S.pulse ? S.pulse(t) : 0);
  const rr = r * (1 + pulse * .04);
  p.ray(x, y, 0, TAU, rr * 1.15, rr * (1.7 + pulse * .3), 12, { c: 6, alpha: .3, t0: .4, t1: 2, step: .05 });
  for (let i = 0; i < 3; i++) {
    p.circle(x, y, rr * (1 - i * .2), { c: 6, w: 2.2 - i * .4, t0: .3 + i * .25, t1: 1.6 + i * .25 });
  }
  // дуги-«ток» по кольцу
  for (let i = 0; i < 5; i++) {
    const a0 = t * 1.4 + i * TAU / 5;
    p.ink(U.arcPts(x, y, rr * 1.02, rr * 1.02, a0, a0 + .9, 12), { c: 6, w: 1.4, alpha: .8, t0: 1.6, t1: 2 });
  }
  p.sparkle(x - rr * .7, y - rr * .8, 20, { c: 6, t0: 2, t1: 2.6 });
  p.sparkle(x + rr * .8, y + rr * .6, 16, { c: 6, t0: 2.2, t1: 2.8 });
  if (o.core !== false) p.dot(x, y, rr * .12, { c: 6, t0: 1.4, t1: 2 });
}

function towers(p, t, o = {}) {
  const hor = o.hor ?? 1180;
  const list = o.list || [[30, 700, 130, hor], [170, 560, 110, hor], [830, 600, 120, hor], [955, 740, 100, hor]];
  list.forEach((tw, i) => {
    const [x, y, w, b] = tw;
    p.shape(U.rectPts(x, y, w, b - y, 4), { closeShape: true, fill: 'fill', c: 4, fillAlpha: .35, stroke: 'main', strokeColor: INK, w: 1.2, t0: .5 + i * .2, t1: 2 + i * .2, spacing: 30 });
    p.line(x + w / 2, y - 60 - (i % 3) * 30, x + w / 2, y, { color: INK, w: 1, t0: 1 + i * .15, t1: 2 });
    p.dot(x + w / 2, y - 60 - (i % 3) * 30, 6, { c: 0, t0: 1.6, t1: 2.2 });
    // окна
    for (let wy = y + 40; wy < b - 30; wy += 64) for (let wx = x + 22; wx < x + w - 14; wx += 40) {
      if (U.hash(wx * 3.1 + wy * 7.7 + i) < .55) p.dot(wx, wy, 7, { c: 2, alpha: .85, t0: 2 + (wy - y) * .002, t1: 2.6 + (wy - y) * .002 });
    }
  });
}

function flycar(p, x, y, s, o = {}) {
  const w = 120 * s, h = 44 * s;
  p.shape(U.rectPts(x - w / 2, y - h / 2, w, h, h / 2), { closeShape: true, fill: 'fill', c: 4, fillAlpha: .5, stroke: 'main', strokeColor: INK, w: 1, t0: o.t0 ?? 2, t1: (o.t0 ?? 2) + .8 });
  p.dot(x - w * .28, y, 7 * s, { c: 2, t0: 2.4, t1: 3 });
  p.dot(x + w * .28, y, 7 * s, { c: 0, t0: 2.4, t1: 3 });
  p.ink([[x - w / 2 - 90 * s, y + 8], [x - w / 2, y + 4]], { c: 1, w: 1.6, alpha: .7, t0: 2.6, t1: 3.2 });
}

function palm(p, x, y, s, flip, o = {}) {
  const f = flip ? -1 : 1, H = 420 * s;
  p.curve([[x, y], [x + f * 60 * s, y - H * .55], [x + f * 30 * s, y - H]], { color: INK, w: 2.2, t0: o.t0 ?? .6, t1: (o.t0 ?? .6) + 1.4 });
  const tx = x + f * 30 * s, ty = y - H, sway = Math.sin((o.t ?? 0) * .9) * 8;
  for (let i = 0; i < 6; i++) {
    const a = PI * (1.08 + i * .17) * (flip ? -1 : 1) + (flip ? PI * .0 : 0);
    const len = (150 - Math.abs(i - 2.5) * 18) * s;
    const tip = [tx + Math.cos(flip ? PI - a : a) * len + sway, ty + Math.abs(Math.sin(a)) * len * .55 - 20 * s];
    p.curve([[tx, ty], [(tx + tip[0]) / 2, Math.min(ty, tip[1]) - 30 * s], tip], { color: INK, w: 1.3, ...p.seq(i, (o.t0 ?? .6) + 1, .12, .5) });
  }
  p.dot(tx - 14 * s, ty + 16 * s, 12 * s, { c: 5, t0: 2.4, t1: 3 });
  p.dot(tx + 14 * s, ty + 16 * s, 12 * s, { c: 5, t0: 2.5, t1: 3.1 });
}

// ── платформа и слизь ───────────────────────────────────────────────────────
function platform(p, cx, topY, w, o = {}) {
  const h = 120, pts = [[cx - w / 2, topY], [cx + w / 2, topY], [cx + w / 2 - 60, topY + h], [cx - w / 2 + 60, topY + h]];
  p.shape(pts, { closeShape: true, fill: 'fill', c: 4, fillAlpha: .4, stroke: 'main', strokeColor: INK, w: 1.8, smooth: .3, t0: o.t0 ?? 1, t1: (o.t0 ?? 1) + 1.4, spacing: 34 });
  for (let i = 1; i < 5; i++) {
    const x = cx - w / 2 + (w * i) / 5;
    p.line(x, topY + 8, x - 12, topY + h - 8, { color: INK, w: .9, alpha: .8, t0: 2, t1: 3 });
  }
  for (let i = 0; i < 4; i++) p.dot(cx - w / 2 + 90 + i * ((w - 180) / 3), topY + h / 2, 8, { c: 2, t0: 2.4 + i * .1, t1: 3 + i * .1 });
  if (o.slime !== false) slime(p, cx, topY, w, o);
}

function slime(p, cx, y, w, o = {}) {
  const R = U.mulberry(900 + Math.round(cx));
  for (let i = 0; i < 5; i++) {
    const bx = cx - w / 2 + 60 + R() * (w - 120), br = 26 + R() * 44;
    p.shape(U.cloudPts(bx, y - 6, br, i * 7 + 1), { closeShape: true, fill: 'fill', c: 3, stroke: 'main', cStroke: 3, color: undefined, w: 1, smooth: .5, t0: 2 + i * .15, t1: 3.2 + i * .15 });
    if (R() < .7) {
      const dl = 40 + R() * 70;
      p.ink(U.wobbleLine(bx + (R() - .5) * 30, y + 4, bx + (R() - .5) * 30, y + dl, 4, i * 3, 6), { c: 3, w: 1.6, t0: 2.6 + i * .12, t1: 3.4 + i * .12 });
      p.dot(bx, y + dl + 8, 7, { c: 3, t0: 3 + i * .12, t1: 3.5 + i * .12 });
    }
  }
}

// ── робот ───────────────────────────────────────────────────────────────────
function robot(p, t, x, feetY, s, o = {}) {
  const dance = o.dance ? (S_pulse(o, t)) : 0;
  const bob = Math.sin(t * (o.dance ? 4.4 : 1.3)) * (o.dance ? 16 : 6) * s - dance * 10;
  const bw = 150 * s, bh = 170 * s, by = feetY - 60 * s + bob;
  // ноги-тумбы
  for (const sd of [-1, 1]) {
    p.shape(U.rectPts(x + sd * 44 * s - 26 * s, by, 52 * s, 60 * s, 8), { closeShape: true, fill: 'fill', c: 4, fillAlpha: .5, stroke: 'main', strokeColor: INK, w: 1.1, t0: 1.4, t1: 2.4 });
  }
  // тело
  p.shape(U.rectPts(x - bw / 2, by - bh, bw, bh, 18), { closeShape: true, fill: 'fill', c: 4, fillAlpha: .45, stroke: 'main', strokeColor: INK, w: 1.5, t0: 1.2, t1: 2.4, spacing: 26 });
  // экран-лицо
  const sw = 104 * s, sh = 80 * s, sy = by - bh + 34 * s;
  p.shape(U.rectPts(x - sw / 2, sy, sw, sh, 14), { closeShape: true, fill: 'fill', c: 3, fillAlpha: .8, stroke: 'main', strokeColor: INK, w: 1.2, t0: 1.8, t1: 2.8 });
  const blink = (t % 3.7) < .14 ? .2 : 1;
  p.dot(x - 24 * s, sy + sh * .38, 8 * s * blink + 1, { color: INK, t0: 2.2, t1: 2.6 });
  p.dot(x + 24 * s, sy + sh * .38, 8 * s * blink + 1, { color: INK, t0: 2.2, t1: 2.6 });
  p.ink(U.arcPts(x, sy + sh * .42, 30 * s, 22 * s, PI * .15, PI * .85, 12), { color: INK, w: 1.2, t0: 2.4, t1: 3 });
  // антенна
  p.line(x, by - bh, x, by - bh - 60 * s, { color: INK, w: 1.1, t0: 2, t1: 2.6 });
  p.dot(x, by - bh - 66 * s, 8 * s, { c: 0, alpha: .5 + .5 * Math.sin(t * 5), t0: 2.2, t1: 2.6 });
  // руки
  const wave = o.wave ? Math.sin(t * 5) * .5 : 0;
  const aL = -2.4 + (o.dance ? Math.sin(t * 4.4) * .7 : 0), aR = .5 + wave + (o.dance ? -Math.sin(t * 4.4) * .7 : 0);
  for (const [sd, a] of [[-1, aL], [1, aR]]) {
    const sx = x + sd * bw / 2, shy = by - bh + 70 * s;
    const ex = sx + Math.sin(a) * 90 * s, ey = shy + Math.cos(a) * 90 * s;
    p.line(sx, shy, ex, ey, { color: INK, w: 1.6, t0: 2, t1: 3 });
    p.circle(ex, ey, 16 * s, { color: INK, w: 1.1, t0: 2.2, t1: 3 });
  }
}
function S_pulse(o, t) { return o.S && o.S.pulse ? o.S.pulse(t) : 0; }

// ── герой ───────────────────────────────────────────────────────────────────
// feetY — ступни; s — масштаб; позы: stand (fist up/down), sit, fly.
function surfer(p, t, S, x, feetY, s, o = {}) {
  const dark = o.dark;   // силуэт для сцены света
  const C = c => (dark ? INK : undefined);   // цвет контура
  const F = c => (dark ? { c: undefined, color: INK, fillAlpha: .85 } : { c });  // заливка
  const dy = o.dy ?? 0, lean = o.lean ?? 0;
  const X = y => x + lean * (feetY - y) * .12;
  const hipY = feetY - 430 * s + dy, shoY = hipY - 330 * s, shoX = X(shoY);
  const lw = 74 * s;   // ширина ноги
  // ноги
  for (const sd of [-1, 1]) {
    const lx = X(hipY) + sd * 78 * s;
    p.shape([[lx - lw / 2, hipY], [lx + lw / 2, hipY], [lx + lw * .32, feetY - 40 * s + dy], [lx - lw * .32, feetY - 40 * s + dy]],
      { closeShape: true, fill: 'fill', ...F(1), fillAlpha: dark ? .85 : .45, stroke: 'main', strokeColor: INK, w: 1.4, smooth: .3, t0: 1.2, t1: 2.6, spacing: 24 });
    p.ellipse(lx, feetY - 22 * s + dy, 52 * s, 24 * s, { color: C() || INK, w: 1.2, t0: 1.6, t1: 2.6 });
  }
  // шорты
  const shT = hipY - 50 * s, shB = hipY + 200 * s, shW = 310 * s;
  p.shape([[X(shT) - shW / 2, shT], [X(shT) + shW / 2, shT], [X(shB) + shW * .42, shB], [X(shB), shB - 60 * s], [X(shB) - shW * .42, shB]],
    { closeShape: true, fill: 'fill', ...F(5), stroke: 'main', strokeColor: INK, w: 1.6, smooth: .3, t0: 1.5, t1: 3, spacing: 30 });
  if (!dark) for (const sd of [-1, 1]) {   // пальмы на шортах
    const px = X(shT + 120 * s) + sd * 80 * s, py = shT + 120 * s;
    p.line(px, py + 34 * s, px, py - 10 * s, { color: INK, w: .9, t0: 3, t1: 3.6 });
    for (let i = 0; i < 4; i++) {
      const a = PI * (1.1 + i * .22);
      p.ink([[px, py - 8 * s], [px + Math.cos(a) * 34 * s, py - 8 * s - Math.abs(Math.sin(a)) * 26 * s]], { color: INK, w: .8, t0: 3.1 + i * .06, t1: 3.6 + i * .06 });
    }
  }
  // футболка
  const tT = shoY - 30 * s, tB = hipY + 30 * s, tW = 360 * s;
  p.shape([[X(tT) - tW / 2, tT], [X(tT) + tW / 2, tT], [X(tB) + tW * .44, tB], [X(tB) - tW * .44, tB]],
    { closeShape: true, ...(dark ? { fill: 'fill', color: INK, fillAlpha: .85 } : {}), stroke: 'main', strokeColor: INK, w: 1.7, smooth: .3, t0: 1.8, t1: 3.2 });
  if (!dark) {
    p.text('ACID', X(tT + 130 * s), tT + 120 * s, { size: 72 * s, align: 'center', c: 0, t0: 3.4, t1: 4.4 });
    p.text('CRUNCH', X(tT + 200 * s), tT + 195 * s, { size: 56 * s, align: 'center', c: 0, t0: 3.7, t1: 4.7 });
  }
  // робо-руки
  const armW = 66 * s;
  const arm = (sd, kind) => {
    const sx = shoX + sd * (tW / 2 - 20 * s), sy = shoY + 60 * s;
    let ex, ey, hx, hy;
    if (kind === 'up') { ex = sx + sd * 120 * s; ey = sy - 150 * s; hx = sx + sd * 150 * s; hy = sy - 330 * s; }
    else { ex = sx + sd * 70 * s; ey = sy + 170 * s; hx = sx + sd * 90 * s; hy = sy + 350 * s; }
    const segm = (ax, ay, bx, by) => {
      const d = U.nrm([bx - ax, by - ay]), n = [-d[1], d[0]];
      p.shape([[ax + n[0] * armW / 2, ay + n[1] * armW / 2], [bx + n[0] * armW / 2, by + n[1] * armW / 2],
        [bx - n[0] * armW / 2, by - n[1] * armW / 2], [ax - n[0] * armW / 2, ay - n[1] * armW / 2]],
        { closeShape: true, fill: 'fill', ...F(3), fillAlpha: dark ? .85 : .6, stroke: 'main', strokeColor: INK, w: 1.3, t0: 2.2, t1: 3.4, spacing: 20 });
    };
    segm(sx, sy, ex, ey); segm(ex, ey, hx, hy);
    p.circle(sx, sy, 44 * s, { color: C() || INK, w: 1.2, t0: 2.6, t1: 3.4 });
    p.circle(ex, ey, 40 * s, { color: C() || INK, w: 1.2, t0: 2.8, t1: 3.6 });
    // кулак
    p.shape(U.cloudPts(hx, hy + (kind === 'up' ? -30 * s : 30 * s), 52 * s, sd * 5 + 2), { closeShape: true, fill: 'fill', ...F(3), fillAlpha: dark ? .85 : .6, stroke: 'main', strokeColor: INK, w: 1.3, t0: 3, t1: 4 });
    if (!dark && kind === 'down') for (let i = 0; i < 3; i++) p.line(hx - 30 * s + i * 30 * s, hy + 40 * s, hx - 30 * s + i * 30 * s, hy + 66 * s, { color: INK, w: .9, t0: 3.4, t1: 4 });
    return [hx, hy];
  };
  const fistR = arm(1, o.fist || 'up');
  arm(-1, 'down');
  // цепь
  if (!dark) {
    const cy = shoY + 10 * s;
    for (let i = 0; i <= 10; i++) {
      const k = i / 10, cx = shoX - 70 * s + k * 140 * s;
      p.dot(cx, cy + Math.sin(k * PI) * 44 * s, 7 * s, { c: 4, t0: 3.2 + i * .05, t1: 3.8 + i * .05 });
    }
  }
  // голова
  const hr = 100 * s, hx = X(shoY - 150 * s), hy = shoY - 150 * s + dy * .5;
  p.line(shoX, shoY - 20 * s, hx, hy + hr * .8, { color: C() || INK, w: 1.4, t0: 2.4, t1: 3.2 });
  if (!dark) {   // волосы сзади
    p.shape(U.cloudPts(hx, hy + 30 * s, hr * 1.35, 9), { closeShape: true, fill: 'fill', c: 2, fillAlpha: .7, stroke: false, t0: 2.2, t1: 3.4 });
  }
  p.circle(hx, hy, hr, { color: C() || INK, w: 1.6, t0: 2.4, t1: 3.4, ...(dark ? {} : { fill: 'fill', c: 1, fillAlpha: .45 }) });
  if (!dark) {
    // кепка задом наперёд
    p.shape(U.arcPts(hx, hy - hr * .28, hr * 1.02, hr * .8, PI * 1.02, PI * 1.98, 20), { closeShape: true, fill: 'fill', c: 1, stroke: 'main', strokeColor: INK, w: 1.3, t0: 3, t1: 4 });
    p.shape([[hx + hr * .7, hy - hr * .9], [hx + hr * 1.7, hy - hr * 1.25], [hx + hr * 1.65, hy - hr * .85], [hx + hr * .75, hy - hr * .5]],
      { closeShape: true, fill: 'fill', c: 1, stroke: 'main', strokeColor: INK, w: 1.1, t0: 3.2, t1: 4.1 });
    p.dot(hx, hy - hr * 1.05, 10 * s, { c: 0, t0: 3.6, t1: 4 });
    // очки-визор: широкая линза-эллипс
    p.shape(U.circlePts(hx, hy - hr * .02, hr * 1.0, hr * .34, 4), { closeShape: true, fill: 'fill', c: 4, fillAlpha: .45, stroke: false, t0: 3.2, t1: 4.2 });
    p.ellipse(hx, hy - hr * .02, hr * 1.0, hr * .34, { color: INK, w: 1.4, t0: 3.4, t1: 4.4 });
    p.dot(hx - hr * .45, hy - hr * .12, hr * .07, { c: 2, t0: 3.8, t1: 4.4 });
    // улыбка
    p.ink(U.arcPts(hx, hy + hr * .42, hr * .34, hr * .24, PI * .12, PI * .88, 14), { color: INK, w: 1.2, t0: 4, t1: 4.8 });
  }
  return { head: [hx, hy], headR: hr, fist: fistR };
}

// ── СЦЕНЫ ───────────────────────────────────────────────────────────────────

// 1 — стойка на платформе, постер
const surf_stand = {
  id: 'surf_stand', name: 'Сёрфер: стойка', tags: ['сёрфер', 'энергия'], dur: 14,
  draw(p, t, S) {
    seaBG(p, t, S, {});
    portal(p, t, S, 850, 360, 105, {});
    towers(p, t, {});
    flycar(p, 300 + Math.sin(t * .3) * 30, 640, .9, {});
    palm(p, 70, 1120, 1.25, false, { t }); palm(p, 1010, 1080, 1.0, true, { t });
    const bob = Math.sin(t * 1.2) * 10;
    platform(p, 540, 1600 + bob, 780, {});
    robot(p, t, 250, 1600 + bob, .8, { wave: true });
    const H = surfer(p, t, S, 550, 1600 + bob, .85, { fist: 'up', dy: 0 });
    const pu = S.pulse ? S.pulse(t) : 0;
    if (pu > .72 && t > 4) sparkBurst(p, H.fist[0], H.fist[1], t, { n: 6, r1: 70, period: 99, t0: 4, c: 2 });
    dust(p, t, S, { n: 12, y0: 300, y1: 1200, c: 4 });
  },
};

// 2 — отжимания: цикл вверх-вниз
const surf_push = {
  id: 'surf_push', name: 'Сёрфер: отжимания', tags: ['сёрфер', 'энергия'], dur: 12,
  draw(p, t, S) {
    seaBG(p, t, S, { sunX: 860 });
    portal(p, t, S, 200, 400, 90, {});
    towers(p, t, { list: [[830, 640, 120, 1180], [955, 760, 100, 1180]] });
    palm(p, 70, 1120, 1.1, false, { t });
    const py = 1640;
    platform(p, 540, py, 880, {});
    const ph = (t * .55) % 1, lift = Math.sin(ph * TAU) * 55;   // тело ходит вверх-вниз
    const hip = [680, 1330 + lift], sho = [420, 1290 + lift], head = [305, 1220 + lift];
    const hand = [450, py - 8], foot = [890, py - 10];
    // конечность объёмным сегментом
    const limb = (ax, ay, bx, by, wdt, cFill, alpha, t0) => {
      const d = U.nrm([bx - ax, by - ay]), n = [-d[1], d[0]];
      p.shape([[ax + n[0] * wdt / 2, ay + n[1] * wdt / 2], [bx + n[0] * wdt / 2, by + n[1] * wdt / 2],
        [bx - n[0] * wdt / 2, by - n[1] * wdt / 2], [ax - n[0] * wdt / 2, ay - n[1] * wdt / 2]],
        { closeShape: true, fill: 'fill', c: cFill, fillAlpha: alpha, stroke: 'main', strokeColor: INK, w: 1.2, t0, t1: t0 + 1, spacing: 18 });
    };
    // дальние рука и нога (тоньше, за телом)
    const el2 = U.ik([sho[0] + 30, sho[1]], [hand[0] + 30, hand[1]], 170, 170, 1)[1];
    limb(sho[0] + 30, sho[1], el2[0], el2[1], 52, 3, .45, 1.8);
    limb(el2[0], el2[1], hand[0] + 30, hand[1], 52, 3, .45, 1.8);
    limb(hip[0], hip[1] + 34, foot[0], foot[1], 56, 1, .35, 1.6);
    // ноги
    limb(hip[0], hip[1], foot[0], foot[1], 72, 1, .45, 1.6);
    p.ellipse(foot[0], foot[1] - 6, 48, 22, { color: INK, w: 1.2, t0: 2, t1: 3 });
    // шорты
    p.shape([[hip[0] - 130, hip[1] - 95], [hip[0] + 125, hip[1] - 85], [hip[0] + 105, hip[1] + 95], [hip[0] - 110, hip[1] + 95]],
      { closeShape: true, fill: 'fill', c: 5, stroke: 'main', strokeColor: INK, w: 1.6, t0: 1.8, t1: 3, spacing: 26 });
    // спина-футболка
    const back = [[sho[0] - 60, sho[1] - 90], [hip[0] + 80, hip[1] - 90], [hip[0] + 80, hip[1] + 80], [sho[0] - 60, sho[1] + 80]];
    p.shape(back, { closeShape: true, stroke: 'main', strokeColor: INK, w: 1.8, smooth: .3, t0: 2, t1: 3.2 });
    p.text('ACID', (sho[0] + hip[0]) / 2 + 10, sho[1] + 30, { size: 60, align: 'center', c: 0, t0: 3.2, t1: 4.2 });
    // ближняя робо-рука: плечо→локоть→кисть
    const el = U.ik(sho, hand, 170, 170, 1)[1];
    limb(sho[0], sho[1], el[0], el[1], 66, 3, .6, 2.2);
    limb(el[0], el[1], hand[0], hand[1], 66, 3, .6, 2.2);
    p.circle(sho[0], sho[1], 40, { color: INK, w: 1.2, t0: 2.6, t1: 3.4 });
    p.circle(el[0], el[1], 36, { color: INK, w: 1.2, t0: 2.6, t1: 3.4 });
    p.shape(U.cloudPts(hand[0], hand[1], 44, 3), { closeShape: true, fill: 'fill', c: 3, fillAlpha: .6, stroke: 'main', strokeColor: INK, w: 1.2, t0: 2.8, t1: 3.6 });
    // голова + кепка + очки
    p.shape(U.circlePts(head[0], head[1], 82, 82, 6), { closeShape: true, fill: 'fill', c: 1, fillAlpha: .45, stroke: false, t0: 2.2, t1: 3.2 });
    p.circle(head[0], head[1], 82, { color: INK, w: 1.5, t0: 2.4, t1: 3.4 });
    p.shape(U.arcPts(head[0], head[1] - 22, 84, 64, PI * 1.02, PI * 1.98, 18), { closeShape: true, fill: 'fill', c: 1, stroke: 'main', strokeColor: INK, w: 1.2, t0: 3, t1: 4 });
    p.ellipse(head[0] - 10, head[1] + 2, 62, 24, { color: INK, w: 1.1, t0: 3.2, t1: 4 });
    p.ink(U.arcPts(head[0], head[1] + 38, 26, 18, PI * .15, PI * .85, 10), { color: INK, w: 1.1, t0: 3.4, t1: 4 });
    // дуги движения над спиной
    for (let i = 0; i < 3; i++) {
      p.ink(U.arcPts(560, 1290 + lift, 150 + i * 44, 90 + i * 30, PI * 1.15, PI * 1.85, 16), { c: 3, w: 1, alpha: .5, t0: 3.6 + i * .1, t1: 4.4 });
    }
    // счёт повторов
    const reps = Math.floor(t * .55) + 1;
    if (t > 4) p.text('×' + reps, 880, 1120, { size: 76, align: 'center', c: 3, t0: 4, t1: 4.2 });
    slime(p, 180, py, 300, {});
  },
};

// 3 — лицо крупно, в очках портал
const surf_face = {
  id: 'surf_face', name: 'Сёрфер: взгляд', tags: ['сёрфер', 'спокойное'], dur: 12,
  draw(p, t, S) {
    // закатные полосы
    for (let i = 0; i < 6; i++) {
      const y = 260 + i * 90;
      p.ink(U.wobbleLine(60, y, 1020, y + 10, 8, i * 7, 12), { c: i % 2 ? 1 : 0, w: 2.4, alpha: .35, t0: .2 + i * .12, t1: 1.4 + i * .12 });
    }
    portal(p, t, S, 850, 330, 90, {});
    const hx = 540, hy = 1050, hr = 300;
    p.shape(U.cloudPts(hx, hy + 60, hr * 1.3, 4), { closeShape: true, fill: 'fill', c: 2, fillAlpha: .7, stroke: false, t0: .8, t1: 2.2 });
    p.shape(U.circlePts(hx, hy, hr, hr, 7), { closeShape: true, fill: 'fill', c: 1, fillAlpha: .45, stroke: false, t0: .8, t1: 2.2 });
    p.circle(hx, hy, hr, { color: INK, w: 2, t0: 1, t1: 2.4 });
    // кепка
    p.shape(U.arcPts(hx, hy - hr * .3, hr * 1.02, hr * .82, PI * 1.02, PI * 1.98, 24), { closeShape: true, fill: 'fill', c: 1, stroke: 'main', strokeColor: INK, w: 1.6, t0: 1.8, t1: 3 });
    p.shape([[hx + hr * .7, hy - hr * .95], [hx + hr * 1.32, hy - hr * 1.12], [hx + hr * 1.28, hy - hr * .78], [hx + hr * .75, hy - hr * .55]],
      { closeShape: true, fill: 'fill', c: 1, stroke: 'main', strokeColor: INK, w: 1.3, t0: 2.2, t1: 3.4 });
    // очки с отражением портала
    p.shape(U.circlePts(hx, hy + hr * .02, hr * 1.0, hr * .32, 5), { closeShape: true, fill: 'fill', c: 4, fillAlpha: .45, stroke: false, t0: 2.2, t1: 3.4 });
    p.ellipse(hx, hy + hr * .02, hr * 1.0, hr * .32, { color: INK, w: 1.8, t0: 2.4, t1: 3.6 });
    for (const sd of [-1, 1]) {
      p.circle(hx + sd * hr * .5, hy + hr * .02, hr * .15, { c: 6, w: 1.4, t0: 3, t1: 4 });
      p.dot(hx + sd * hr * .5, hy + hr * .02, hr * .045, { c: 6, t0: 3.2, t1: 4 });
    }
    p.ink(U.arcPts(hx, hy + hr * .44, hr * .3, hr * .2, PI * .12, PI * .88, 14), { color: INK, w: 1.4, t0: 3.4, t1: 4.4 });
    // цепь снизу
    for (let i = 0; i <= 12; i++) {
      const k = i / 12, cx = hx - 200 + k * 400;
      p.dot(cx, hy + hr + 60 + Math.sin(k * PI) * 70, 10, { c: 4, t0: 4 + i * .05, t1: 4.6 + i * .05 });
    }
    p.text('beautiful far distance', 540, 1780, { size: 56, align: 'center', c: 6, t0: 5, t1: 6.6, underline: true });
  },
};

// 4 — далёкий портал, широкий план
const surf_horizon = {
  id: 'surf_horizon', name: 'Сёрфер: горизонт', tags: ['сёрфер', 'спокойное'], dur: 12,
  draw(p, t, S) {
    seaBG(p, t, S, { hor: 1120, sunX: 540, sunY: 880, sunR: 110 });
    portal(p, t, S, 800, 480, 190, {});
    towers(p, t, { hor: 1120, list: [[40, 760, 120, 1120], [880, 700, 120, 1120]] });
    flycar(p, 250 + Math.sin(t * .25) * 40, 700, .8, {});
    // крошечный сёрфер на платформе
    const sx = 540 + Math.sin(t * .3) * 24, sy = 1290 + Math.sin(t * 1.1) * 8;
    p.shape([[sx - 90, sy], [sx + 90, sy], [sx + 70, sy + 34], [sx - 70, sy + 34]], { closeShape: true, fill: 'fill', c: 4, fillAlpha: .5, stroke: 'main', strokeColor: INK, w: 1.1, t0: 2, t1: 3 });
    p.line(sx, sy - 110, sx, sy, { color: INK, w: 2, t0: 2.2, t1: 3.2 });
    p.circle(sx, sy - 140, 26, { color: INK, w: 1.1, t0: 2.4, t1: 3.2 });
    p.line(sx, sy - 90, sx - 44, sy - 140, { color: INK, w: 1.6, t0: 2.6, t1: 3.4 });
    p.dot(sx, sy - 6, 8, { c: 3, t0: 3, t1: 3.6 });
    palm(p, 80, 1120, 1.1, false, { t }); palm(p, 1000, 1120, 1.1, true, { t });
    skyStars(p, t, S, { n: 14, y1: 700, t0: 3, c: 2 });
  },
};

// 5 — на гребне волны
const surf_wave = {
  id: 'surf_wave', name: 'Сёрфер: волна', tags: ['сёрфер', 'энергия'], dur: 13,
  draw(p, t, S) {
    p.sun(180, 330, 80, { t0: .2, t1: 1.2, c: 1, rays: 10 });
    portal(p, t, S, 880, 330, 85, {});
    // гигантская волна справа
    const wx = 760;
    p.shape(U.catmull([[wx - 420, 1920], [wx - 380, 1300], [wx - 200, 950], [wx + 120, 820], [wx + 260, 950], [wx + 200, 1150], [wx + 40, 1100], [wx + 60, 1300], [wx - 100, 1600], [wx - 160, 1920]], 10, false),
      { closeShape: true, fill: 'fill', c: 4, fillAlpha: .55, stroke: 'main', strokeColor: INK, w: 1.8, smooth: .5, t0: .6, t1: 2.4, spacing: 40 });
    p.ink(U.humps(wx - 360, wx + 220, 970, 9, 34, 3), { w: 1.6, t0: 1.6, t1: 2.8, c: 4 });
    p.ink(U.humps(wx - 300, wx + 180, 1120, 7, 26, 8), { w: 1.3, t0: 2, t1: 3.2, c: 4 });
    // герой на склоне
    const ry = 1450 + Math.sin(t * 1.6) * 22;
    p.shape([[430, ry], [700, ry - 60], [680, ry - 10], [410, ry + 50]], { closeShape: true, fill: 'fill', c: 4, fillAlpha: .5, stroke: 'main', strokeColor: INK, w: 1.4, t0: 2, t1: 3 });
    surfer(p, t, S, 560, ry - 10, .62, { fist: 'up', lean: .5 });
    // брызги и скорость
    for (let i = 0; i < 10; i++) {
      const sx = 180 + U.hash(i * 3.3) * 500, sy = 900 + ((U.hash(i * 7.7) * 800 + t * 260) % 800);
      p.dot(sx, sy, 5 + U.hash(i) * 7, { c: 4, alpha: .7, t0: 2.4, t1: 3 });
    }
    for (let i = 0; i < 6; i++) {
      const y = 1250 + i * 90;
      p.ink([[60, y], [330, y - 30]], { c: 1, w: 1.4, alpha: .6, t0: 3 + i * .1, t1: 4 + i * .1 });
    }
    const pu = S.pulse ? S.pulse(t) : 0;
    if (pu > .7 && t > 4) sparkBurst(p, 560, 900, t, { n: 7, r1: 90, period: 99, t0: 4, c: 2 });
  },
};

// 6 — полёт к башням
const surf_fly = {
  id: 'surf_fly', name: 'Сёрфер: полёт', tags: ['сёрфер', 'энергия'], dur: 13,
  draw(p, t, S) {
    // облака несутся мимо
    for (let i = 0; i < 4; i++) {
      const cx = U.wrapV(1200 - t * (140 + i * 60) + i * 300, -300, 1400);
      p.cloud(cx, 400 + i * 260, 90 - i * 8, { t0: .2, t1: 1.2, seed: i * 3, alpha: .8, color: INK });
    }
    portal(p, t, S, 830, 420, 120, {});
    // башни внизу едут назад
    for (let i = 0; i < 3; i++) {
      const bx = U.wrapV(1100 - t * 120 + i * 420, -260, 1300);
      p.shape(U.rectPts(bx, 1450, 150, 470, 6), { closeShape: true, fill: 'fill', c: 4, fillAlpha: .35, stroke: 'main', strokeColor: INK, w: 1.2, t0: .6, t1: 1.6, spacing: 30 });
      for (let wy = 1500; wy < 1880; wy += 70) p.dot(bx + 40 + (wy % 2) * 60, wy, 7, { c: 2, t0: 1.4, t1: 2 });
    }
    p.line(-20, 1450, 1100, 1454, { color: INK, w: 1.3, t0: .4, t1: 1.2 });
    const bob = Math.sin(t * 1.8) * 18;
    p.shape([[380, 1080 + bob], [700, 1040 + bob], [660, 1100 + bob], [340, 1140 + bob]], { closeShape: true, fill: 'fill', c: 4, fillAlpha: .5, stroke: 'main', strokeColor: INK, w: 1.4, t0: 1.6, t1: 2.6 });
    surfer(p, t, S, 530, 1080 + bob, .68, { fist: 'up', lean: .35 });
    flycar(p, U.wrapV(900 - t * 90, -200, 1300), 700, .75, {});
    flycar(p, U.wrapV(300 - t * 130, -200, 1300), 1300, .6, {});
    for (let i = 0; i < 8; i++) {
      const y = 500 + i * 130, x = U.wrapV(1100 - t * 420 + i * 160, -200, 1300);
      p.ink([[x, y], [x + 130, y - 8]], { c: 1, w: 1.2, alpha: .5, t0: 2.4, t1: 3 });
    }
  },
};

// 7 — робот танцует
const surf_bot = {
  id: 'surf_bot', name: 'Сёрфер: робот', tags: ['сёрфер', 'энергия'], dur: 11,
  draw(p, t, S) {
    equalizer(p, t, S, { x0: 150, x1: 930, y: 620, h: 260, n: 14, t0: .4, c: 3 });
    notesFlying(p, t, S, { x: 230, y: 950, n: 3, rise: 520 });
    notesFlying(p, t, S, { x: 850, y: 950, n: 3, rise: 520 });
    platform(p, 540, 1560, 800, {});
    robot(p, t, 540, 1560, 1.7, { dance: true, S });
    // ноги героя сбоку
    for (const dx of [-330, -250]) {
      p.shape([[540 + dx - 36, 1180], [540 + dx + 36, 1180], [540 + dx + 24, 1560], [540 + dx - 24, 1560]],
        { closeShape: true, fill: 'fill', c: 1, fillAlpha: .45, stroke: 'main', strokeColor: INK, w: 1.3, t0: 2.6, t1: 4 });
    }
    p.text('кислота!', 540, 750, { size: 84, align: 'center', c: 3, t0: 4, t1: 5.4, underline: true });
  },
};

// 8 — тихий закат, сидит
const surf_rest = {
  id: 'surf_rest', name: 'Сёрфер: отдых', tags: ['сёрфер', 'спокойное'], dur: 12,
  draw(p, t, S) {
    seaBG(p, t, S, { hor: 1220, sunX: 540, sunY: 1000, sunR: 120 });
    palm(p, 90, 1220, 1.2, false, { t }); palm(p, 990, 1220, 1.2, true, { t });
    const py = 1600 + Math.sin(t * 1.1) * 8;
    platform(p, 540, py, 820, {});
    // сидящий: бедро горизонтально, голень вниз, рука на колене
    const hx = 430, hy = py - 300, lean = Math.sin(t * .5) * 6;
    p.shape([[hx - 150, hy - 40], [hx + 150, hy - 40], [hx + 150, hy + 60], [hx - 150, hy + 60]], { closeShape: true, fill: 'fill', c: 1, fillAlpha: .45, stroke: 'main', strokeColor: INK, w: 1.4, t0: 1.6, t1: 3 });
    for (const sd of [-1, 1]) {
      p.shape([[hx + sd * 120 - 36, hy - 30], [hx + sd * 120 + 36, hy - 30], [hx + sd * 120 + 20, py - 30], [hx + sd * 120 - 20, py - 30]],
        { closeShape: true, fill: 'fill', c: 1, fillAlpha: .45, stroke: 'main', strokeColor: INK, w: 1.3, t0: 2, t1: 3.2 });
      p.ellipse(hx + sd * 120, py - 22, 52, 22, { color: INK, w: 1.1, t0: 2.4, t1: 3.2 });
    }
    // шорты поверх бедра
    p.shape([[hx - 165, hy - 150], [hx + 165, hy - 150], [hx + 160, hy + 10], [hx - 160, hy + 10]],
      { closeShape: true, fill: 'fill', c: 5, stroke: 'main', strokeColor: INK, w: 1.4, t0: 2, t1: 3.2, spacing: 24 });
    // торс уже, с надписью
    p.shape([[hx - 95 + lean, hy - 330], [hx + 95 + lean, hy - 330], [hx + 130, hy - 120], [hx - 130, hy - 120]],
      { closeShape: true, stroke: 'main', strokeColor: INK, w: 1.6, smooth: .3, t0: 2.2, t1: 3.4 });
    p.text('ACID', hx + lean, hy - 190, { size: 46, align: 'center', c: 0, t0: 3.4, t1: 4.4 });
    // шея
    p.shape([[hx + lean - 28, hy - 400], [hx + lean + 28, hy - 400], [hx + lean + 28, hy - 320], [hx + lean - 28, hy - 320]],
      { closeShape: true, fill: 'fill', c: 1, fillAlpha: .45, stroke: 'main', strokeColor: INK, w: 1.1, t0: 2.4, t1: 3.2 });
    // голова в кепке, смотрит вдаль
    const hr = 88, hyy = hy - 430;
    p.shape(U.circlePts(hx + lean, hyy, hr, hr, 8), { closeShape: true, fill: 'fill', c: 1, fillAlpha: .45, stroke: false, t0: 2.4, t1: 3.4 });
    p.circle(hx + lean, hyy, hr, { color: INK, w: 1.5, t0: 2.6, t1: 3.6 });
    p.shape(U.arcPts(hx + lean, hyy - hr * .25, hr * 1.02, hr * .8, PI * 1.02, PI * 1.98, 20), { closeShape: true, fill: 'fill', c: 1, stroke: 'main', strokeColor: INK, w: 1.2, t0: 3, t1: 4 });
    p.ink(U.arcPts(hx + lean + 20, hyy + 10, 40, 26, PI * .1, PI * .9, 10), { color: INK, w: 1, t0: 3.4, t1: 4 });
    // рука объёмно лежит на колене
    const sax = hx + 80 + lean, say = hy - 250, hax = hx + 150, hay = hy - 50;
    const dd = U.nrm([hax - sax, hay - say]), nn = [-dd[1], dd[0]];
    p.shape([[sax + nn[0] * 30, say + nn[1] * 30], [hax + nn[0] * 30, hay + nn[1] * 30], [hax - nn[0] * 30, hay - nn[1] * 30], [sax - nn[0] * 30, say - nn[1] * 30]],
      { closeShape: true, fill: 'fill', c: 3, fillAlpha: .6, stroke: 'main', strokeColor: INK, w: 1.2, t0: 3, t1: 4, spacing: 18 });
    p.circle(hax, hay, 30, { color: INK, w: 1.2, t0: 3.2, t1: 4 });
    robot(p, t, 830, py, .7, {});
    skyStars(p, t, S, { n: 16, y1: 800, t0: 4, c: 2 });
    p.text('тихо...', 540, 480, { size: 72, align: 'center', c: 4, t0: 5, t1: 6.4 });
  },
};

// 9 — внутри света, кульминация
const surf_light = {
  id: 'surf_light', name: 'Сёрфер: свет', tags: ['сёрфер', 'энергия'], dur: 13,
  draw(p, t, S) {
    const e = S.energy ? S.energy(t) : .8;
    // портал на весь кадр
    p.ray(540, 900, 0, TAU, 200, 700 + e * 260, 16, { c: 6, alpha: .3 + e * .2, t0: .2, t1: 1.6, step: .04 });
    for (let i = 0; i < 4; i++) p.circle(540, 900, 560 - i * 120, { c: 6, w: 2.4 - i * .3, t0: .3 + i * .2, t1: 1.8 + i * .2 });
    for (let i = 0; i < 8; i++) {
      const a0 = t * (1 + e) + i * TAU / 8;
      p.ink(U.arcPts(540, 900, 430, 430, a0, a0 + 1.1, 14), { c: 6, w: 2, alpha: .85, t0: 1.4, t1: 2 });
    }
    // силуэт летит в свет
    const fy = 1150 - Math.min(t * 40, 320) + Math.sin(t * 2) * 14;
    p.shape([[430, fy + 260], [650, fy + 230], [620, fy + 290], [400, fy + 320]], { closeShape: true, fill: 'fill', color: INK, fillAlpha: .85, stroke: false, t0: 1.6, t1: 2.6 });
    surfer(p, t, S, 530, fy + 250, .6, { fist: 'up', lean: .2, dark: true });
    for (let i = 0; i < 12; i++) {
      const a = U.hash(i * 3.3) * TAU, r = 200 + U.hash(i * 7.1) * 500;
      p.sparkle(540 + Math.cos(a) * r, 900 + Math.sin(a) * r, 14, { c: 2, alpha: .8, t0: 2 + i * .08, t1: 2.8 + i * .08 });
    }
    if (t > 3) sparkBurst(p, 540, 900, t, { n: 8, r1: 200, period: 1.2, life: 1, t0: 3, c: 6 });
  },
};

export const SCENES_D = [surf_stand, surf_push, surf_face, surf_horizon, surf_wave, surf_fly, surf_bot, surf_rest, surf_light];
