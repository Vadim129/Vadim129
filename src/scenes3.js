// scenes3.js — свои картинки (фото в кадр и обводка в штрихи) + четыре новые сцены.
import * as U from './util.js';
import { PAGE } from './paper.js';
import { skyStars, sparkBurst, dust, foliage, equalizer, scribbleText, person } from './common.js';
import { fitStrokes, fitBox } from './image.js';
const TAU = U.TAU, PI = U.PI, ik = U.ik;

// ── фото в кадре: полароид со скотчем, подписью и каракулями ────────────────
export function makePhotoScene(asset) {
  return {
    id: 'my_photo', name: 'Моё фото (полароид)', tags: ['своё', 'фото'], dur: 12, dynamic: true,
    draw(p, t, S) {
      const cx = 540, cy = 900;
      const maxW = 700, maxH = 820;
      const k = Math.min(maxW / asset.canvas.width, maxH / asset.canvas.height);
      const w = asset.canvas.width * k, h = asset.canvas.height * k;
      const rot = -.035, grow = U.ss(.1, 1.1, t);
      const gg = .9 + grow * .1;
      const photo = { x: cx - w / 2 * gg, y: cy - h / 2 * gg, w: w * gg, h: h * gg };
      // бумажная рамка полароида
      p.rect(photo.x - 34, photo.y - 34, photo.w + 68, photo.h + 130, { r: 4, w: 1.6, t0: .3, t1: 1.4 });
      p.shade(photo.x - 30, photo.y + photo.h + 4, photo.w + 60, 92, { angle: .35, spacing: 9, t0: 1.2, t1: 2.6, alpha: .5 });
      // само фото (растр кладём на бумагу)
      p.raster(asset.canvas, photo.x, photo.y, photo.w, photo.h, { rot, t0: .5, t1: 1.6 });
      // скотч
      for (const [sx, sy, a] of [[photo.x - 20, photo.y - 26, -.5], [photo.x + photo.w - 66, photo.y - 26, .5]]) {
        p.shape([[sx, sy], [sx + 96, sy + (a > 0 ? -8 : 8)], [sx + 100, sy + 30], [sx + 4, sy + 34]], { closeShape: true, fill: 'fill', stroke: 'main', w: .9, t0: 1.4 + (a > 0 ? .3 : 0), t1: 2.2, spacing: 12, angle: .4, alpha: .8 });
      }
      // подпись от руки под фото (на паспарту, не на картинке)
      const cap = (S.params && S.params.caption) || (asset.caption && asset.caption()) || 'этот день';
      p.text(cap, cx, photo.y + photo.h + 78, { size: 60, align: 'center', t0: 2.6, t1: 4.4, underline: false });
      p.line(cx - 150, photo.y + photo.h + 100, cx + 150, photo.y + photo.h + 104, { w: 1.1, t0: 3.4, t1: 4.6, amp: 2.6 });
      // каракули вокруг
      p.heart(cx - 400, cy - 330, 40, { closeShape: true, w: 1.1, role: 'accent', t0: 4.2, t1: 5.2 });
      p.star(cx + 420, cy - 250, 44, { fill: 'fill', stroke: 'main', closeShape: true, t0: 4.6, t1: 5.6, c: 2 });
      p.sparkle(cx + 380, cy + 330, 34, { role: 'accent', t0: 4.8, t1: 5.4 });
      p.sparkle(cx - 420, cy + 250, 26, { role: 'accent', t0: 5.0, t1: 5.6 });
      const note = (S.params && S.params.caption) || (asset.note && asset.note()) || '';
      if (note) p.text(note, cx, 1740, { size: 58, align: 'center', role: 'accent', t0: 5.4, t1: 7 });
    },
  };
}

// ── обводка: своя картинка рисуется штрихами у тебя на глазах ───────────────
export function makeTraceScene(asset) {
  return {
    id: 'my_trace', name: 'Обводка рисунка', tags: ['своё', 'обводка'], dur: 16, dynamic: true,
    draw(p, t, S) {
      const box = [130, 400, 950, 1500];
      const rect = fitBox(asset.w, asset.h, box);
      const [bx, by, bw, bh] = rect;
      // тонкая рамка-«поле»
      p.rect(bx - 26, by - 26, bw + 52, bh + 52, { r: 3, w: .9, alpha: .5, role: 'accent', t0: 0, t1: .6 });
      // 1) штриховка (тени) — первой, как в карандашном рисунке
      const sh = asset.shading && asset.shading.length ? fitStrokes(asset.shading, [bx, by, bx + bw, by + bh]) : [];
      const tShade = Math.min(6.5, asset.strokes.length * .02);
      sh.forEach((s, i) => {
        p.ink(s, { smooth: 0, w: .8, role: 'fill', alpha: .75, wob: .4, p: .6, ...p.seq(i, .4, Math.max(.004, tShade / Math.max(1, sh.length)), .3) });
      });
      // 2) контуры — сверху вниз, чтобы рисунок «проявлялся» как настоящий
      const strokes = fitStrokes(asset.strokes, [bx, by, bx + bw, by + bh]);
      const order = strokes.map((s, i) => {
        const b = U.bbox(s); return { s, i, key: b[1] + (b[0] - bx) * .002 };
      }).sort((a, b) => a.key - b.key);
      const tDraw = Math.min(11, asset.strokes.length * .05);
      const step = Math.max(.006, tDraw / Math.max(1, order.length));
      order.forEach((o, i) => {
        p.ink(o.s, { smooth: .35, w: 1, wob: .45, p: .62, ...p.seq(i, 1.2 + (sh.length ? 1 : 0) * .3, step, Math.min(.7, step * 8)) });
      });
      // 3) подпись
      const note = (S.params && S.params.caption) || (asset.note && asset.note()) || '';
      if (note) p.text(note, 540, 1740, { size: 66, align: 'center', t0: 12, t1: 13.6 });
    },
  };
}

// ── Снег ───────────────────────────────────────────────────────────────────
const snow = {
  id: 'snow', name: 'Снег', tags: ['зима', 'спокойное'], dur: 14,
  draw(p, t, S) {
    const gy = 1780;
    p.cloud(240, 420, 92, { t0: .4, t1: 1.8, seed: 3, alpha: .9 });
    p.cloud(640, 340, 110, { t0: .7, t1: 2.1, seed: 7 });
    p.cloud(900, 480, 74, { t0: 1, t1: 2.4, seed: 11, alpha: .85 });
    p.sun(190, 260, 70, { t0: .3, t1: 1.4, role: 'accent', rays: 9, alpha: .7 });
    // снежинки
    const R = U.mulberry(414 + S.seed), n = Math.round(72 * S.dens);
    for (let i = 0; i < n; i++) {
      const sp = U.lerp(40, 110, R()), span = 1500;
      const x = U.lerp(60, 1020, R()) + Math.sin(t * .6 + i) * 46;
      const y = 260 + ((R() * span + t * sp) % span);
      const r = U.lerp(4, 11, R());
      if (R() < .4) p.dot(x, y, r * .7, { role: 'accent', alpha: .85 });
      else {
        p.ink([[x - r, y], [x + r, y]], { w: .8, role: 'accent', alpha: .8, raw: false });
        p.ink([[x, y - r], [x, y + r]], { w: .8, role: 'accent', alpha: .8, raw: false });
      }
    }
    // сугробы и ёлки
    p.hills(gy, { n: 6, amp: 70, t0: 2.6, t1: 4.2, seed: 5 });
    p.hills(gy + 60, { n: 8, amp: 44, t0: 3, t1: 4.6, seed: 9 });
    for (let i = 0; i < 3; i++) {
      const x = 150 + i * 128, y = gy - 10, h = 260 + i * 70;
      for (let k = 0; k < 3; k++) {
        const yy = y - h * (k * .3), ww = h * (.5 - k * .13);
        p.ink([[x - ww, yy], [x, yy - h * .42], [x + ww, yy]], { w: 1.5, t0: 4 + i * .3 + k * .12, t1: 5 + i * .3 + k * .12, smooth: .5 });
      }
      p.ink([[x, y - h], [x, y - h - 26]], { w: 1.2, t0: 5 + i * .3, t1: 5.5 + i * .3 });
    }
    p.line(-20, gy + 60, 1100, gy + 64, { w: 1.4, t0: 3.4, t1: 4.2 });
    // девочка в шапке ловит снежинки
    const sho = [600, gy - 330], head = [606, sho[1] - 70], hip = [600, gy - 180];
    const hand = [700 + Math.sin(t * 2.2) * 24, sho[1] - 130 + Math.cos(t * 2.2) * 18];
    const legL = ik(hip, [520, gy], 200, 200, 1), legR = ik(hip, [672, gy], 200, 200, 1);
    person(p, {
      hip, sho, head, headR: 52, skirt: 104, skirtLen: 150, bell: 1.15,
      kL: legL[1], fL: legL[2], kR: legR[1], fR: legR[2],
      eL: ik(sho, hand, 165, 165, 1)[1], hL: hand, eR: [sho[0] - 78, sho[1] + 110], hR: [sho[0] - 104, sho[1] + 190],
    }, { t0: 5, t1: 7, w: 1.25, fill: 'fill', wind: 1.4, feet: true, mouth: true, hairLen: .9, hairQ: 3 });
    // шарф
    p.ink(U.humps(head[0] - 46, head[0] + 46, head[1] + 52, 4, 10, 5), { w: 1.1, role: 'accent', t0: 6.8, t1: 7.6 });
    p.ink([[head[0] + 30, head[1] + 58], [head[0] + 56, head[1] + 150], [head[0] + 34, head[1] + 190]], { w: 1.1, role: 'accent', smooth: .7, t0: 7, t1: 7.8 });
    // шапка с помпоном
    const hy = head[1] - 16;
    p.ink(U.arcPts(head[0], hy, 56, 52, PI * 1.05, PI * 1.95, 20), { w: 1.5, t0: 6, t1: 6.8 });
    p.ink([[head[0] - 54, hy + 6], [head[0] + 54, hy + 6]], { w: 1.3, t0: 6.2, t1: 6.9 });
    p.circle(head[0], hy - 56, 15, { w: 1.3, t0: 6.4, t1: 7.2 });
    // пойманная снежинка в руке
    p.sparkle(hand[0], hand[1] - 26, 22, { w: 1, role: 'accent', alpha: .9 });
    p.text('снег', 540, 300, { size: 112, align: 'center', t0: 7.4, t1: 9, underline: true, halo: false, noHalo: true });
  },
};

// ── Костёр ─────────────────────────────────────────────────────────────────
const fire = {
  id: 'fire', name: 'Костёр ночью', tags: ['ночь', 'тепло'], dur: 14,
  draw(p, t, S) {
    const gy = 1700;
    skyStars(p, t, S, { n: 24, y0: 240, y1: 900, t0: .2, seed: 6 });
    p.moon(900, 300, 66, { t0: .6, t1: 1.7 });
    p.line(-20, gy, 1100, gy + 6, { w: 1.5, t0: .4, t1: 1.2 });
    p.hills(gy + 30, { n: 7, amp: 50, t0: 1, t1: 2.4, seed: 4 });
    // поленья и камни
    p.ink([[420, gy], [640, gy - 40]], { w: 3.4, t0: 1.6, t1: 2.4, smooth: .4 });
    p.ink([[420, gy - 40], [640, gy]], { w: 3.4, t0: 1.8, t1: 2.6, smooth: .4 });
    p.ink([[470, gy - 74], [600, gy - 30]], { w: 2.6, t0: 2, t1: 2.8, smooth: .4 });
    for (let i = 0; i < 7; i++) {
      const a = PI * (1.05 + i * .13), r = 190 + U.vn(i * 3.3) * 30;
      p.shape(U.catmull([[530 + Math.cos(a) * r, gy + Math.sin(a) * r * .5 + 30], [530 + Math.cos(a) * r * 1.06, gy + Math.sin(a) * r * .5 + 16], [530 + Math.cos(a) * r * .98, gy + Math.sin(a) * r * .5 + 2]], 5, false),
        { closeShape: true, fill: 'fill', stroke: 'main', w: 1, t0: 2.4 + i * .12, t1: 3.2 + i * .12, spacing: 14, scale: 1 });
    }
    // пламя: языки, открытые снизу
    const y0 = gy - 60;
    const tongue = (cx0, wdt, hgt, ph, role) => {
      const sway = Math.sin(t * 3 + ph) * 18;
      p.ink([
        [cx0 - wdt, y0],
        [cx0 - wdt * .82 + sway * .3, y0 - hgt * .34],
        [cx0 - wdt * .3 + sway, y0 - hgt * .7],
        [cx0 + sway * 1.5, y0 - hgt],
        [cx0 + wdt * .48 + sway, y0 - hgt * .58],
        [cx0 + wdt * .84 + sway * .4, y0 - hgt * .28],
        [cx0 + wdt, y0],
      ], { w: 1.8, smooth: .9, role, alpha: .95, t0: 2.8 + ph * .25, t1: 4.2 + ph * .25 });
    };
    tongue(530, 84, 320, 0, 'main');
    tongue(568, 46, 200, 1.7, 'accent');
    tongue(494, 42, 170, 3.2, 'accent');
    // искры взлетают
    const R = U.mulberry(88 + S.seed);
    for (let i = 0; i < 16; i++) {
      const life = 2.4, ph = ((t + i * .21) % life) / life;
      if (t < 3.4) continue;
      const x = 530 + Math.sin(ph * 5 + i) * 70 * ph, y = gy - 300 - ph * 460;
      p.ink([[x, y], [x + (R() - .5) * 7, y - 11]], { w: .85, role: 'accent', alpha: (1 - ph) * .85, t0: 0, t1: .01 });
      if (i % 6 === 0) p.dot(x, y, 3, { role: 'accent', alpha: 1 - ph });
    }
    // бревно-скамейка и девочка, греющая руки
    const bx = 250, by = gy - 46;
    p.ink(U.wobbleLine(bx - 150, by, bx + 150, by - 10, 6, 11, 9), { w: 3.2, t0: 3.2, t1: 4 });
    p.ink(U.wobbleLine(bx - 150, by + 26, bx + 150, by + 16, 6, 13, 9), { w: 3.2, t0: 3.3, t1: 4.1 });
    const gx = 300, gyy = gy + 20;
    p.figure(gx, gyy, 1.05, {
      footL: [gx - 60, gyy], footR: [gx + 54, gyy],
      handL: [bx + 210, by - 250], handR: [bx + 186, by - 180],
      lean: -.05, skirt: 112, skirtLen: 200, bell: 1.15, mouth: true,
    }, { t0: 4.6, t1: 6.6, w: 1.3, fill: 'fill', hairLen: 1.4, hairQ: 5 });
    // тёплое свечение
    p.ray(530, gy - 150, -PI * .82, -PI * .18, 260, 520, 4, { role: 'accent', alpha: .18, t0: 5, t1: 6.4, step: .14, w: 1.8 });
    p.ray(530, gy - 120, -PI * .95, -PI * .05, 130, 430, 10, { role: 'accent', alpha: .25, t0: 5.4, t1: 6.6, step: .06 });
    p.text('тепло', 540, 340, { size: 104, align: 'center', t0: 7, t1: 8.6, underline: true, halo: false, noHalo: true });
  },
};

// ── Дорога ─────────────────────────────────────────────────────────────────
const road = {
  id: 'road', name: 'Дорога', tags: ['движение', 'путь'], dur: 15,
  draw(p, t, S) {
    const hor = 880, gy = 1920;
    p.sun(160, 300, 80, { t0: .4, t1: 1.6, role: 'accent', rays: 11 });
    p.cloud(760, 300, 92, { t0: 1.2, t1: 2.6, seed: 3 });
    p.cloud(430, 470, 66, { t0: 1.6, t1: 3, seed: 8, alpha: .85 });
    p.line(-20, hor, 1100, hor + 4, { w: 1.4, t0: .3, t1: 1 });
    p.hills(hor - 30, { n: 6, amp: 70, t0: 1, t1: 2.4, seed: 2 });
    p.hills(hor + 10, { n: 8, amp: 44, t0: 1.4, t1: 2.8, seed: 6 });
    // далёкие поля: редкие мягкие линии
    for (let i = 0; i < 4; i++) {
      const y = hor + 30 + i * 26;
      p.ink(U.wobbleLine(40, y, 1040, y + 8, 6, i * 5, 10), { w: .75, alpha: .22, role: 'accent', t0: 1.8 + i * .12, t1: 2.8 + i * .12 });
    }
    // дорога: трапеция к горизонту
    const cx = 540, wBot = 620, wTop = 34;
    p.ink([[cx - wBot, gy], [cx - wTop, hor], [cx + wTop, hor], [cx + wBot, gy]], { w: 1.8, t0: 2, t1: 3.2 });
    // обочины
    p.ink([[cx - wBot, gy], [cx - wTop, hor]], { w: 2.4, t0: 2.2, t1: 3.2 });
    p.ink([[cx + wBot, gy], [cx + wTop, hor]], { w: 2.4, t0: 2.2, t1: 3.2 });
    // разметка бежит на зрителя
    for (let i = 0; i < 7; i++) {
      const ph = ((t * .34 + i / 7) % 1), p2 = ph * ph;
      const y = U.lerp(hor, gy, p2), w = U.lerp(wTop, wBot, p2) * .07;
      p.ink([[cx - w / 2, y], [cx + w / 2, y]], { w: 1.4, role: 'accent', alpha: .55 + .45 * ph, t0: 3, t1: 3.6 });
    }
    // столбы едут мимо
    for (let i = 0; i < 4; i++) {
      const ph = ((t * .3 + i / 4) % 1), p2 = ph * ph;
      const side = i % 2 ? 1 : -1;
      const y = U.lerp(hor + 20, 1900, p2), h = U.lerp(50, 560, p2), x = cx + side * U.lerp(46, 900, p2);
      if (ph > .04 && p2 > .06) {
        p.ink([[x, y], [x, y - h]], { w: U.lerp(1, 3.6, p2), alpha: .95, t0: 3, t1: 3.4 });
        p.ink([[x - h * .16, y - h * .82], [x + h * .16, y - h * .82]], { w: U.lerp(.8, 2.8, p2), t0: 3, t1: 3.4 });
        p.ink([[x - h * .1, y - h * .64], [x + h * .1, y - h * .64]], { w: U.lerp(.6, 2, p2), t0: 3, t1: 3.4 });
      }
    }
    // линии скорости
    for (let i = 0; i < 12; i++) {
      const a = U.hash(i * 3.3) * TAU, r = 380 + U.hash(i * 7.1) * 320;
      const x = cx + Math.cos(a) * r, y = 1500 + U.hash(i * 5.5) * 320;
      p.ink([[x, y], [x + Math.cos(a) * 110, y + Math.sin(a) * 40]], { w: .9, alpha: .45, role: 'accent', t0: 4.4 + i * .05, t1: 5.6 });
    }
    // чайки
    if (t > 4) for (let i = 0; i < 3; i++) {
      const life = 9, ph = ((t + i * 3) % life) / life;
      p.bird(U.lerp(-80, 1160, ph), 700 + i * 70 + Math.sin(ph * 6 + i) * 30, 26, { w: 1, t0: 0, t1: .01 });
    }
    p.text('поехали', 540, 380, { size: 108, align: 'center', t0: 6, t1: 7.8, underline: true, halo: false, noHalo: true });
  },
};

// ── Утро: потягивается ─────────────────────────────────────────────────────
const stretch = {
  id: 'stretch', name: 'Утро: потягивается', tags: ['утро', 'дом', 'спокойное'], dur: 14,
  draw(p, t, S) {
    const bedY = 1420;
    // окно и солнце
    p.rect(700, 260, 300, 320, { r: 8, w: 1.5, t0: .3, t1: 1.2 });
    p.line(850, 260, 850, 580, { w: 1.1 });
    p.line(700, 420, 1000, 420, { w: 1.1 });
    p.sun(900, 360, 62, { t0: .8, t1: 2, role: 'accent', rays: 10 });
    // свет полосой на пол
    p.ray(1000, 470, PI * .5, PI * .74, 300, 760, 3, { role: 'accent', alpha: .16, t0: 1.4, t1: 3, step: .16, w: 2 });
    // кровать
    p.line(-20, bedY + 240, 1100, bedY + 244, { w: 1.6, t0: .6, t1: 1.4 });
    p.rect(120, bedY + 60, 840, 180, { r: 6, w: 1.5, t0: 1, t1: 2 });
    p.cloud(300, bedY + 40, 190, { fill: 'fill', stroke: 'main', w: 1.5, t0: 1.6, t1: 3, seed: 5, spacing: 28 });
    // одеяло сдвинуто — встала
    p.shape(U.catmull([[420, bedY + 230], [500, bedY + 60], [700, bedY - 10], [860, bedY + 40], [940, bedY + 230]], 9, false),
      { closeShape: true, fill: 'fill', stroke: 'main', w: 1.6, t0: 2.2, t1: 4, spacing: 28, angle: -.12 });
    for (let i = 0; i < 4; i++) p.ink(U.humps(520 + i * 140, 660 + i * 140, bedY + 230, 3, 14, i), { w: 1, t0: 3 + i * .2, t1: 4.2 + i * .2 });
    // потягивание: руки вверх, зевок
    const sx = 300, sy = bedY + 210;
    const up = .5 + .5 * Math.sin(t * (TAU / 6) - PI / 2);
    const handL = [sx - 150 - up * 20, sy - 700 - up * 90], handR = [sx + 150 + up * 20, sy - 700 - up * 90];
    const sho = [sx, sy - 350], head = [sx + 8, sho[1] - 100], hip = [sx, sy - 170];
    const legL = ik(hip, [sx - 120, bedY + 150], 230, 230, 1), legR = ik(hip, [sx + 130, bedY + 150], 230, 230, 1);
    person(p, {
      hip, sho, head, headR: 60, skirt: 118, skirtLen: 200, bell: 1.2,
      kL: legL[1], fL: legL[2], kR: legR[1], fR: legR[2],
      eL: ik(sho, handL, 190, 190, 1)[1], hL: handL, eR: ik(sho, handR, 190, 190, -1)[1], hR: handR,
    }, { t0: 4, t1: 6, w: 1.35, fill: 'fill', wind: 1.2, feet: true, eyes: 'closed', mouth: false, hairLen: 1.05, hairQ: 3 });
    // раскрытый рот и «а-а-а»
    if (t > 5.6) {
      p.ink(U.arcPts(head[0], head[1] + 22, 20, 26, 0, TAU * .95, 16), { w: .9, t0: 5.6, t1: 6.2 });
      const ph = ((t - 5.8) % 3.6) / 3.6;
      p.text('а', head[0] + 90, head[1] - 60 - ph * 90, { size: 46 + ph * 14, role: 'accent', alpha: .9 * (1 - ph), t0: 5.8, t1: 5.9, align: 'center' });
    }
    // тапки и чашка рядом
    p.shape(U.catmull([[120, 1810], [210, 1810], [216, 1846], [126, 1846]], 5, true), { closeShape: true, fill: 'fill', stroke: 'main', w: 1.1, t0: 6.4, t1: 7.4, spacing: 12 });
    p.shape(U.catmull([[240, 1810], [330, 1810], [336, 1846], [246, 1846]], 5, true), { closeShape: true, fill: 'fill', stroke: 'main', w: 1.1, t0: 6.6, t1: 7.6, spacing: 12 });
    p.cup(840, bedY + 210, 78, { t0: 7, t1: 8, blush: true, w: 1.3 });
    p.steam(840, bedY + 120, 180, { t0: 7.6, t1: 8.4, n: 3, speed: 1.1 });
    p.text('доброе утро', 470, 820, { size: 104, align: 'center', t0: 8.4, t1: 10, underline: true });
  },
};

export const SCENES_C = [snow, fire, road, stretch];
