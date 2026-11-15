// api.js — «рука» сцены: короткие команды, из которых собирается любой рисунок.
// Сцена говорит ЧТО рисовать (роль: главная линия / заливка / акцент) и каким цветом,
// а профиль материала решает, ЧЕМ это нарисовано — поэтому один и тот же клип
// перерисовывается карандашом, фломастерами или ручкой без правок в сценах.
import * as U from './util.js';
import { MAT, PROFILES, PALETTES, press, drawStroke, drawBleed, fillShape } from './materials.js';
import { PAGE } from './paper.js';

const TAU = U.TAU, PI = U.PI;

export class Pen {
  constructor(paint, opts = {}) {
    this.paint = paint;
    this.setProfile(opts.profile || 'pencil', opts.palette || 'warm');
    this.paper = opts.paper || 'notebook';
    this.page = PAGE;
    this.now = 0;
    this.seed = opts.seed ?? 1;
    this.mood = opts.mood || 'day';
    this.count = 0;
    this.beatT = 0;         // время ближайшей доли (для подпрыгиваний)
    this.pulse = 0;         // 0..1 — сила удара, для «качания» на битах
    this.hashSeed = 0.37;
    this.rasters = [];      // картинки, которые сцена кладёт на бумагу
  }
  setProfile(id, palette) {
    this.profile = PROFILES[id] || PROFILES.pencil;
    this.palette = PALETTES[palette] || PALETTES.warm;
    return this;
  }
  // ── служебное ──────────────────────────────────────────────────────────────
  _res(o = {}) {
    const P = this.profile, role = o.role || 'main';
    const base = P[role] || P.main;
    let color = base.color;
    if (!P.mono) color = o.color || (o.c !== undefined ? this.palette[((o.c | 0) % this.palette.length + this.palette.length) % this.palette.length] : this.palette[0]);
    else if (o.color && role === 'accent' && this.profile.id === 'chalk') color = o.color;
    return { mat: base.mat, color, fillStyle: base.fillStyle, wScale: base.wScale || 1 };
  }
  _frac(o = {}) {
    if (o.frac !== undefined) return U.clamp(o.frac);
    if (o.t0 === undefined && o.t1 === undefined) return 1;
    const t0 = o.t0 ?? 0, t1 = o.t1 ?? this.now;
    if (this.now <= t0) return 0;
    if (this.now >= t1) return 1;
    return U.easeOut((this.now - t0) / Math.max(.02, t1 - t0));
  }
  // появление N элементов по очереди: dur(0, 8) -> {t0,t1}
  seq(i, start = 0, step = .16, dur = .55) { return { t0: start + i * step, t1: start + i * step + dur }; }
  // ── линии ─────────────────────────────────────────────────────────────────
  raster(canvas, x, y, w, h, o = {}) {   // картинка на страницу (под штрихи)
    if (!canvas) return;
    const frac = this._frac(o);
    if (frac <= 0) return;
    this.rasters.push({ canvas, x, y, w, h, rot: o.rot || 0, alpha: (o.alpha ?? .97) * Math.min(1, .35 + frac * .65) });
    this.count++;
  }
  ink(pts, o = {}) {
    const res = this._res(o), mat = res.mat, color = res.color;
    o = res.wScale !== 1 ? { ...o, w: (o.w ?? 1) * res.wScale } : o;
    const frac = this._frac(o);
    if (frac <= 0 || pts.length < 2) return;
    const M = MAT[mat];
    let P;
    if (o.raw) P = pts;
    else {
      const smooth = o.smooth === undefined ? 0 : o.smooth;
      P = press(U.smoothPath(pts, smooth, this.seed + (o.seed || 0) * 3.3, o.seg || 7), (o.seed || 0) * 7.7 + this.hashSeed, {
        wob: (M.wob || 1) * (o.wob ?? 1), p: o.p ?? .7, blob: o.blob, taper: o.taper,
      });
    }
    const opts = { ...o, frac, color, w: o.w ?? 1, seed: (o.seed || 0) * 3.1 + this.seed };
    if (mat === 'marker' && !o.noBleed) drawBleed(this.paint.layer(mat), P, M, opts);
    else drawStroke(this.paint.layer(mat), P, M, opts);
    this.count++;
  }
  line(x1, y1, x2, y2, o = {}) { this.ink(U.wobbleLine(x1, y1, x2, y2, o.amp ?? 1.5, (o.seed || 0) + this.seed, o.n ?? 8), o); }
  poly(pts, o = {}) { this.ink(o.close ? U.catmull(pts, o.seg || 7, true) : pts, o); }
  curve(pts, o = {}) { this.ink(U.catmull(pts, o.seg || 8), o); }
  circle(cx, cy, r, o = {}) { this.ink(U.circlePts(cx, cy, r * (o.sqx ?? 1), r * (o.sqy ?? 1), (o.seed || 0) + this.seed, { over: o.over ?? .3, a0: o.a0 ?? -.4 }), o); }
  ellipse(cx, cy, rx, ry, o = {}) { this.circle(cx, cy, rx, { ...o, sqx: 1, sqy: ry / rx, r: undefined }); }
  arc(cx, cy, r, a0, a1, o = {}) { this.circle(cx, cy, r, { ...o, a0, over: o.over ?? .1 }); }
  rect(x, y, w, h, o = {}) { this.ink(U.rectPts(x, y, w, h, o.r || 0), o); }
  // ── фигуры (заливка + контур) ─────────────────────────────────────────────
  shape(path, o = {}) {
    const frac = this._frac(o);
    if (frac <= 0) return;
    if (o.fill) {
      const { mat, color, fillStyle } = this._res({ ...o, role: o.fill === true ? 'fill' : o.fill });
      const mode = o.mode || fillStyle || (MAT[mat].bleed ? 'solid' : MAT[mat].dry ? (o.scribble ? 'scribble' : 'hatch') : 'hatch');
      const rev = o.rev || ((k, total, pass) => {
        const q = 1 / (1 + k * .012 + pass * 2) ; return U.clamp(q * (this.now - (o.t0 ?? 0)) / Math.max(.05, (o.t1 ?? .6) - (o.t0 ?? 0)) * 1.6);
      });
      fillShape(this.paint.layer(mat), U.catmull(path, 4, true), MAT[mat], {
        color, mode, seed: (o.seed || 0) + 3.7, spacing: o.spacing, angle: o.angle, cross: o.cross,
        reveal: rev, w: o.fillW ?? 1, alphaScale: o.fillAlpha ?? (this.profile.id === 'pen' ? .8 : 1),
      });
    }
    if (o.stroke !== false) {
      const w = o.strokeW ?? 1;
      this.ink(U.catmull(path, o.seg || 6, !!o.closeShape), { ...o, color: o.strokeColor || o.color, role: o.stroke === true ? 'main' : (o.stroke || 'main'), w });
    }
  }
  dot(x, y, r, o = {}) {
    const { mat, color } = this._res(o);
    const frac = this._frac(o); if (frac <= 0) return;
    const g = this.paint.layer(mat);
    g.globalAlpha = U.clamp((MAT[mat].alpha) * frac * (mat === 'pen' ? 1.6 : 2.4), .05, 1); g.fillStyle = color;
    g.beginPath(); g.ellipse(x, y, r * frac, r * frac * .88, 0, 0, TAU); g.fill(); g.globalAlpha = 1;
  }
  // лёгкая тень-штриховка (без контура): пятно на бумаге
  shade(x, y, w, h, o = {}) {
    this.shape(U.rectPts(x, y, w, h), { ...o, fill: o.fill || 'fill', stroke: false, spacing: o.spacing ?? 11, cross: o.cross, angle: o.angle ?? -.32 });
  }
  // ── текст ─────────────────────────────────────────────────────────────────
  font(size, o = {}) {
    // Весь текст клипа — детским почерком Neucha (assets/fonts, OFL).
    // Печатных букв в списке нет специально: fallback только рукописные.
    const fam = o.font || '"Neucha","Comic Sans MS","Segoe Print","Bradley Hand","Comic Neue",cursive';
    return `${o.weight || 700} ${size}px ${fam}`;
  }
  text(str, x, y, o = {}) {
    const { mat, color } = this._res(o);
    const halo = o.halo !== false && !o.noHalo;
    if (halo) {   // светлый ореол под текстом: буквы читаются поверх любых линий
      const hg = this.paint.layer('white');
      const fracH = this._frac(o);
      if (fracH > 0) {
        hg.save(); hg.font = this.font(o.size ?? 72, o); hg.textBaseline = 'alphabetic';
        const chars = [...str], widths = chars.map(ch => hg.measureText(ch).width);
        const full = widths.reduce((a, b) => a + b, 0);
        let cx = o.align === 'center' ? x - full / 2 : o.align === 'right' ? x - full : x;
        const shown = Math.ceil(fracH * chars.length + .0001);
        hg.globalAlpha = .9; hg.lineWidth = (o.size ?? 72) * .19; hg.lineJoin = 'round';
        hg.strokeStyle = this.paper === 'dark' ? 'rgba(12,16,26,.85)' : 'rgba(250,246,235,.95)';
        for (let i = 0; i < shown; i++) { if (chars[i] === ' ') { cx += widths[i]; continue; } hg.strokeText(chars[i], cx, y); cx += widths[i]; }
        hg.restore();
      }
    }
    const g = this.paint.layer(mat), size = o.size ?? 72;
    const frac = this._frac(o);
    g.font = this.font(size, o); g.textBaseline = 'alphabetic'; g.textAlign = 'left';
    const chars = [...str];
    const shown = Math.ceil(frac * chars.length + .0001);
    let cx = x, total = 0;
    const widths = chars.map(ch => { const w = g.measureText(ch).width; return w; });
    const full = widths.reduce((a, b) => a + b, 0);
    if (o.align === 'center') cx = x - full / 2;
    if (o.align === 'right') cx = x - full;
    g.save();
    g.globalAlpha = U.clamp((MAT[mat].textAlpha ?? MAT[mat].alpha) * (o.alpha ?? 1), .12, 1);
    g.strokeStyle = g.fillStyle = color;
    for (let i = 0; i < shown; i++) {
      const ch = chars[i], w = widths[i];
      if (ch === ' ') { cx += w; continue; }
      const s = U.hash(i * 3.1 + (o.seed || 0)) - .5;
      g.save();
      g.translate(cx + w / 2, y + s * size * .05);
      g.rotate(s * .05);
      g.font = this.font(size, o);
      g.fillText(ch, -w / 2, 0);
      g.restore();
      cx += w;
    }
    g.restore();
    if (o.underline) this.line(x + (o.align === 'center' ? -full / 2 : 0), y + size * .28, x + (o.align === 'center' ? full / 2 : full), y + size * .28, { ...o, amp: 2.2, role: o.role });
    return full;
  }
  zzz(x, y, size, o = {}) {   // «с-с-с» — спящие
    ['z', 'z', 'z'].forEach((z, i) => this.text(z, x + i * size * .75, y - i * size * .55, { ...o, size: size * (1 - i * .13), t0: (o.t0 ?? 0) + i * .5, t1: (o.t1 ?? 1) + i * .5 }));
  }
  // ── проверки в списке дел ─────────────────────────────────────────────────
  scribbleOut(x0, x1, y, o = {}) {
    const n = o.n ?? 2;
    for (let i = 0; i < n; i++) this.line(x0, y + (i - (n - 1) / 2) * 9, x1, y + (i - (n - 1) / 2) * 9 + (i % 2 ? 8 : -10), { ...o, amp: 3.4, wob: 1.7, t0: (o.t0 ?? 0) + i * .16, t1: (o.t1 ?? .5) + i * .16, w: 1.1, role: o.role || 'accent' });
  }
  tick(x, y, s, o = {}) { this.ink([[x - s * .5, y], [x - s * .12, y + s * .45], [x + s * .6, y - s * .5]], { ...o, smooth: 1.2, w: 1.3 }); }
  box(x, y, s, o = {}) { this.rect(x, y, s, s, { ...o, r: 3, w: 1 }); }
  // ── растительность, погода, мелочи ────────────────────────────────────────
  cloud(cx, cy, s, o = {}) { this.poly(U.cloudPts(cx, cy, s, (o.seed || 0) + this.seed), { ...o, close: true, smooth: o.smooth ?? .6 }); }
  star(cx, cy, r, o = {}) { this.shape(U.starPts(cx, cy, r, r * (o.deep ?? .42), o.points || 5, (o.rot ?? -PI / 2), o.jit ?? .12, (o.seed || 0) + this.seed), { ...o, stroke: o.fill ? o.stroke : 'main', closeShape: true }); }
  sparkle(cx, cy, r, o = {}) { this.ink([[cx - r, cy], [cx, cy], [cx + r, cy]], { ...o, w: .7, smooth: 0 }); this.ink([[cx, cy - r], [cx, cy], [cx, cy + r]], { ...o, w: .7 }); }
  heart(cx, cy, s, o = {}) { this.shape(U.heartPts(cx, cy, s), { ...o, closeShape: true, seg: 0, smooth: .8 }); }
  leaf(x, y, s, ang, o = {}) { this.shape(U.leafPts(x, y, s, ang, (o.seed || 0) + this.seed), { ...o, closeShape: true, smooth: .5 }); }
  sun(cx, cy, r, o = {}) {
    this.circle(cx, cy, r * .62, { ...o, role: o.role || 'accent', fill: o.fill || null });
    const rays = o.rays ?? 9;
    for (let i = 0; i < rays; i++) {
      const a = i / rays * TAU + (o.rot || 0), r0 = r * .82, r1 = r * (1.16 + U.vn(i * 2.3 + this.seed) * .34);
      this.line(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0, cx + Math.cos(a) * r1, cy + Math.sin(a) * r1, { ...o, role: o.accentRole || 'accent', ...this.seq(i, o.t0 ?? 0, .05, .3), w: .85 });
    }
  }
  moon(cx, cy, r, o = {}) {
    const a0 = PI * .62, a1 = PI * 2.38;
    const outer = U.arcPts(cx, cy, r, r, a0, a1, 34);
    const inner = U.arcPts(cx + r * .52, cy, r * .84, r * .96, a1, a0, 30);
    this.ink(outer.concat(inner), { ...o, w: 1.35, smooth: .6 });
    for (const [dx, dy, rr] of [[-.24, -.3, .12], [-.34, .1, .09], [-.16, .34, .07]]) {
      this.ink(U.arcPts(cx + r * dx, cy + r * dy, r * rr, r * rr, 0, TAU * .92, 14), { ...o, w: .8, alpha: .7 });
    }
  }
  flower(cx, cy, s, o = {}) {
    const n = o.petals ?? 6, t0 = o.t0 ?? 0, d = o.pd ?? .22;
    for (let i = 0; i < n; i++) {
      const a = i / n * TAU - PI / 2 + (o.rot || 0);
      const k = this.seq(i, t0, d, o.ddur ?? .5);
      this.shape(U.catmull([[cx, cy], [cx + Math.cos(a + .3) * s * .8, cy + Math.sin(a + .3) * s * .8], [cx + Math.cos(a) * s * 1.5, cy + Math.sin(a) * s * 1.5], [cx + Math.cos(a - .3) * s * .8, cy + Math.sin(a - .3) * s * .8], [cx, cy]], 5, false),
        { ...o, closeShape: true, fill: o.fill, stroke: o.stroke ?? 'main', ...k, w: .9 });
    }
    this.circle(cx, cy, s * .28, { ...o, role: o.coreRole || 'accent', t0: t0 + n * d, t1: t0 + n * d + .4 });
  }
  ray(cx, cy, a0, a1, r0, r1, n, o = {}) {
    for (let i = 0; i < n; i++) {
      const a = U.lerp(a0, a1, n === 1 ? .5 : i / (n - 1));
      const rr = r1 * (.85 + U.vn(i * 2.3 + this.seed) * .3);
      this.ink([[cx + Math.cos(a) * r0, cy + Math.sin(a) * r0], [cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]], { ...o, ...this.seq(i, o.t0 ?? 0, o.step ?? .06, o.dur ?? .4), w: o.w ?? .85 });
    }
  }
  bird(x, y, s, o = {}) {   // галочка-птица
    this.ink([[x - s, y], [x - s * .35, y - s * .55], [x, y - s * .08], [x + s * .35, y - s * .55], [x + s, y]], { ...o, smooth: .8, w: .95 });
  }
  waves(x0, x1, y, amp, n, o = {}) {
    for (let k = 0; k < n; k++) {
      const yy = y + k * (o.gap ?? 34), a = amp * (1 - k / (n + 1)) * (o.vary ?? 1) * (.6 + U.vn(k * 3.1 + this.seed) * .7);
      this.ink(U.wavePts(x0, x1, yy, a, o.waves ?? 2 + k, k * 1.7 + (o.seed || 0), 70), { ...o, ...this.seq(k, o.t0 ?? 0, o.step ?? .18, o.dur ?? .9), w: .95 });
    }
  }
  hills(y, o = {}) {   // линия холмов
    const pts = [];
    const x0 = o.x0 ?? -40, x1 = o.x1 ?? PAGE.w + 40, n = o.n ?? 5, amp = o.amp ?? 90;
    for (let i = 0; i <= n; i++) pts.push([U.lerp(x0, x1, i / n), y - U.vn(i * 2.7 + (o.seed || 0) + this.seed) * amp]);
    this.curve(pts, { ...o, smooth: 1.2, w: .95 });
  }
  grass(y, o = {}) {   // пучки травы
    const n = o.n ?? 16, R = U.mulberry((o.seed || 0) + this.seed * 7);
    for (let i = 0; i < n; i++) {
      const x = U.lerp(o.x0 ?? PAGE.x0 - 40, o.x1 ?? PAGE.x1 + 40, (i + R() * .6) / n);
      const h = U.lerp(o.h0 ?? 18, o.h1 ?? 46, R()), bend = (R() - .5) * 26;
      this.ink([[x, y], [x + bend * .4, y - h * .6], [x + bend, y - h]], { ...o, ...this.seq(i, o.t0 ?? 0, .05, .35), w: .8 });
    }
  }
  balloon(cx, cy, r, o = {}) {
    this.shape(U.catmull([[cx, cy + r], [cx - r * .92, cy + r * .25], [cx - r * .72, cy - r * .55], [cx, cy - r * .9], [cx + r * .72, cy - r * .55], [cx + r * .92, cy + r * .25], [cx, cy + r]], 7, false), { ...o, closeShape: true, fill: o.fill, smooth: .6 });
    this.ink([[cx - r * .2, cy - r * .55], [cx - r * .38, cy - r * .72], [cx - r * .28, cy - r * .86]], { ...o, w: .7 });
    if (o.thread) this.ink([[cx, cy + r], [cx + o.thread[0], o.thread[1]]], { ...o, smooth: .8, w: .8 });
  }
  cup(cx, cy, s, o = {}) {   // чашка
    this.shape(U.catmull([[cx - s, cy - s * .7], [cx + s, cy - s * .7], [cx + s * .78, cy + s * .8], [cx - s * .78, cy + s * .8]], 6, true), { ...o, closeShape: true, fill: o.fill, smooth: .4 });
    this.ink(U.arcPts(cx + s * 1.0, cy - s * .1, s * .52, s * .5, -PI * .62, PI * .62, 18), { ...o, w: 1 });
    if (o.blush) this.shape(U.catmull([[cx - s * 1.9, cy + s * .92], [cx + s * 1.9, cy + s * .92], [cx + s * 1.6, cy + s * 1.12], [cx - s * 1.6, cy + s * 1.12]], 5, true), { ...o, closeShape: true, fill: o.fill, stroke: 'main', w: .8 });
  }
  steam(cx, cy, s, o = {}) {   // пар: завивающиеся струйки
    for (let k = 0; k < (o.n ?? 2); k++) {
      const pts = [];
      for (let i = 0; i <= 14; i++) {
        const t = i / 14, y = cy - t * s;
        pts.push([cx + (k - (o.n ?? 2) / 2 + .5) * s * .34 + Math.sin(t * 4.4 + k * 2.1 + this.now * (o.speed ?? 1.6)) * s * .22 * t, y]);
      }
      this.ink(pts, { ...o, w: .75, alpha: o.alpha ?? .5 });
    }
  }
  candle(cx, y, h, o = {}) {
    this.rect(cx - h * .13, y - h, h * .26, h, { ...o, w: .9 });
    const fl = Math.sin(this.now * 9 + cx) * h * .04;
    this.ink([[cx, y - h], [cx + fl, y - h - h * .34], [cx + fl * 1.4, y - h - h * .5], [cx - fl, y - h - h * .22], [cx, y - h]], { ...o, role: o.role || 'accent', w: .9, smooth: .6, close: true });
    this.dot(cx + fl * .5, y - h - h * .26, h * .07, { ...o, role: o.coreRole || 'accent' });
  }
  note(cx, cy, s, o = {}) {   // нота
    this.ellipse(cx, cy, s * .34, s * .26, { ...o, a0: PI * .1, over: .2, w: 1 });
    this.ink([[cx + s * .3, cy - s * .2], [cx + s * .3, cy - s * 1.5]], { ...o, w: 1.1 });
    this.ink([[cx + s * .3, cy - s * 1.5], [cx + s * .95, cy - s * 1.62], [cx + s * .95, cy - s * .95]], { ...o, w: 1 });
  }
  headphones(cx, cy, s, o = {}) {
    this.ink(U.arcPts(cx, cy, s, s, PI * 1.06, PI * 1.94, 26), { ...o, w: 1.5 });
    this.shape(U.catmull([[cx - s, cy - s * .2], [cx - s * 1.28, cy - s * .1], [cx - s * 1.28, cy + s * .72], [cx - s * 1.02, cy + s * .8], [cx - s * .82, cy + s * .5]], 5, true), { ...o, closeShape: true, fill: o.fill, w: 1 });
    this.shape(U.catmull([[cx + s, cy - s * .2], [cx + s * 1.28, cy - s * .1], [cx + s * 1.28, cy + s * .72], [cx + s * 1.02, cy + s * .8], [cx + s * .82, cy + s * .5]], 5, true), { ...o, closeShape: true, fill: o.fill, w: 1 });
  }
  // ── фигура человека ───────────────────────────────────────────────────────
  // x, y — ступни; s — рост (1.0 ≈ 300 px). pose: углы рук/ног + наклон.
  figure(x, y, s, pose = {}, o = {}) {
    const f = 300 * s;
    const lean = pose.lean || 0, face = o.face === undefined ? 1 : o.face;
    const hipY = y - f * .5, shoY = y - f * .84, neckY = y - f * .88;
    const sho = [x + lean * f * .33, shoY], hip = [x + lean * f * .15, hipY];
    const L1 = f * .15, L2 = f * .145, T1 = f * .25, T2 = f * .25;
    const shL = [sho[0] - f * .082 * face, sho[1] + f * .012], shR = [sho[0] + f * .082 * face, sho[1] + f * .012];
    const hpL = [hip[0] - f * .045 * face, hip[1]], hpR = [hip[0] + f * .045 * face, hip[1]];
    const limb = (S, a1, a2, l1, l2) => {
      const e = [S[0] + Math.sin(a1) * l1 * face, S[1] + Math.cos(a1) * l1];
      return [S, e, [e[0] + Math.sin(a1 + a2) * l2 * face, e[1] + Math.cos(a1 + a2) * l2]];
    };
    const armL = pose.handL ? U.ik(shL, pose.handL, L1, L2, pose.bendL ?? 1) : limb(shL, pose.aL ? pose.aL[0] : -.5, pose.aL ? pose.aL[1] : .5, L1, L2);
    const armR = pose.handR ? U.ik(shR, pose.handR, L1, L2, pose.bendR ?? -1) : limb(shR, pose.aR ? pose.aR[0] : .5, pose.aR ? pose.aR[1] : .5, L1, L2);
    const legL = pose.footL ? U.ik(hpL, pose.footL, T1, T2, 1) : limb(hpL, pose.lL ? pose.lL[0] : -.14, pose.lL ? pose.lL[1] : .1, T1, T2);
    const legR = pose.footR ? U.ik(hpR, pose.footR, T1, T2, -1) : limb(hpR, pose.lR ? pose.lR[0] : .14, pose.lR ? pose.lR[1] : .1, T1, T2);
    const c = { ...o, ...(o.t0 !== undefined ? this.seq(0, o.t0, 0, o.t1 - o.t0) : {}) };
    const w = c.w ?? 1;
    // 1) дальние конечности
    this.ink(legR, { ...c, w: w * 1.05, ...this.seq(6, o.t0 ?? 0, .1, .5) });
    this.ink(armR, { ...c, ...this.seq(3, o.t0 ?? 0, .1, .5) });
    // 2) тело: платье-трапеция от плеч до подола
    const dress = pose.dress !== false;
    const hemH = dress ? (pose.skirtLen ?? f * .18) : 0;
    const hemY = y + (pose.hemDrop ?? f * .06) * (dress ? 1 : .2);
    const hemW = dress ? (pose.skirt ?? f * .17) : f * .06;
    const waistR = [hip[0] + f * .085, hipY], waistL = [hip[0] - f * .085, hipY];
    const hemR = [hip[0] + hemW * (pose.bell ?? 1) + (pose.sway || 0) * f * .1, y + (pose.hemDrop === undefined ? f * .02 : pose.hemDrop) * .3];
    const hemL = [hip[0] - hemW * (pose.bell ?? 1) + (pose.sway || 0) * f * .1, hemR[1]];
    const hemY2 = Math.max(hemR[1], hipY + hemH);
    const hemRr = [hemR[0], hemY2], hemLl = [hemL[0], hemY2];
    const path = [shL, [U.lerp(shL[0], waistL[0], .5) - f * .015, U.lerp(shL[1], waistL[1], .5)], waistL, hemLl];
    const scallops = 5;
    for (let i = 1; i <= scallops; i++) {
      const k = i / scallops, xx = U.lerp(hemLl[0], hemRr[0], k);
      path.push([xx, hemY2 + (i % 2 ? f * .018 : -f * .004)]);
    }
    path.push(hemRr, waistR, [U.lerp(shR[0], waistR[0], .5) + f * .015, U.lerp(shR[1], waistR[1], .5)], shR);
    this.shape(path, { ...c, closeShape: true, fill: c.fill, stroke: c.stroke !== false ? 'main' : false, smooth: .45, w: w * 1.15, ...this.seq(4, o.t0 ?? 0, .1, .55) });
    if (dress) this.ink([waistL, waistR], { ...c, w: w * .8, alpha: .6, ...this.seq(4.5, o.t0 ?? 0, .1, .5) });
    // 3) ближние конечности
    this.ink(legL, { ...c, w: w * 1.05, ...this.seq(7, o.t0 ?? 0, .1, .5) });
    this.ink(armL, { ...c, ...this.seq(2, o.t0 ?? 0, .1, .5) });
    // 4) шея, голова, лицо, волосы
    const headR = f * .083;
    const hx = sho[0] + (pose.headDX || 0) * f * .05, hy = neckY - headR * 1.15;
    this.ink([sho, [hx, hy + headR * .8]], { ...c, w: w * .9, ...this.seq(5, o.t0 ?? 0, .1, .4) });
    this.circle(hx, hy, headR, { ...c, w: w * 1.1, ...this.seq(5, o.t0 ?? 0, .1, .5), over: .35 });
    if (o.face !== false) {
      const eo = headR * .34, ey = hy - headR * .05, F = this.seq(8, o.t0 ?? 0, 0, .3);
      if (pose.eyes === 'closed') {
        this.ink(U.arcPts(hx - eo, ey, headR * .19, headR * .14, PI * 1.1, PI * 1.9, 8), { ...c, w: w * .7, ...F });
        this.ink(U.arcPts(hx + eo, ey, headR * .19, headR * .14, PI * 1.1, PI * 1.9, 8), { ...c, w: w * .7, ...F });
      } else {
        this.dot(hx - eo, ey, headR * .11, { ...c, ...F });
        this.dot(hx + eo, ey, headR * .11, { ...c, ...F });
      }
      if (pose.mouth !== false) this.ink(U.arcPts(hx, hy + headR * .3, headR * .21, headR * .15, PI * .15, PI * .85, 10), { ...c, w: w * .68, ...F });
    }
    const hl = pose.hairLen ?? 1.25, hq = o.hairQ ?? 4;
    for (let i = 0; i < hq; i++) {
      const a = PI * (.14 + i * .23), r = headR * (1.02 + U.vn(i * 3.7 + this.seed) * .2);
      const tip = [hx - Math.cos(a) * headR * hl * (.5 + i * .28) * (pose.wind || 1), hy + headR * (.35 + hl * .5) + i * headR * .1];
      this.curve([[hx + Math.cos(a) * r * .7, hy + Math.sin(a) * r * .55], [hx + Math.cos(a) * r * .95, hy + Math.sin(a) * r * 1.05], tip],
        { ...c, w: w * .78, ...this.seq(10 + i, o.t0 ?? 0, .06, .45) });
    }
    // 5) ступни
    for (const leg of [legL, legR]) {
      const wn = leg[2], a = Math.atan2(wn[1] - leg[1][1], (wn[0] - leg[1][0]) * face);
      this.ink([[wn[0] - Math.cos(a) * f * .055 * face, wn[1] - Math.sin(a) * f * .055], [wn[0] + Math.cos(a) * f * .052 * face, wn[1] + Math.sin(a) * f * .052]], { ...c, w: w * .85 });
    }
    return { head: [hx, hy], headR, hands: [armL[2], armR[2]], sho, hip, feet: [legL[2], legR[2]] };
  }
  // позы
  walkPose(ph, o = {}) {   // ph: 0..1 — фаза шага
    const A = TAU * ph;
    return { aL: [-.35 - .5 * Math.sin(A), .3 + .25 * Math.sin(A + .7)], aR: [-.35 + .5 * Math.sin(A), .3 + .25 * Math.sin(A - .7)],
             lL: [-.35 * Math.sin(A), .18 + .2 * Math.sin(A + .5)], lR: [.35 * Math.sin(A), .18 - .2 * Math.sin(A - .5)],
             lean: .08, bob: Math.abs(Math.cos(A)), sway: Math.sin(A * 2) * .3, ...o };
  }
  dancePose(ph, o = {}) {  // танец: руки вверх-в стороны, ноги в прыжке-приставном шаге
    const A = TAU * ph;
    const hop = Math.max(0, Math.sin(A)) * .1;
    return { aL: [-1.5 - .55 * Math.sin(A), .4 + .35 * Math.sin(A)], aR: [1.5 + .55 * Math.sin(A + 1.2), .4 + .35 * Math.sin(A + 1.2)],
             lL: [-.1 - .1 * Math.sin(A), .12 + hop], lR: [.1 + .1 * Math.sin(A), .1 + hop],
             lean: .05 * Math.sin(A), sway: .4 * Math.sin(A), ...o };
  }
  sitPose(o = {}) { return { aL: [-.5, .6], aR: [.5, .6], lL: [-1.15, .6], lR: [-1.0, .5], lean: -.12, ...o }; }
}
function incl() { return 0; }
