// scenes2.js — вторая половина библиотеки сцен.
import * as U from './util.js';
import { PAGE } from './paper.js';
import { skyStars, sparkBurst, dust, foliage, equalizer, notesFlying, scribbleText, person } from './common.js';
const TAU = U.TAU, PI = U.PI, ik = U.ik;

// 9 ── Лодка и море ─────────────────────────────────────────────────────────
const boat = {
  id: 'boat', name: 'Лодка и море', tags: ['спокойное', 'вода', 'вечер'], dur: 15,
  draw(p, t, S) {
    const hor = 1140;
    const sunY = hor - 150 + Math.sin(t * .3) * 12;
    p.circle(830, sunY, 96, { w: 1.7, role: 'accent', t0: .4, t1: 1.7 });
    p.ray(830, sunY, -PI * .95, -PI * .05, 120, 210, 11, { role: 'accent', alpha: .6, t0: 1, t1: 1.8 });
    p.cloud(240, 460, 90, { t0: 1.4, t1: 2.6, seed: 4 });
    p.cloud(880, 360, 68, { t0: 1.8, t1: 3, seed: 9 });
    p.line(-20, hor, 1100, hor + 4, { w: 1.5, t0: .2, t1: .9 });
    // отражение
    for (let i = 0; i < 10; i++) {
      const y = hor + 30 + i * 42, w = 60 + i * 20;
      p.ink(U.wobbleLine(830 - w, y, 830 + w, y, 5, i * 2, 9), { w: .95, role: 'accent', alpha: .7 - i * .055, t0: 1.2 + i * .12, t1: 2 + i * .12 });
    }
    // волны
    p.waves(-40, 1120, 1250, 30, 7, { t0: 2, step: .22, dur: 1.1, gap: 84, waves: 3, vary: 1.2 });
    // лодка
    const rock = Math.sin(t * (TAU / 2.8)) * .05, dx = Math.sin(t * (TAU / 3.4)) * 18;
    const bx = 520 + dx, by = 1560;
    p.shape(U.catmull([[bx - 250, by - 60], [bx - 110, by + 84], [bx + 110, by + 84], [bx + 250, by - 60], [bx + 180, by - 68], [bx - 180, by - 68]], 6, true),
      { closeShape: true, fill: 'fill', stroke: 'main', w: 1.7, spacing: 26, t0: 2.6, t1: 4.2, angle: -.15 });
    const mastTop = [bx + rock * 900, by - 700];
    p.ink([[bx, by - 60], mastTop], { w: 1.7, t0: 3.4, t1: 4.3 });
    p.shape([[bx + 8, by - 640], [bx + 300, by - 90], [bx + 8, by - 90]], { closeShape: true, fill: 'fill', stroke: 'main', w: 1.6, t0: 3.8, t1: 5.2, spacing: 30, angle: -.2 });
    p.shape([[bx - 10, by - 610], [bx - 210, by - 90], [bx - 10, by - 90]], { closeShape: true, fill: 'fill', stroke: 'main', w: 1.3, t0: 4.2, t1: 5.6, spacing: 30, angle: .2 });
    p.ink([[mastTop[0], mastTop[1]], [mastTop[0] + 80 + Math.sin(t * 3) * 14, mastTop[1] + 20]], { w: 1.1, t0: 4.4, t1: 4.9 });
    for (let i = 0; i < 6; i++) {
      const x = U.lerp(140, 980, U.hash(i * 2.3)), y = 1380 + (i % 3) * 70 + Math.sin(t * 2 + i) * 10;
      p.ink(U.humps(x - 46, x + 46, y, 3, 18, i), { w: .9, alpha: .6, t0: 4.6 + i * .14, t1: 5.5 + i * .14 });
    }
    // чайки
    if (t > 4) for (let i = 0; i < 4; i++) {
      const life = 8, ph = ((t + i * 2.2) % life) / life;
      p.bird(U.lerp(-100, 1180, ph), 380 + i * 90 + Math.sin(ph * 6 + i) * 46, 28 + i * 4, { w: 1, t0: 0, t1: .01 });
    }
    p.text('некуда спешить', 540, 330, { size: 104, align: 'center', t0: 5.4, t1: 7.2, underline: true, halo: false, noHalo: true });
  },
};

// 10 ── Шарик улетает ───────────────────────────────────────────────────────
const balloon = {
  id: 'balloon', name: 'Воздушный шарик', tags: ['движение', 'день', 'детское'], dur: 14,
  draw(p, t, S) {
    const gy = 1840, fx = 470;
    p.line(-20, gy, 1100, gy + 6, { w: 1.6, t0: .1, t1: .8 });
    p.grass(gy, { n: 22, t0: 1, h0: 16, h1: 40 });
    p.sun(200, 360, 88, { t0: .4, t1: 1.6, role: 'accent', rays: 11 });
    p.cloud(780, 440, 84, { t0: 1.2, t1: 2.4, seed: 5 });
    p.cloud(340, 620, 62, { t0: 1.6, t1: 2.8, seed: 8, alpha: .8 });
    for (let i = 0; i < 9; i++) {
      const x = 940 + Math.sin(t * 2 + i) * 34, y = 620 + i * 120;
      p.ink(U.wobbleLine(x - 150, y - 24, x, y, 7, i * 3, 8), { w: .85, alpha: .45, role: 'accent', t0: 3.4 + i * .1, t1: 4.4 + i * .1 });
    }
    // шарик: держат, потом отпускают
    const rel = 5.4, up = U.ss(rel, rel + .5, t), fly = Math.max(0, t - rel);
    const bx = fx + 230 + up * (fly * 24) + Math.sin(t * 2.2) * 16 * (1 - up * .6);
    const by = 1080 - fly * 95 - up * fly * 26 + Math.sin(t * 1.8) * 20 * (1 - up * .6);
    const R0 = 190 + up * 8;
    p.balloon(bx, by, R0, { fill: 'fill', stroke: 'main', w: 1.8, thread: [0, 0], spacing: 26, t0: 1.6, t1: 3.2, c: 0, smooth: .5 });
    p.ink([[bx - 30 * (1 - up), by + R0 * .42], [bx - 60, by + R0 * .3], [bx - 46, by - R0 * .1], [bx - 8, by - R0 * .62]], { w: 1, alpha: .8, t0: 2.4, t1: 3.2 });
    // нитка к руке
    if (t < rel + .7) p.ink([[bx, by + R0], [U.lerp(bx, fx + 150, .45), U.lerp(by + R0 + 160, 1600, .5)], [fx + 152, 1596]], { w: 1.05, smooth: .85, t0: 2.2, t1: 3.4 });
    // девочка
    const waving = U.ss(rel + .3, rel + 1.2, t), ph = t * 2.8;
    const hand = waving ? [fx + 120 + Math.sin(ph * 3) * 40, 1290 + Math.cos(ph * 3) * 34] : [bx, by + R0 * .96];
    const sho = [fx, gy - 430], headR = 58, head = [fx + 8, sho[1] - headR * 1.45], hip = [fx, gy - 250];
    const legL = ik(hip, [fx - 96, gy], 240, 240, 1), legR = ik(hip, [fx + 104, gy], 240, 240, 1);
    const armL = ik(sho, hand, 190, 190, 1);
    person(p, {
      hip, sho, head, headR, skirt: 130, skirtLen: 210, bell: 1.2,
      kL: legL[1], fL: legL[2], kR: legR[1], fR: legR[2],
      eL: armL[1], hL: armL[2], eR: [sho[0] - 95, sho[1] + 120], hR: [sho[0] - 120, sho[1] + 215],
    }, { t0: 2.2, t1: 4.6, w: 1.3, fill: 'fill', wind: 1.5, feet: true, mouth: true, hairLen: 1.1, hairQ: 4, eyes: t > rel + 1.2 ? 'closed' : 'open' });
    // птицы следом
    if (t > rel) for (let i = 0; i < 3; i++) {
      const lifeP = 8, k = ((t + i * 2.6) % lifeP) / lifeP;
      p.bird(120 + k * 1000, 1120 - k * 620 - i * 70, 24, { w: .95, t0: 0, t1: .01, alpha: .9 });
    }
    p.text('ветер в лицо', 540, 320, { size: 100, align: 'center', t0: 5.8, t1: 7.6, underline: true, halo: false, noHalo: true });
  },
};

// 11 ── Цветы ───────────────────────────────────────────────────────────────
const flowers = {
  id: 'flowers', name: 'Цветы', tags: ['природа', 'утро', 'рост'], dur: 15,
  draw(p, t, S) {
    const gy = 1860;
    p.line(-20, gy, 1100, gy + 6, { w: 1.6, t0: .1, t1: .8 });
    p.hills(gy, { n: 5, amp: 90, t0: .4, t1: 1.7, seed: 2 });
    p.sun(870, 360, 96, { t0: .5, t1: 1.7, role: 'accent', rays: 12 });
    p.cloud(300, 430, 78, { t0: 1.2, t1: 2.4, seed: 3 });
    const R = U.mulberry(2024 + S.seed);
    const n = Math.round(6 * S.dens) + 2;
    for (let i = 0; i < n; i++) {
      const x = 150 + i * (800 / Math.max(1, n - 1)) + (R() - .5) * 46;
      const grow = U.ss(1.2 + i * .6, 4.8 + i * .6, t);
      const h = U.lerp(560, 860, R()) * grow, bend = (R() - .5) * 80;
      const top = [x + bend, gy - h];
      p.ink([[x, gy], [x + bend * .35, gy - h * .55], [x + bend * .8, gy - h * .82], top], { w: 1.6, smooth: .8, t0: 1.2 + i * .6, t1: 4.8 + i * .6 });
      for (const s of [-1, 1]) if (R() < .85) {
        const ly = gy - h * U.lerp(.25, .62, R());
        p.leaf(x + bend * .3, ly, U.lerp(110, 180, R()), s < 0 ? PI * .94 : PI * .06, { w: 1.2, t0: 3.6 + i * .6, t1: 4.6 + i * .6, c: 4, fill: 'fill', spacing: 22 });
      }
      p.flower(top[0], top[1], U.lerp(52, 74, R()) * (.5 + grow * .5), { t0: 5 + i * .5, pd: .2, ddur: .6, c: i % 2 ? 0 : 2, coreRole: 'accent', petals: R() < .4 ? 5 : 6, rot: R(), fill: 'fill', spacing: 16 });
    }
    // пчёлы
    if (t > 5.5) for (let i = 0; i < 5; i++) {
      const life = 5.6, ph = ((t + i * 1.7) % life) / life;
      const bx = 200 + i * 180 + Math.sin(ph * TAU * 2 + i) * 150, by = 1150 - Math.sin(ph * PI) * 480 - i * 30;
      p.dot(bx, by, 13, { role: 'accent' });
      p.ink([[bx - 8, by - 16], [bx - 4, by + 12]], { w: .8, t0: 0, t1: .01, alpha: .55 });
      p.ink([[bx + 4, by - 16], [bx + 8, by + 12]], { w: .8, t0: 0, t1: .01, alpha: .55 });
      p.ink([[bx + 12, by + 6], [bx + 46, by - 10]], { w: 1, t0: 0, t1: .01, alpha: .8 });
    }
    p.grass(gy, { n: 30, t0: 6, h0: 20, h1: 56, c: 3, role: 'fill' });
    p.text('расти', 540, 330, { size: 118, align: 'center', t0: 7, t1: 8.8, underline: true, halo: false, noHalo: true });
  },
};

// 12 ── Ноты и наушники ─────────────────────────────────────────────────────
const music = {
  id: 'music', name: 'Ноты и наушники', tags: ['музыка', 'энергия'], dur: 13,
  draw(p, t, S) {
    const y0 = 640, gap = 46;
    for (let i = 0; i < 5; i++) p.line(80, y0 + i * gap, 1000, y0 + i * gap + 2, { w: .9, role: 'accent', alpha: .6, t0: .2 + i * .12, t1: 1 + i * .12 });
    // скрипичный ключ
    p.ink(U.spiralPts(196, 700, 10, 74, 1.5, PI * .4, 60), { w: 1.6, t0: 1, t1: 2.2 });
    p.ink([[196, 690], [200, 860], [176, 900]], { w: 1.6, smooth: .6, t0: 1.2, t1: 2.4 });
    p.ink([[176, 900], [212, 880], [210, 820]], { w: 1.4, smooth: .6, t0: 1.6, t1: 2.6 });
    // ноты на стане прыгают в такт
    const beat = S.beat ? S.beat(t) : (t * (S.bpm / 60)) % 1;
    const lanes = [20, 26, 32, 24, 30, 22, 28];
    for (let i = 0; i < 7; i++) {
      const x = 320 + i * 100, lane = lanes[i];
      const jump = Math.abs(Math.sin((t - i * .16) * 3.4 + beat * .4)) * 52;
      p.note(x, y0 + lane + 36 - jump, 52, { ...p.seq(i, 1.4, .2, .7), role: 'main', c: i % 2 ? 0 : 4, alpha: 1 });
    }
    // наушники
    p.headphones(540, 1230, 150, { t0: 3.2, t1: 5, fill: 'fill', w: 1.9, c: 4, spacing: 22 });
    p.ray(540, 1230, -PI * .8, -PI * .2, 190, 330, 7, { role: 'accent', alpha: .45, t0: 4.4, t1: 5.4, step: .08 });
    notesFlying(p, t, S, { n: 6, x: 540, y: 1180, rise: 760, size: 36, wob: 90, seed: 3 });
    equalizer(p, t, S, { n: 13, x0: 160, x1: 920, y: 1790, h: 190, t0: 3, gain: .95 });
    p.text('громче', 540, 300, { size: 112, align: 'center', t0: 5.4, t1: 7, underline: true, halo: false, noHalo: true });
  },
};

// 13 ── Танец ───────────────────────────────────────────────────────────────
const dance = {
  id: 'dance', name: 'Танец', tags: ['энергия', 'музыка', 'движение'], dur: 12,
  draw(p, t, S) {
    const gy = 1760, bpm = S.bpm || 120, beats = t * bpm / 60, ph = beats * .5;
    const pulse = S.pulse ? S.pulse(t) : Math.abs(Math.sin(t * 2.4));
    const hop = -Math.max(0, Math.sin(beats * PI)) * 30;
    equalizer(p, t, S, { n: 15, x0: 100, x1: 980, y: 1930, h: 280, t0: .6, gain: 1 });
    p.ellipse(540, gy + 30, 320, 50, { w: 1.2, role: 'accent', t0: 1, t1: 2.2, over: .3 });
    p.ray(540, 1200, -PI * .92, -PI * .08, 430 + pulse * 40, 640 + pulse * 100, 11, { role: 'accent', alpha: .3 + pulse * .3, t0: 2.6, t1: 3.6, step: .05 });
    sparkBurst(p, 540, gy - 480, t, { period: S.beatDur ? S.beatDur(t) : .5, n: 7, r0: 50, r1: 200, life: .85, seed: 11 });
    p.figure(540, gy + hop, 1.42, { ...p.dancePose(ph % 1), skirt: 150, bell: 1.35, wind: 1.5, mouth: true }, { t0: 1.4, t1: 3.4, legRole: 'main', w: 1.35 });
    notesFlying(p, t, S, { n: 7, x: 540, y: gy - 240, rise: 900, size: 38, wob: 170, seed: 5 });
    p.text('танцуй', 540, 300, { size: 118, align: 'center', t0: 4.4, t1: 6.2, underline: true, halo: false, noHalo: true });
  },
};

// 14 ── Список дел ──────────────────────────────────────────────────────────
const todo = {
  id: 'todo', name: 'Список дел', tags: ['дом', 'сюжет'], dur: 14,
  draw(p, t, S) {
    const x0 = 170, y0 = 640, rowH = 170;
    p.text('дела', x0, 520, { size: 118, t0: .2, t1: 1.3, underline: true });
    scribbleText(p, x0 + 420, 508, 240, { w: 1, t0: 1.2, t1: 2, seed: 4 });
    const rows = 5;
    const lens = [];
    for (let i = 0; i < rows; i++) {
      const y = y0 + i * rowH, len = U.lerp(340, 520, U.hash(i * 3.1));
      lens.push(len);
      p.box(x0, y - 52, 62, { w: 1.4, t0: .8 + i * .22, t1: 1.7 + i * .22, r: 8 });
      scribbleText(p, x0 + 96, y - 26, len, { w: 1.1, t0: 1.1 + i * .22, t1: 2.1 + i * .22, seed: i * 7 });
    }
    // зачёркиваем дела
    const strikes = [{ i: 0, t0: 3.0 }, { i: 1, t0: 4.2 }, { i: 2, t0: 5.4 }, { i: 3, t0: 6.6 }];
    strikes.forEach(s => {
      const y = y0 + s.i * rowH - 26, xA = x0 + 96, xB = xA + lens[s.i];
      const done = U.ss(s.t0, s.t0 + .75, t);
      p.scribbleOut(xA - 12, xB, y, { t0: s.t0, t1: s.t0 + .75, n: 2, role: 'accent', w: 1.4 });
      if (t > s.t0 - .6 && t < s.t0 + 1.3) {
        const px = U.lerp(xA - 40, xB + 40, done), py = U.lerp(y - 70, y + 30, done);
        penTool(p, px + 100, py - 170, .85, { t0: s.t0 - .6, t1: s.t0 + 1.3 });
      }
      if (t > s.t0 + .85) {
        p.box(x0, y0 + s.i * rowH - 52, 62, { w: 1.4, t0: s.t0 + .85, t1: s.t0 + 1.3, r: 8, role: 'accent' });
        p.tick(x0 + 31, y0 + s.i * rowH - 22, 64, { t0: s.t0 + .95, t1: s.t0 + 1.6, w: 1.6, role: 'accent' });
      }
    });
    // последняя строка превращается в цветок
    const y = y0 + 4 * rowH, bloom = U.ss(8.8, 10.6, t);
    if (bloom > 0) {
      p.ink([[x0 + 96, y - 26], [x0 + 96 + 300 * (1 - bloom), y - 26 + Math.sin(t * 2) * 3]], { w: 1.1, alpha: 1 - bloom * .85, t0: 8.6, t1: 9.4 });
      p.ink([[x0 + 400, y - 26], [x0 + 400, y - 90 - 80 * bloom], [x0 + 430 + 40 * bloom, y - 190 - 120 * bloom]], { w: 1.5, smooth: .7, t0: 9, t1: 10.4 });
      p.leaf(x0 + 400, y - 120, 130, PI * .05, { w: 1.1, t0: 9.4, t1: 10.2, c: 4 });
      p.leaf(x0 + 404, y - 160, 120, PI * .95, { w: 1.1, t0: 9.6, t1: 10.4, c: 4 });
      p.flower(x0 + 440 + 50 * bloom, y - 330 - 90 * bloom, 70 * bloom, { t0: 9.8, pd: .18, c: 0, petals: 6, fill: 'fill', spacing: 16 });
    }
    p.text('ничего не надо', 540, 1600, { size: 84, align: 'center', t0: 10.8, t1: 12.6 });
    p.text('можно', 540, 1760, { size: 138, align: 'center', t0: 11.6, t1: 13.4, underline: true });
  },
};
function penTool(p, x, y, s, o = {}) {   // ручка/карандаш в кадре
  const ang = -.62, L = 320 * s;
  p.ink([[x, y], [x + Math.cos(ang) * L, y + Math.sin(ang) * L]], { ...o, w: 6, role: 'main', alpha: .95 });
  p.ink([[x + 14, y - 10], [x + Math.cos(ang) * L + 14, y + Math.sin(ang) * L - 10]], { ...o, w: 1.2, role: 'accent', alpha: .8 });
  p.ink([[x, y], [x - 40 * s, y + 26 * s]], { ...o, w: 2.6, role: 'main' });
}

// 15 ── Торт со свечами ────────────────────────────────────────────────────
const cake = {
  id: 'cake', name: 'Торт со свечами', tags: ['праздник', 'энергия'], dur: 13,
  draw(p, t, S) {
    const gy = 1800, cx = 540;
    p.line(-20, gy + 60, 1100, gy + 66, { w: 1.6, t0: .1, t1: .8 });
    p.ellipse(cx, gy + 40, 460, 52, { w: 1.3, t0: .8, t1: 1.9, role: 'accent', over: .3 });
    const tiers = [[-390, 250], [-300, 230], [-210, 210]];
    let topY = gy;
    tiers.forEach(([dx, h], i) => {
      const yy = topY;
      p.shape(U.catmull([[cx + dx, yy], [cx - dx, yy], [cx - dx + 8, yy - h], [cx + dx - 8, yy - h]], 5, true),
        { closeShape: true, fill: 'fill', stroke: 'main', w: 1.7, spacing: 30, t0: 1 + i * .5, t1: 2.3 + i * .5, c: i % 2 ? 1 : 6, angle: -.12 });
      p.ink(U.humps(cx - dx + 8, cx + dx - 8, yy - h, 7, 22, i * 3), { w: 1.3, t0: 1.6 + i * .5, t1: 2.7 + i * .5, role: 'accent' });
      topY -= h;
    });
    // свечи
    const n = (S.params && S.params.candles) || 5;
    for (let i = 0; i < n; i++) {
      const x = cx - 150 + i * (300 / Math.max(1, n - 1)), T = p.seq(i, 3.4, .2, .6);
      p.rect(x - 6, topY - 140, 12, 140, { ...T, w: 1, c: i % 2 ? 0 : 2 });
      p.ink([[x, topY - 140], [x, topY - 154]], { ...T, w: .9 });
      const fl = Math.sin(t * 8 + i) * 7;
      p.ink([[x - 12, topY - 158], [x + fl, topY - 206], [x + 12, topY - 158], [x + fl, topY - 168], [x - 12, topY - 158]],
        { ...T, w: 1, role: 'accent', smooth: .6 });
      p.dot(x + fl * .6, topY - 186, 4.6, { role: 'accent', ...T });
    }
    // конфетти
    const R = U.mulberry(303 + S.seed);
    if (t > 3) for (let i = 0; i < 24; i++) {
      const life = 4.4, ph = ((t + i * .41) % life) / life, x = R() * 1080 + Math.sin(ph * 6 + i) * 46, y = -60 + ph * 1500;
      p.ink([[x - 14, y], [x + 14, y + Math.sin(ph * 4 + i) * 10]], { w: 1.2, role: 'fill', c: i % 3, t0: 0, t1: .01, alpha: .9 });
    }
    // кусок на тарелке
    p.ellipse(180, gy + 30, 150, 34, { w: 1.2, t0: 4.6, t1: 5.7 });
    p.shape([[122, gy + 20], [122, gy - 130], [238, gy - 170], [238, gy + 20]], { closeShape: true, fill: 'fill', stroke: 'main', w: 1.3, t0: 5, t1: 6.2, spacing: 20, c: 1 });
    p.text('с днём', 540, 500, { size: 150, align: 'center', t0: 6, t1: 7.8, underline: true });
  },
};

// 16 ── Финал: фраза-подушка ────────────────────────────────────────────────
const pillow = {
  id: 'pillow', name: 'Финал: фраза-подушка', tags: ['финал', 'вечер', 'спокойное'], dur: 16,
  draw(p, t, S) {
    // окно с месяцем
    p.rect(700, 260, 300, 320, { r: 8, w: 1.5, t0: .2, t1: 1.1 });
    p.line(850, 260, 850, 580, { w: 1.1 });
    p.line(700, 420, 1000, 420, { w: 1.1 });
    p.moon(920, 340, 46, { t0: .6, t1: 1.7 });
    skyStars(p, t, S, { n: 10, x0: 715, y0: 275, x1: 985, y1: 565, t0: 1, seed: 4 });
    // торшер
    p.line(170, 1560, 170, 1180, { w: 1.6, t0: 1, t1: 2.1 });
    p.shape([[104, 1180], [236, 1180], [212, 1104], [128, 1104]], { closeShape: true, fill: 'fill', stroke: 'main', w: 1.4, t0: 1.4, t1: 2.6, spacing: 24, angle: .4 });
    p.shade(60, 1100, 360, 480, { angle: .68, spacing: 34, t0: 2.4, t1: 4.2, alpha: .38 });
    // фраза рукописью + облако вокруг
    const txt1 = 'мне сегодня', txt2 = 'можно';
    p.text(txt1, 520, 760, { size: 96, align: 'center', t0: 1.2, t1: 3.4 });
    const grow = U.ss(3.4, 6, t);
    p.cloud(520, 720, 80 + grow * 150, { fill: false, stroke: 'accent', w: 1.3, t0: 3.4, t1: 5.6, seed: 3, alpha: .9 });
    p.shape(U.cloudPts(520, 720, 86 + grow * 140, 3), { closeShape: true, fill: 'fill', stroke: 'main', w: 1.6, t0: 3.6, t1: 6, spacing: 34, alpha: grow * .9 });
    p.text(txt2, 520, 940, { size: 132, align: 'center', t0: 4.4, t1: 6.2, underline: true });
    // кровать, одеяло, спящая
    const bedY = 1560;
    p.line(-20, bedY + 190, 1100, bedY + 194, { w: 1.6, t0: .6, t1: 1.5 });
    p.cloud(240, bedY + 70, 170, { fill: 'fill', stroke: 'main', w: 1.5, t0: 2.4, t1: 3.8, seed: 7, spacing: 30 });
    const fx = 470, fy = bedY + 90;
    const breathe = Math.sin(t * 1.05) * 6;
    p.shape(U.catmull([[fx - 320, fy + 190], [fx - 300, fy + 40], [fx - 140, fy - 130 + breathe], [fx + 60, fy - 170 + breathe], [fx + 270, fy - 120 + breathe * .7], [fx + 400, fy + 60], [fx + 430, fy + 190]], 9, false),
      { closeShape: true, fill: 'fill', stroke: 'main', w: 1.8, t0: 6.4, t1: 9, spacing: 30, angle: -.1 });
    for (let i = 0; i < 5; i++) p.ink(U.humps(fx - 280 + i * 150, fx - 130 + i * 150, fy + 190, 3, 16, i), { w: 1.1, t0: 7 + i * .18, t1: 8.2 + i * .18 });
    // голова на подушке
    const hx = fx - 214, hy = fy - 40;
    p.circle(hx, hy, 74, { w: 1.5, t0: 5.4, t1: 6.6 });
    p.ink(U.arcPts(hx - 24, hy - 8, 19, 13, PI * 1.12, PI * 1.88, 10), { w: 1, t0: 6, t1: 6.6 });
    p.ink(U.arcPts(hx + 24, hy - 8, 19, 13, PI * 1.12, PI * 1.88, 10), { w: 1, t0: 6, t1: 6.6 });
    p.ink(U.arcPts(hx, hy + 24, 19, 14, PI * .2, PI * .8, 10), { w: .85, t0: 6.2, t1: 6.7 });
    for (let i = 0; i < 5; i++) {
      const a = PI * (.1 + i * .17);
      p.curve([[hx + Math.cos(a) * 56, hy + Math.sin(a) * 40], [hx + Math.cos(a) * 74, hy + Math.sin(a) * 74], [hx - 90 - i * 10, hy + 40 + i * 16]],
        { w: .95, t0: 6.2 + i * .12, t1: 7 + i * .12 });
    }
    // «с-с-с»
    const ph = ((t - 8) % 3.4) / 3.4;
    if (t > 8) {
      p.text('z', hx + 120, hy - 180 - ph * 130, { size: 58 + ph * 18, role: 'accent', alpha: .95 * (1 - ph), t0: 8, t1: 8.1, align: 'center' });
      if (ph > .4) p.text('z', hx + 172, hy - 110 - ph * 90, { size: 38 + ph * 14, role: 'accent', alpha: .75 * (1 - ph), t0: 8, t1: 8.1, align: 'center' });
    }
    // окно: тёплый свет идёт от лампы к кровати
    p.shade(240, 1160, 340, 460, { angle: .7, spacing: 40, t0: 9, t1: 10.4, alpha: .3 });
  },
};

export const SCENES_B = [boat, balloon, flowers, music, dance, todo, cake, pillow];
