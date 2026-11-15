// scenes1.js — первая половина библиотеки сцен.
import * as U from './util.js';
import { PAGE } from './paper.js';
import { skyStars, sparkBurst, dust, foliage, bushes, equalizer, notesFlying, scribbleText, person } from './common.js';
const TAU = U.TAU, PI = U.PI, ik = U.ik;

// 1 ── Дождь за окном ───────────────────────────────────────────────────────
const window_rain = {
  id: 'window_rain', name: 'Дождь за окном', tags: ['спокойное', 'дождь', 'дом'], dur: 14,
  draw(p, t, S) {
    const wx0 = 110, wy0 = 250, wx1 = 970, wy1 = 1300;
    const R = U.mulberry(101 + S.seed);
    // стекло и рама
    p.rect(wx0, wy0, wx1 - wx0, wy1 - wy0, { r: 10, w: 1.9, t0: 0, t1: 1.0 });
    p.rect(wx0 + 16, wy0 + 16, wx1 - wx0 - 32, wy1 - wy0 - 32, { r: 6, w: .9, t0: .4, t1: 1.4 });
    p.line(540, wy0 + 16, 540, wy1 - 16, { w: 1.2, t0: .7, t1: 1.5 });
    p.line(wx0 + 16, 790, wx1 - 16, 790, { w: 1.2, t0: .8, t1: 1.6 });
    // шторы по бокам
    for (const side of [-1, 1]) {
      const bx = side < 0 ? wx0 + 30 : wx1 - 30, pts = [];
      for (let i = 0; i <= 14; i++) {
        const k = i / 14, y = U.lerp(wy0 + 8, wy0 + 700, k);
        pts.push([bx + side * (Math.sin(k * 5 + t * .8) * 22 + k * 30), y]);
      }
      pts.push([bx + side * 210, wy0 + 690], [bx + side * 210, wy0 + 24], [bx + side * 40, wy0 + 8]);
      p.shape(pts, { closeShape: true, fill: 'fill', stroke: 'main', w: 1, smooth: .5, spacing: 22, t0: .4, t1: 2.4, angle: side * .5 });
    }
    // дождь за стеклом
    const rainN = Math.round(44 * S.dens);
    for (let i = 0; i < rainN; i++) {
      const x = U.lerp(wx0 + 24, wx1 - 24, R()), sp = U.lerp(560, 980, R());
      const span = wy1 - wy0 - 40;
      const y = wy0 + 20 + ((R() * span + t * sp) % span);
      const len = U.lerp(34, 66, R());
      p.ink([[x, y], [x + len * .32, y - len]], { w: .8, alpha: .5, raw: false, t0: .8, t1: 1.3, seed: i });
    }
    // капли ползут по стеклу
    const drops = [];
    for (let i = 0; i < 8; i++) drops.push({ x: U.lerp(wx0 + 60, wx1 - 60, R()), y0: U.lerp(wy0 + 60, wy0 + 420, R()), start: 1.6 + R() * 5, sp: U.lerp(40, 90, R()) });
    drops.forEach((d, i) => {
      const tt = Math.max(0, t - d.start); if (tt <= 0) return;
      const y = Math.min(d.y0 + tt * d.sp, wy1 - 30), wob = Math.sin(tt * 2.4 + i) * 5;
      p.ink([[d.x, d.y0], [d.x + wob * .4, (d.y0 + y) / 2], [d.x + wob, y]], { w: .9, role: 'accent', alpha: .85, t0: d.start, t1: d.start + .3 });
      p.dot(d.x + wob, y, 5.5, { role: 'accent' });
    });
    // подоконник и полка под ним
    p.line(70, wy1, 1010, wy1 + 8, { w: 2, t0: .6, t1: 1.5 });
    p.line(96, wy1 + 44, 984, wy1 + 50, { w: 1.2, t0: .7, t1: 1.7 });
    p.shade(120, wy1 + 60, 840, 90, { angle: -.1, spacing: 26, t0: 1, t1: 2.2, alpha: .4 });
    // растение в горшке слева
    const px = 210, ptop = 1520;
    p.shape([[px - 96, ptop], [px + 96, ptop], [px + 74, 1810], [px - 74, 1810]], { closeShape: true, fill: 'fill', stroke: 'main', w: 1.5, spacing: 20, t0: 2.2, t1: 3.4 });
    p.ink(U.humps(px - 96, px + 96, ptop, 5, 16, 3), { w: 1.1, t0: 2.6, t1: 3.6, role: 'accent' });
    for (let i = 0; i < 6; i++) {
      const a = -PI / 2 + (i - 2.5) * .3, len = U.lerp(130, 210, U.vn(i * 2.7 + p.seed));
      const tip = [px + Math.cos(a) * len * .55, ptop - 40 + Math.sin(a) * len];
      p.ink([[px + Math.cos(a) * 14, ptop - 10], [U.lerp(px, tip[0], .5) + Math.sin(t * .8 + i) * 6, U.lerp(ptop - 20, tip[1], .55)], tip],
        { ...p.seq(i, 3), w: 1.15, smooth: .8 });
      p.leaf(tip[0], tip[1], U.lerp(56, 84, U.vn(i * 3.1)), a, { ...p.seq(i, 3.4), w: 1, c: 4 });
    }
    // чашка справа
    p.cup(870, 1700, 74, { t0: 3.4, t1: 4.4, blush: true, w: 1.4 });
    p.steam(870, 1620, 170, { t0: 4.2, t1: 5, n: 3, speed: 1.1 });
    p.text('дождь за окном', 540, 1860, { size: 84, align: 'center', t0: 5, t1: 6.4, underline: true });
  },
};

// 2 ── Кот спит ─────────────────────────────────────────────────────────────
const cat_sleep = {
  id: 'cat_sleep', name: 'Кот спит', tags: ['спокойное', 'дом'], dur: 13,
  draw(p, t, S) {
    const cx = 540, cy = 1180;
    const br = 1 + .025 * Math.sin(t * (TAU / 3.1));
    // подстилка
    p.shape(U.catmull([[cx - 430, cy + 90], [cx - 300, cy + 250], [cx, cy + 290], [cx + 320, cy + 250], [cx + 440, cy + 90], [cx + 300, cy + 130], [cx, cy + 150], [cx - 300, cy + 130]], 6, true),
      { closeShape: true, fill: 'fill', stroke: 'main', w: 1.2, spacing: 30, t0: .2, t1: 1.8, angle: -.05, alpha: .8 });
    // хвост спиралью
    const tail = [];
    for (let i = 0; i <= 46; i++) {
      const k = i / 46, a = -PI * .35 + k * TAU * .84;
      const tw = Math.max(0, (k - .78) / .22) * Math.sin(t * 5.5) * 26;
      tail.push([cx + Math.cos(a) * (400 + k * 26) * br, cy + Math.sin(a) * (270 + k * 22) + tw]);
    }
    p.ink(tail, { w: 1.5, smooth: .5, t0: .4, t1: 2 });
    // тело
    const body = [];
    for (let i = 0; i <= 48; i++) { const a = i / 48 * TAU; body.push([cx + Math.cos(a) * 360 * br, cy + Math.sin(a) * 235 * br + Math.sin(a * 2) * 14]); }
    p.shape(body, { closeShape: true, fill: 'fill', stroke: 'main', w: 1.7, spacing: 26, angle: -.22, t0: .6, t1: 2.6 });
    // полоски
    for (let i = 0; i < 7; i++) {
      const a = -.95 + i * .28;
      p.ink(U.arcPts(cx + 30, cy - 30, 250 * br, 160 * br, a - .26, a + .26, 12), { w: 1.2, t0: 2.2 + i * .13, t1: 2.7 + i * .13, alpha: .85 });
    }
    // голова
    const hx = cx - 300, hy = cy - 90 + Math.sin(t * (TAU / 3.1)) * 8, headR = 118;
    for (const s of [-1, 1]) {
      p.shape([[hx + s * 34, hy - 84], [hx + s * 74, hy - 196], [hx + s * 116, hy - 66]], { closeShape: true, fill: 'fill', stroke: 'main', w: 1.3, t0: 1.4, t1: 2.2, spacing: 16, angle: .7 });
      p.ink([[hx + s * 52, hy - 118], [hx + s * 72, hy - 168], [hx + s * 92, hy - 104]], { w: .9, t0: 1.9, t1: 2.4, role: 'accent' });
    }
    p.circle(hx, hy, headR, { w: 1.7, t0: 1.2, t1: 2.3, sqy: .93 });
    // закрытые глаза, нос, усы, щёки
    for (const s of [-1, 1]) {
      p.ink(U.arcPts(hx + s * 42, hy - 12, 26, 18, PI * 1.12, PI * 1.88, 10), { w: 1.1, t0: 2.2, t1: 2.8 });
      for (let i = 0; i < 3; i++) p.ink([[hx + s * 20, hy + 26 + i * 11], [hx + s * 148, hy + 6 + i * 22]], { w: .7, alpha: .8, t0: 2.6 + i * .1, t1: 3.1 + i * .1 });
    }
    p.ink([[hx - 14, hy + 20], [hx, hy + 32], [hx + 14, hy + 20]], { w: 1.1, t0: 2.4, t1: 2.9, role: 'accent' });
    p.shade(hx - 92, hy - 6, 60, 40, { angle: .3, spacing: 12, t0: 2.8, t1: 3.4, alpha: .7, role: 'accent' });
    p.shade(hx + 44, hy - 6, 60, 40, { angle: .3, spacing: 12, t0: 2.8, t1: 3.4, alpha: .7, role: 'accent' });
    // лапки
    for (let i = 0; i < 2; i++) {
      p.ellipse(hx + 150 + i * 86, hy + 150, 52, 32, { w: 1.2, t0: 2.8 + i * .15, t1: 3.5 + i * .15, over: .3 });
      for (let k = 0; k < 3; k++) p.ink([[hx + 176 + i * 86 + k * 14, hy + 124], [hx + 190 + i * 86 + k * 15, hy + 150]], { w: .6, t0: 3.1 + k * .06, t1: 3.4 + k * .06 });
    }
    // клубок с ниткой
    p.circle(860, 1520, 74, { w: 1.2, t0: 3.2, t1: 4 });
    for (let i = 0; i < 5; i++) p.ink(U.arcPts(860, 1520, 74, 74 * (.35 + i * .13), -1.1 + i * 2.2, .6 + i * 2.2, 16), { w: .8, t0: 3.4 + i * .1, t1: 3.9 + i * .1 });
    p.ink([[860, 1520], [700, 1420], [cx + 120, cy + 150], [300, 1560], [200, 1700]], { w: .9, smooth: .8, t0: 4, t1: 5 });
    // «с-с-с»
    const ph = (t % 3.4) / 3.4;
    if (t > 3.4) {
      p.text('z', hx + 150, hy - 200 - ph * 150, { size: 62 + ph * 20, role: 'accent', alpha: .95 * (1 - ph), t0: 3.4, t1: 3.5, align: 'center' });
      if (ph > .35) p.text('z', hx + 196, hy - 140 - ph * 110, { size: 40 + ph * 14, role: 'accent', alpha: .8 * (1 - ph), t0: 3.4, t1: 3.5, align: 'center' });
    }
    p.text('тихо', 540, 1770, { size: 84, align: 'center', t0: 5, t1: 6.4, underline: true });
  },
};

// 3 ── Город вечером ────────────────────────────────────────────────────────
const city_night = {
  id: 'city_night', name: 'Город вечером', tags: ['город', 'вечер'], dur: 15,
  draw(p, t, S) {
    const groundY = 1660;
    skyStars(p, t, S, { n: 20, y0: 260, y1: 700, t0: .2, seed: 3 });
    p.moon(250, 300, 76, { t0: .6, t1: 1.7, w: 1.5 });
    const R = U.mulberry(707 + S.seed);
    const bld = [];
    let x = -40;
    while (x < 1120) { const w = U.lerp(130, 230, R()), h = U.lerp(330, 780, R()); bld.push({ x, w, h }); x += w + U.lerp(8, 26, R()); }
    bld.forEach((b, i) => {
      const y0 = groundY - b.h, T = p.seq(i, .3, .18, .9);
      p.rect(b.x, y0, b.w, b.h, { w: 1.5, t0: T.t0, t1: T.t1 });
      if (R() < .5) p.line(b.x + b.w * .5, y0, b.x + b.w * .5, y0 - U.lerp(50, 130, R()), { w: 1.1 });
      const cols = Math.max(2, Math.floor(b.w / 54)), rows = Math.max(2, Math.floor(b.h / 76));
      for (let c = 0; c < cols; c++) for (let r = 0; r < rows; r++) {
        if (R() < .34) continue;
        const wx = b.x + 20 + c * (b.w - 34) / cols, wy = y0 + 26 + r * (b.h - 44) / rows;
        const tw = .6 + .4 * Math.sin(t * (1.3 + R() * 2.2) + i * 3 + c + r);
        p.shape(U.rectPts(wx, wy, 26, 32), { closeShape: true, fill: 'fill', stroke: false, spacing: 9, t0: 2 + i * .18 + (c + r) * .06, t1: 2.6 + i * .18 + (c + r) * .06, alpha: tw * .9, fillAlpha: .5, role: 'accent' });
      }
    });
    p.line(-40, groundY, 1120, groundY + 6, { w: 1.7, t0: .2, t1: .9 });
    // провода с птицами
    p.ink(U.wobbleLine(-30, 980, 1110, 1040, 30, 3, 16), { w: 1, t0: 1.1, t1: 2.5 });
    for (let i = 0; i < 6; i++) {
      const k = .12 + i * .16, xw = U.lerp(-30, 1110, k), yw = U.lerp(980, 1040, k) + Math.sin(k * 15) * 14;
      p.bird(xw, yw - 14, 17, { w: 1, t0: 2.4 + i * .28, t1: 3 + i * .28 });
    }
    // фонарь со светом
    p.line(170, groundY, 170, groundY - 380, { w: 1.5, t0: 1.4, t1: 2.4 });
    p.ink([[170, groundY - 380], [244, groundY - 380]], { w: 1.2 });
    p.circle(244, groundY - 368, 20, { w: 1.1 });
    p.shade(90, groundY - 340, 320, 340, { angle: -.5, spacing: 26, t0: 2.4, t1: 3.6, alpha: .45, role: 'accent' });
    // машина
    const carX = ((t * 150) % 1500) - 260, carY = groundY + 46;
    p.shape([[carX, carY], [carX + 200, carY], [carX + 172, carY - 74], [carX + 40, carY - 80]], { closeShape: true, fill: 'fill', stroke: 'main', w: 1.3, spacing: 14, t0: 3, t1: 3.6 });
    p.circle(carX + 48, carY + 2, 22, { w: 1.1 });
    p.circle(carX + 152, carY + 2, 22, { w: 1.1 });
    p.ink([[carX + 200, carY - 26], [carX + 350, carY - 12]], { w: .9, role: 'accent', alpha: .6 });
    p.text('город', 540, 320, { size: 112, align: 'center', t0: 3.6, t1: 5.2, underline: true, noHalo: true });
  },
};

// 4 ── Звёзды ───────────────────────────────────────────────────────────────
const stars = {
  id: 'stars', name: 'Звёзды', tags: ['ночь', 'спокойное'], dur: 14,
  draw(p, t, S) {
    p.moon(870, 300, 92, { t0: .3, t1: 1.6, w: 1.5 });
    const R = U.mulberry(9001 + S.seed);
    const pts = [];
    const n = Math.round(46 * S.dens);
    for (let i = 0; i < n; i++) pts.push([U.lerp(110, 1000, R()), U.lerp(240, 1080, R())]);
    pts.forEach((q, i) => {
      const r = U.lerp(4, 11, R() ** 2), tw = .55 + .45 * Math.sin(t * (1 + R() * 2) + i * 1.7);
      const T = p.seq(i, .5, .08, .5);
      p.ink([[q[0] - r, q[1]], [q[0], q[1] - r * .25], [q[0] + r, q[1]], [q[0], q[1] + r * .25], [q[0] - r, q[1]]], { w: .85, role: 'accent', alpha: .6 * tw, smooth: .4, t0: T.t0, t1: T.t1 });
      if (i % 4 === 0) p.sparkle(q[0], q[1], r * 2.6 * tw, { w: .65, role: 'accent', alpha: .45 * tw, t0: T.t0 + .2, t1: T.t1 + .3 });
    });
    // созвездие: соединяем только близкие звёзды в верхней части
    const sk = pts.filter(q => q[1] < 780).slice(0, 9);
    for (let i = 0; i < sk.length - 1; i++) {
      const a = sk[i], b = sk[i + 1];
      if (U.dist(a, b) > 330) continue;
      p.ink([a, [U.lerp(a[0], b[0], .5) + 14, U.lerp(a[1], b[1], .5) - 10], b], { w: .7, role: 'accent', alpha: .45, smooth: .4, t0: 2.6 + i * .3, t1: 3.3 + i * .3 });
    }
    // падающая звезда
    const period = 5.5, ph = (t % period) / period;
    if (t > 2.5 && ph < .3) {
      const k = ph / .3, x = U.lerp(900, 300, k), y = U.lerp(280, 660, k);
      p.ink([[x + 210 * (1 - k), y - 170 * (1 - k)], [x + 74, y - 60], [x, y]], { w: 1.1, role: 'accent', alpha: .9, smooth: .5, raw: false, t0: 0, t1: .01 });
      p.dot(x, y, 6, { role: 'accent' });
    }
    // холмы, домик, дерево, трава
    p.hills(1290, { n: 5, amp: 120, t0: 1.4, t1: 2.8, seed: 3 });
    p.hills(1470, { n: 8, amp: 80, x0: -40, x1: 1120, t0: 1.9, t1: 3.3, seed: 8 });
    p.shape([[620, 1290], [620, 1080], [730, 960], [840, 1080], [840, 1290]], { closeShape: true, fill: 'fill', stroke: 'main', w: 1.6, t0: 3, t1: 4.1, spacing: 30, angle: .5 });
    p.shape([[662, 1232], [662, 1178], [710, 1146], [758, 1178], [758, 1232]], { closeShape: true, fill: 'fill', stroke: 'main', w: 1.2, t0: 3.6, t1: 4.6, spacing: 14, role: 'accent', alpha: .8 + .2 * Math.sin(t * 3) });
    p.ink([[730, 960], [730, 890]], { w: 1.3, t0: 4.2, t1: 4.7 });
    // дерево рядом с домиком
    p.ink([[300, 1300], [316, 1180], [300, 1080], [324, 980]], { w: 1.4, smooth: .7, t0: 4.2, t1: 5 });
    p.ink([[316, 1180], [240, 1120]], { w: 1.1, smooth: .6, t0: 4.6, t1: 5.1 });
    p.ink([[312, 1090], [388, 1020]], { w: 1.1, smooth: .6, t0: 4.7, t1: 5.2 });
    foliage(p, 308, 1010, 130, 90, Math.round(9 * S.dens), { t0: 5, step: .12, fill: 'fill', stroke: 'main', w: .8, spacing: 16, scale: .8 });
    // дымок из трубы
    for (let i = 0; i < 14; i++) {
      const k = i / 14, y = 880 - k * 260, x = 732 + Math.sin(k * 5 + t * 1.4) * 40 * k;
      p.dot(x, y, 6, { role: 'accent', alpha: .3 * (1 - k) });
    }
    p.grass(1480, { x0: 40, x1: 1040, n: 24, h0: 16, h1: 40, t0: 4.4 });
    p.text('звёзды', 540, 1770, { size: 104, align: 'center', t0: 5, t1: 6.6, underline: true });
  },
};

// 5 ── Кофе ─────────────────────────────────────────────────────────────────
const coffee = {
  id: 'coffee', name: 'Кофе', tags: ['утро', 'дом', 'спокойное'], dur: 13,
  draw(p, t, S) {
    const ty = 1300;
    p.sun(880, 620, 84, { t0: .6, t1: 1.8, role: 'accent', rays: 11 });
    p.shade(420, 700, 460, 520, { angle: .52, spacing: 34, t0: .8, t1: 2.2, alpha: .3, cross: true });
    p.line(-20, ty, 1100, ty + 8, { w: 1.8, t0: .2, t1: .9 });
    p.shade(40, ty + 14, 1000, 130, { angle: -.12, spacing: 30, t0: .5, t1: 1.8, alpha: .38 });
    // чашка
    const cx = 380, cy = ty - 150;
    p.ellipse(cx, cy + 150, 210, 34, { w: 1.2, t0: 1.4, t1: 2.2 });
    p.cup(cx, cy, 130, { t0: 1.8, t1: 3.2, blush: true, w: 1.6, fill: 'fill' });
    p.steam(cx, cy - 240, 300, { t0: 3.2, t1: 4, n: 3, speed: 1.05 });
    // ложка
    p.ellipse(cx + 250, ty + 90, 34, 52, { w: 1.2, t0: 3.2, t1: 3.9, over: .3 });
    p.ink([[cx + 256, ty + 140], [cx + 330, ty + 230]], { w: 1.2, t0: 3.5, t1: 4.1 });
    // тарелка с печеньем
    p.ellipse(790, ty + 20, 200, 40, { w: 1.3, t0: 2.6, t1: 3.4 });
    for (let i = 0; i < 3; i++) {
      const bx = 720 + i * 66, by = ty - 40 - (i === 1 ? 20 : 0);
      p.shape(U.catmull([[bx - 54, by + 22], [bx - 46, by - 20], [bx, by - 34], [bx + 46, by - 20], [bx + 54, by + 22], [bx, by + 32]], 5, true),
        { closeShape: true, fill: 'fill', stroke: 'main', w: 1.15, t0: 2.9 + i * .25, t1: 3.7 + i * .25, spacing: 16 });
      for (let k = 0; k < 4; k++) p.dot(bx - 26 + k * 17, by - 6 + (k % 2) * 12, 3.4, { role: 'accent' });
    }
    // записка и ручка
    p.shape(U.rectPts(600, 1560, 380, 240, 5), { closeShape: true, fill: 'fill', stroke: 'main', w: 1.2, t0: 3.8, t1: 4.9, angle: -.3, spacing: 22 });
    for (let i = 0; i < 3; i++) scribbleText(p, 640, 1624 + i * 52, 240 + i * 40, { w: .9, t0: 4.4 + i * .2, t1: 5 + i * .2, seed: i * 9 });
    p.ink([[640, 1830], [960, 1786]], { w: 6.5, t0: 5, t1: 5.7 });
    p.ink([[644, 1822], [956, 1778]], { w: 1.2, role: 'accent', t0: 5, t1: 5.7 });
    p.text('доброе утро', 540, 380, { size: 118, align: 'center', t0: 5.4, t1: 7, underline: true, halo: false, noHalo: true });
  },
};

// 6 ── Велосипед ────────────────────────────────────────────────────────────
const bicycle = {
  id: 'bicycle', name: 'Велосипед', tags: ['движение', 'день'], dur: 15,
  draw(p, t, S) {
    const gy = 1720, cx = 520, wheelR = 175;
    p.hills(gy, { n: 7, amp: 60, t0: .4, t1: 1.7, seed: 4 });
    p.sun(880, 330, 96, { t0: .5, t1: 1.7, role: 'accent', rays: 12 });
    p.cloud(260, 420, 86, { t0: 1.2, t1: 2.4, seed: 2, alpha: .9 });
    p.cloud(660, 320, 62, { t0: 1.6, t1: 2.8, seed: 6, alpha: .8 });
    bushes(p, t, S, { y: gy + 10, speed: 190, n: 6, t0: 2, scale: 1.2 });
    p.line(-20, gy + 12, 1100, gy + 16, { w: 1.6, t0: .2, t1: .9 });
    const spin = t * 4.4;
    const wL = [cx - 210, gy - wheelR], wB = [cx + 210, gy - wheelR];
    for (const [k, w] of [wL, wB].entries()) {
      p.circle(w[0], w[1], wheelR, { w: 1.8, t0: 1.4 + k * .4, t1: 2.6 + k * .4 });
      p.circle(w[0], w[1], wheelR - 30, { w: .85, t0: 1.8 + k * .4, t1: 2.8 + k * .4 });
      for (let i = 0; i < 12; i++) {
        const a = spin + i / 12 * TAU;
        p.ink([[w[0], w[1]], [w[0] + Math.cos(a) * (wheelR - 30), w[1] + Math.sin(a) * (wheelR - 30)]], { w: .55, alpha: .75, t0: 2.1 + k * .4, t1: 2.7 + k * .4 });
      }
      p.dot(w[0], w[1], 9, { w: 1 });
    }
    const bb = [cx + 30, gy - 130], seat = [cx - 120, gy - 520], bars = [cx + 250, gy - 500];
    p.ink([wL, bb, wB], { w: 1.6, t0: 2.4, t1: 3.4 });
    p.ink([bb, seat], { w: 1.5, t0: 2.6, t1: 3.6 });
    p.ink([seat, bars], { w: 1.5, t0: 2.7, t1: 3.7 });
    p.ink([bars, wB], { w: 1.5, t0: 2.8, t1: 3.8 });
    p.ink([[bars[0] - 6, bars[1]], [bars[0] + 46, bars[1] - 84]], { w: 1.3, t0: 3, t1: 3.8 });
    p.ink([[bars[0] + 4, bars[1] - 90], [bars[0] + 124, bars[1] - 90]], { w: 1.3, t0: 3.1, t1: 3.9 });
    p.ink([[seat[0] - 52, seat[1] - 14], [seat[0] + 52, seat[1] - 6]], { w: 1.6, t0: 3.2, t1: 3.9 });
    // педали
    const crankR = 58, pa = spin;
    const ped1 = [bb[0] + Math.cos(pa) * crankR, bb[1] + Math.sin(pa) * crankR];
    const ped2 = [bb[0] - Math.cos(pa) * crankR, bb[1] - Math.sin(pa) * crankR];
    p.ink([bb, ped1], { w: 1.3, t0: 3.2, t1: 3.9 });
    p.ink([bb, ped2], { w: 1.3, t0: 3.2, t1: 3.9 });
    p.ink([ped1, [ped1[0] + 34, ped1[1]]], { w: 1.6, t0: 3.3, t1: 4 });
    p.ink([ped2, [ped2[0] + 34, ped2[1]]], { w: 1.6, t0: 3.3, t1: 4 });
    // велосипедистка
    const bob = Math.sin(t * 8.6) * 4;
    const hip = [seat[0] + 8, seat[1] - 48 + bob];
    const sho = [hip[0] + 62, hip[1] - 172 + bob * .4];
    const hand = [bars[0] + 52, bars[1] - 92];
    const headR = 54, head = [sho[0] + 26, sho[1] - headR * 1.45];
    const armL = ik(sho, hand, 200, 200, -1);
    const leg1 = ik(hip, [ped1[0] + 26, ped1[1] - 6], 240, 240, 1), leg2 = ik(hip, [ped2[0] + 26, ped2[1] - 6], 240, 240, 1);
    person(p, {
      hip, sho, head, headR, skirt: 96, skirtLen: 150, bell: 1, dress: true,
      kL: leg1[1], fL: leg1[2], kR: leg2[1], fR: leg2[2],
      eL: armL[1], hL: armL[2], eR: ik(sho, hand, 200, 200, -1)[1], hR: hand,
    }, { t0: 3.6, t1: 5.6, w: 1.3, fill: 'fill', wind: 1.5, feet: true, mouth: true, hairLen: .7, hairQ: 3 });
    // линии скорости
    for (let i = 0; i < 8; i++) {
      const y = gy - 220 - i * 130 + Math.sin(t * 3 + i) * 12;
      p.ink([[-60, y], [150 + i * 34, y - 8]], { w: .8, alpha: .5, role: 'accent', t0: 5.4, t1: 6 });
    }
    dust(p, t, S, { n: 8, y0: 800, y1: 1500, seed: 21 });
    p.text('поехали', 540, 300, { size: 108, align: 'center', t0: 5.8, t1: 7.4, underline: true, halo: false, noHalo: true });
  },
};

// 7 ── Дерево и качели ──────────────────────────────────────────────────────
const tree_swing = {
  id: 'tree_swing', name: 'Дерево и качели', tags: ['спокойное', 'природа'], dur: 16,
  draw(p, t, S) {
    const base = 1840, tx = 540;
    p.line(-20, base, 1100, base + 6, { w: 1.6, t0: .1, t1: .8 });
    p.grass(base, { n: 26, t0: 1.6, h0: 18, h1: 46 });
    // ствол
    p.shape([[tx - 76, base], [tx - 48, 1180], [tx - 30, 760], [tx + 34, 760], [tx + 54, 1180], [tx + 84, base]],
      { closeShape: true, fill: 'fill', stroke: 'main', w: 1.9, t0: .3, t1: 2.2, spacing: 34, angle: .06 });
    const R = U.mulberry(515 + S.seed);
    for (let i = 0; i < 12; i++) {
      const y = U.lerp(800, base - 60, i / 11);
      p.ink([[tx - 34 + R() * 22, y], [tx + 12 + R() * 40, y + U.lerp(50, 110, R())]], { w: .9, alpha: .7, t0: 1.4 + i * .1, t1: 2.1 + i * .1 });
    }
    // ветки
    const branches = [
      [[tx, 1000], [tx - 260, 830], [tx - 445, 730]],
      [[tx + 12, 950], [tx + 280, 800], [tx + 480, 740]],
      [[tx - 6, 860], [tx - 150, 680], [tx - 280, 590]],
      [[tx + 18, 840], [tx + 190, 660], [tx + 330, 560]],
      [[tx, 780], [tx - 50, 600], [tx - 20, 460]],
      [[tx + 10, 760], [tx + 70, 580], [tx + 170, 450]],
    ];
    branches.forEach((b, i) => p.curve(b, { w: 1.6 - i * .1, t0: 1 + i * .2, t1: 2.3 + i * .2, smooth: .6 }));
    // листва
    foliage(p, tx - 350, 660, 320, 210, Math.round(22 * S.dens), { t0: 2.4, step: .1, fill: 'fill', stroke: 'main', w: .85, spacing: 18, scale: 1.25 });
    foliage(p, tx + 300, 600, 320, 220, Math.round(22 * S.dens), { t0: 2.8, step: .1, fill: 'fill', stroke: 'main', w: .85, spacing: 18, scale: 1.25, seed: 3 });
    foliage(p, tx - 20, 470, 290, 170, Math.round(16 * S.dens), { t0: 3.4, step: .1, fill: 'fill', stroke: 'main', w: .85, spacing: 18, scale: 1.2, seed: 7 });
    // качели
    const piv = [tx - 330, 790], sw = Math.sin(t * (TAU / 3.8)) * .3, len = 520;
    const seatC = [piv[0] + Math.sin(sw) * len, piv[1] + Math.cos(sw) * len];
    p.ink([piv, [seatC[0] - 70, seatC[1]]], { w: 1.4, t0: 4.2, t1: 5 });
    p.ink([piv, [seatC[0] + 70, seatC[1]]], { w: 1.4, t0: 4.2, t1: 5 });
    p.rect(seatC[0] - 104, seatC[1], 208, 20, { r: 3, w: 1.6, t0: 4.6, t1: 5.4 });
    const dir = [Math.sin(sw), Math.cos(sw)];      // вдоль верёвки
    const seatL = [seatC[0] - 92 * dir[1], seatC[1] + 92 * dir[0]];
    const seatR = [seatC[0] + 92 * dir[1], seatC[1] - 92 * dir[0]];
    p.figure(seatC[0], seatC[1] + 6, .92, {
      footL: seatL, footR: seatR,
      handL: [piv[0] - 80 + Math.sin(sw) * 250, piv[1] + Math.cos(sw) * 250],
      handR: [piv[0] + 80 + Math.sin(sw) * 250, piv[1] + Math.cos(sw) * 250],
      lean: .25 * Math.sin(sw) * 3, lL: [-.05, .08], lR: [.05, .08],
      skirtLen: 150, skirt: 92, bell: 1.1, wind: 1.4,
    }, { t0: 5, t1: 6.6, w: 1.15, fill: 'fill', hairLen: 1.6, hairQ: 5, mouth: true });
    // птица прилетает
    const fly = U.ss(8, 10.2, t);
    const bx2 = U.lerp(1180, tx + 360, fly), by2 = U.lerp(220, 660 + Math.sin(t * 2) * 8, fly);
    p.bird(bx2, by2, 28, { w: 1.1, t0: 8, t1: 8.4 });
    if (t > 10.4) p.bird(tx + 360, 666, 28, { w: 1.1, t0: 10.4, t1: 10.5 });
    // падающие листья
    if (t > 6) for (let i = 0; i < 6; i++) {
      const life = 6, ph = ((t + i * 1.3) % life) / life;
      const lx = U.lerp(240, 860, U.hash(i * 3.7)) + Math.sin(ph * 8 + i) * 70;
      p.leaf(lx, 620 + ph * 1180, 40, ph * 7 + i, { w: .9, role: 'accent', t0: 0, t1: .01, alpha: .85, c: 4 });
    }
    p.text('качели', 540, 1790, { size: 96, align: 'center', t0: 7, t1: 8.6, underline: true, halo: true });
  },
};

// 8 ── Сердце ───────────────────────────────────────────────────────────────
const heart = {
  id: 'heart', name: 'Сердце', tags: ['энергия', 'любовь'], dur: 12,
  draw(p, t, S) {
    const pulse = S.pulse ? S.pulse(t) : Math.abs(Math.sin(t * 2.4));
    const k = 1 + .07 * pulse, cx = 540, cy = 720 - pulse * 8, s = 220 * k;
    p.shape(U.heartPts(cx, cy, s), { closeShape: true, fill: 'fill', stroke: 'main', w: 2.3, spacing: 24, t0: .4, t1: 3.2, angle: -.35 });
    p.shape(U.heartPts(cx, cy, s * 1.14), { closeShape: true, fill: false, stroke: 'accent', w: 1, t0: 3, t1: 4.4, alpha: .55 + pulse * .4 });
    sparkBurst(p, cx, cy, t, { period: S.beatDur ? S.beatDur(t) * 2 : 1.4, n: 10, r0: s * .55, r1: 340, t0: 1.2, seed: 7, life: 1.3 });
    // кардиограмма
    const y0 = 1650, x0 = 90, w = 900, head = U.clamp((t - 2) / 3, 0, 1);
    const pts = [];
    let x = x0;
    pts.push([x, y0]);
    while (x < x0 + w) {
      const seg = [[36, 0], [16, 0], [10, -26], [10, 96], [12, -112], [12, 42], [14, 0], [40, 0]];
      for (const [dx, dy] of seg) { x += dx; pts.push([x, y0 + dy]); }
    }
    p.ink(pts, { w: 1.3, role: 'accent', frac: head, t0: 0, t1: .001, smooth: .3 });
    if (head >= 1) {
      const hx = x0 + (t * 210) % w;
      p.dot(hx, y0, 7, { role: 'accent' });
      const q = Math.round((hx - x0) / 40) % 8;
      p.text('♥', hx, y0 - 40, { size: 26, role: 'accent', align: 'center', t0: 0, t1: .001 });
    }
    p.text('мне сегодня', 540, 1320, { size: 84, align: 'center', t0: 3.6, t1: 5 });
    p.text('можно', 540, 1490, { size: 140, align: 'center', t0: 4.4, t1: 6, underline: true });
    const R = U.mulberry(31 + S.seed);
    for (let i = 0; i < 8; i++) {
      const a = R() * TAU, r = 400 + R() * 220;
      p.heart(cx + Math.cos(a) * r, cy + Math.sin(a) * r * .8, 30 + R() * 20, { closeShape: true, w: 1, role: 'accent', alpha: .8, t0: 2 + i * .22, t1: 2.7 + i * .22 });
    }
  },
};

export const SCENES_A = [window_rain, cat_sleep, city_night, stars, coffee, bicycle, tree_swing, heart];
