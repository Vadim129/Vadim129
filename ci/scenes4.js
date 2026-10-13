// scenes4.js — «военные» сцены для клипа «Честь моя» (цветные карандаши).
// Тот же язык, что у остальных сцен: p.ink / p.shape / p.figure, время t0..t1 «от руки».
import * as U from './util.js';
import { skyStars, dust, person } from './common.js';

const TAU = U.TAU, PI = U.PI;

// ── 1. Солдат ───────────────────────────────────────────────────────────────
const soldier = {
  id: 'soldier', name: 'Солдат', tags: ['военный', 'честь', 'герой'], dur: 15,
  draw(p, t, S) {
    const R = U.mulberry(301 + S.seed);
    // небо
    p.sun(178, 336, 84, { c: 2, t0: .1, t1: .9, rays: 9, seed: 3 });
    p.cloud(824, 300, 108, { w: 1.2, c: 4, t0: .5, t1: 1.5, alpha: .9, seed: 2 });
    p.cloud(690, 430, 74, { w: 1.1, c: 4, t0: .8, t1: 1.8, alpha: .8, seed: 5 });
    for (let i = 0; i < 3; i++) p.bird(700 + i * 48, 268 + i * 28, 24, { ...p.seq(i, 1.3, .25, .6), w: .9, c: 4 });
    // дальние холмы и поле
    p.hills(1150, { amp: 74, n: 5, w: 1.4, c: 3, t0: 1.4, t1: 2.4, seed: S.seed });
    p.hills(1262, { amp: 50, n: 6, w: 1.2, c: 3, alpha: .85, t0: 1.7, t1: 2.7, seed: S.seed + 3 });
    p.shade(120, 1300, 840, 120, { angle: -.18, spacing: 24, alpha: .3, c: 3, t0: 2.4, t1: 3.4 });
    p.grass(1330, { n: 22, h0: 20, h1: 54, w: .9, c: 3, t0: 2.2, t1: 3.4, seed: S.seed });
    // солдат
    const feetY = 1640, s = 2.6, cxs = 528, f = 300 * s;
    const lean = .02;
    const shoX = cxs + lean * f * .33, shoY = feetY - f * .84, neckY = feetY - f * .88, headR = f * .083;
    const hx = shoX, hy = neckY - headR * 1.15;
    const shR = [shoX + f * .082, shoY + f * .012];
    const L1 = f * .15, L2 = f * .145;
    const restEl = [shR[0] + Math.sin(.42) * L1, shR[1] + Math.cos(.42) * L1];
    const restHand = [restEl[0] + Math.sin(.95) * L2, restEl[1] + Math.cos(.95) * L2];
    const sal = U.ss(6.0, 7.0, t);                    // отдание чести
    const salHand = [hx + headR * 1.02, hy - headR * .18];
    const hand = U.L2(restHand, salHand, sal);
    const pose = { dress: false, lean, lL: [-.1, .08], lR: [.11, .1], aL: [-.58, .38], handR: hand, bendR: -1, headDX: 0 };
    const J = p.figure(cxs, feetY, s, pose, { face: true, fill: 'fill', c: 6, w: 1.35, t0: 2.5 });
    const [hipX, hipY] = J.hip ? [J.hip[0], J.hip[1]] : [cxs, feetY - f * .5];
    // шинель (пола) поверх бёдер
    p.shape([[hipX - f * .062, hipY - 6], [hipX + f * .062, hipY - 6], [hipX + f * .085, hipY + f * .19], [hipX - f * .085, hipY + f * .19]],
      { closeShape: true, fill: 'fill', stroke: 'main', c: 6, w: 1.3, spacing: 16, angle: .5, t0: 3.3, t1: 4.3 });
    // сапоги
    for (const ft of J.feet) p.ellipse(ft[0] + 12, ft[1] + 6, 50, 21, { c: 6, fill: 'fill', spacing: 14, w: 1.1, t0: 3.6, t1: 4.2, over: .2 });
    // портупея, пуговицы
    p.ink([[shoX - f * .055, shoY + f * .02], [hipX + f * .05, hipY - f * .028]], { w: 2.2, c: 6, t0: 3.6, t1: 4.2 });
    for (let i = 0; i < 3; i++) p.dot(hipX + f * .006, shoY + f * .07 + i * f * .048, 6.5, { c: 2, t0: 4.0 + i * .12, t1: 4.4 + i * .12 });
    // ремень и пряжка
    p.ink([[hipX - f * .07, hipY - f * .022], [hipX + f * .07, hipY - f * .022]], { w: 2.1, c: 6, t0: 3.5, t1: 4.1 });
    p.rect(hipX - f * .022, hipY - f * .04, f * .044, f * .036, { r: 3, w: 1.2, c: 1, t0: 3.8, t1: 4.3 });
    // погоны
    for (const sg of [-1, 1]) p.ink([[shoX + sg * f * .05, shoY + 1], [shoX + sg * f * .088, shoY + 7]], { w: 2.6, c: 0, t0: 3.9, t1: 4.4 });
    // медаль и колодка
    p.ink([[shoX + f * .048, shoY + f * .045], [shoX + f * .038, shoY + f * .105]], { w: 4.2, c: 0, t0: 4.1, t1: 4.6 });
    p.star(shoX + f * .042, shoY + f * .125, f * .026, { c: 1, fill: 'fill', w: .9, deep: .4, t0: 4.4, t1: 4.9 });
    // каска
    p.shape(U.catmull([[hx - headR * 1.1, hy - headR * .52], [hx - headR * 1.06, hy - headR * .98], [hx - headR * .44, hy - headR * 1.36], [hx + headR * .44, hy - headR * 1.36], [hx + headR * 1.06, hy - headR * .98], [hx + headR * 1.1, hy - headR * .52]], 7, false),
      { closeShape: true, fill: 'fill', stroke: 'main', c: 5, w: 1.5, spacing: 13, angle: .7, t0: 3.9, t1: 4.9 });
    p.ink([[hx - headR * 1.12, hy - headR * .5], [hx + headR * 1.12, hy - headR * .5]], { w: 1.9, c: 5, t0: 4.5, t1: 5.0 });
    p.star(hx, hy - headR * .92, headR * .16, { c: 0, fill: 'fill', w: .9, deep: .42, t0: 4.9, t1: 5.5 });
    // тень под ногами
    p.shade(hipX - f * .2, feetY + 26, f * .4, 46, { angle: -.08, spacing: 15, alpha: .32, c: 6, t0: 5.2, t1: 6.2 });
    // складки шинели
    for (let i = 0; i < 3; i++) p.ink([[hipX - f * .07 + i * f * .06, hipY + f * .04], [hipX - f * .085 + i * f * .062, hipY + f * .18]], { w: 1, c: 6, alpha: .75, ...p.seq(i, 5.4, .18, .5) });
    // трава на переднем плане покачивается
    for (let i = 0; i < 9; i++) {
      const x = 150 + i * 100, h = 40 + R() * 24, x0 = x + Math.sin(t * .9 + i) * 6;
      p.ink([[x, 1720], [x0, 1720 - h * .6], [x0 + Math.sin(t * .9 + i) * 12, 1720 - h]], { w: .9, c: 3, ...p.seq(i, 5.2, .05, .4) });
    }
    p.text('на передовой', 540, 1852, { size: 76, align: 'center', c: 0, t0: 7.2, t1: 8.6, underline: true });
  },
};

// ── 2. Письмо домой ────────────────────────────────────────────────────────
const letter = {
  id: 'letter', name: 'Письмо домой', tags: ['военный', 'письмо', 'дом'], dur: 14,
  draw(p, t, S) {
    const R = U.mulberry(407 + S.seed);
    // свеча слева с тёплым пятном
    p.dot(250, 1262, 104, { c: 2, alpha: .18, t0: .3, t1: 1.2 });
    p.dot(250, 1262, 58, { c: 2, alpha: .22, t0: .5, t1: 1.4 });
    // свеча на столе
    p.rect(226, 1318, 52, 182, { r: 3, w: 1.5, c: 1, t0: .6, t1: 1.8 });
    p.ink([[252, 1318], [252, 1290]], { w: 1.6, c: 6, t0: 1.6, t1: 2.0 });
    const fl = Math.sin(t * 6.2) * 5;
    p.shape(U.catmull([[252, 1292], [234 + fl, 1266], [244 + fl * .5, 1238], [256, 1222], [268 - fl, 1264], [262, 1288], [252, 1292]], 7, false),
      { closeShape: true, fill: 'fill', stroke: 'main', c: 0, w: 1.3, spacing: 9, angle: .8, t0: 1.8, t1: 2.6 });
    p.dot(252, 1258, 9, { c: 2, t0: 2.2, t1: 2.7 });
    p.ink([[238, 1330], [240, 1360]], { w: 1, c: 1, alpha: .8, t0: 2.2, t1: 2.8 });
    p.ink([[264, 1336], [266, 1372]], { w: 1, c: 1, alpha: .8, t0: 2.4, t1: 3.0 });
    // фронтовой треугольник
    const A = [268, 690], B = [824, 690], C = [546, 1232];
    p.shape([A, B, C], { closeShape: true, fill: 'fill', stroke: 'main', c: 2, w: 1.7, spacing: 20, angle: .34, alpha: .9, t0: 1.0, t1: 2.6 });
    // сгибы письма
    p.ink([[A[0], A[1]], [546, 908]], { w: 1.2, c: 6, t0: 2.2, t1: 3.0 });
    p.ink([[B[0], B[1]], [546, 908]], { w: 1.2, c: 6, t0: 2.4, t1: 3.2 });
    p.ink([[546, 908], [546, 1232]], { w: 1.1, c: 6, alpha: .8, t0: 2.6, t1: 3.3 });
    // строки «от руки»
    for (let i = 0; i < 4; i++) {
      const y = 1000 + i * 50, x0 = 372 + (i % 2) * 14, x1 = 700 - (i % 3) * 16;
      p.ink(U.catmull(U.wobbleLine(x0, y - 1, x1, y + 1, 2.2, (S.seed + i * 7) % 13, 14), 4), { w: 1.25, c: 4, ...p.seq(i, 3.4, .28, .8), alpha: .92 });
    }
    // подпись витиеватая
    p.ink([[568, 1178], [632, 1164], [676, 1186], [610, 1184], [556, 1180]], { w: 1.2, c: 4, smooth: .9, t0: 5.0, t1: 6.0 });
    // марка со звездой
    p.rect(668, 728, 94, 112, { r: 4, w: 1.4, c: 0, t0: 4.2, t1: 5.0 });
    p.star(715, 784, 30, { c: 0, fill: 'fill', w: 1, deep: .42, t0: 4.8, t1: 5.6 });
    // штемпель
    p.circle(590, 830, 54, { w: 1.1, c: 4, alpha: .8, a0: -2.2, over: .55, t0: 5.2, t1: 6.0 });
    p.ink([[548, 828], [632, 822]], { w: .9, c: 4, alpha: .75, ...p.seq(0, 5.6, 0, .5) });
    // сердце и лёгкая тень под письмом
    p.heart(540, 1352, 34, { c: 0, fill: 'fill', t0: 6.2, t1: 7.0 });
    p.ink([[104, 1502], [976, 1490]], { w: 2.2, c: 6, smooth: .2, t0: 6.4, t1: 7.2 });
    
    p.shade(150, 1512, 780, 70, { angle: -.06, spacing: 24, alpha: .22, c: 6, t0: 6.9, t1: 8.0 });
    // искры над свечой
    for (let i = 0; i < 5; i++) p.sparkle(250 + (R() - .5) * 96, 1200 + (R() - .5) * 130, 9 + R() * 8, { c: 1, alpha: .8, ...p.seq(i, 1.6, .3, .5) });
    p.text('письмо домой', 540, 1852, { size: 76, align: 'center', c: 0, t0: 7.4, t1: 8.8, underline: true });
  },
};

// ── 3. Возвращение домой ───────────────────────────────────────────────────
const home = {
  id: 'home', name: 'Возвращение домой', tags: ['военный', 'дом', 'встреча'], dur: 15,
  draw(p, t, S) {
    const R = U.mulberry(613 + S.seed);
    // вечернее небо
    skyStars(p, t, S, { n: 26, t0: .2, t1: 1.6 });
    p.moon(838, 318, 72, { c: 2, t0: .5, t1: 1.4 });
    p.hills(1024, { amp: 60, n: 5, w: 1.3, c: 3, t0: 1.2, t1: 2.2, seed: S.seed });
    // дом
    p.shape([[300, 1050], [300, 1400], [640, 1400], [640, 1050]], { closeShape: true, fill: 'fill', stroke: 'main', c: 6, w: 1.6, spacing: 20, angle: .25, t0: 2.0, t1: 3.4 });
    p.shape([[274, 1058], [470, 896], [666, 1058]], { closeShape: true, fill: 'fill', stroke: 'main', c: 0, w: 1.7, spacing: 18, angle: .6, t0: 2.6, t1: 3.9 });
    // труба и дым
    p.rect(588, 920, 40, 86, { r: 2, w: 1.2, c: 6, t0: 3.1, t1: 3.7 });
    p.steam(608, 908, 180, { n: 2, t0: 4.0, t1: 5.0, speed: 1.2, alpha: .45, c: 4 });
    // окна: одно светится
    p.rect(338, 1096, 96, 98, { r: 3, w: 1.4, fill: 'fill', c: 2, spacing: 14, t0: 3.4, t1: 4.4 });
    p.ink([[386, 1096], [386, 1194]], { w: 1, c: 6, t0: 4.0, t1: 4.5 });
    p.ink([[338, 1144], [434, 1144]], { w: 1, c: 6, t0: 4.1, t1: 4.6 });
    p.rect(504, 1096, 96, 98, { r: 3, w: 1.4, c: 6, t0: 3.8, t1: 4.4 });
    p.ink([[552, 1096], [552, 1194]], { w: 1, c: 6, t0: 4.2, t1: 4.7 });
    p.ink([[504, 1144], [600, 1144]], { w: 1, c: 6, t0: 4.3, t1: 4.8 });
    // дверь
    p.rect(438, 1224, 88, 176, { r: 4, w: 1.4, c: 6, t0: 4.0, t1: 4.7 });
    p.dot(512, 1316, 5, { c: 1, t0: 4.6, t1: 5.0 });
    p.ink([[424, 1402], [546, 1400]], { w: 1.4, c: 6, t0: 4.4, t1: 5.0 });
    // забор
    p.ink([[236, 1498], [704, 1486]], { w: 1.3, c: 6, alpha: .9, t0: 4.4, t1: 5.2, smooth: .3 });
    p.ink([[236, 1572], [704, 1560]], { w: 1.3, c: 6, alpha: .9, t0: 4.6, t1: 5.4, smooth: .3 });
    for (let i = 0; i < 9; i++) {
      const x = 262 + i * 54, yTop = 1470 + Math.sin(i) * 6;
      p.ink([[x, yTop], [x + 4, 1612]], { w: 1.2, c: 6, ...p.seq(i, 4.8, .07, .5) });
    }
    // дерево
    p.ink([[902, 1444], [890, 1200], [916, 1042]], { w: 2.4, c: 6, smooth: .5, t0: 2.8, t1: 3.6 });
    p.ink([[892, 1200], [828, 1092]], { w: 1.5, c: 6, t0: 3.2, t1: 3.8 });
    p.ink([[896, 1132], [952, 1052]], { w: 1.4, c: 6, t0: 3.4, t1: 4.0 });
    p.cloud(900, 992, 108, { c: 3, w: 1.2, alpha: .95, t0: 3.6, t1: 4.8, seed: S.seed });
    // тропинка от дома к нижнему краю
    p.ink([[468, 1404], [424, 1560], [338, 1700], [282, 1832]], { w: 1.5, c: 6, smooth: .8, t0: 4.6, t1: 5.6, alpha: .85 });
    p.ink([[552, 1404], [556, 1560], [508, 1700], [438, 1834]], { w: 1.5, c: 6, smooth: .8, t0: 4.8, t1: 5.8, alpha: .85 });
    // солдат идёт домой
    const ph = (t * .55) % 1;
    const k = U.clamp((t - 4.4) / 8.4);                       // 0 → у нижнего края, 1 → у крыльца
    const feetY = U.lerp(1844, 1626, k), cxs = U.lerp(300, 470, k) + Math.sin(t * 2.1) * 4;
    const walk = p.walkPose(ph, { dress: false });
    const sc = U.lerp(.95, .72, k);
    const J = p.figure(cxs, feetY, sc, walk, { face: false, fill: 'fill', c: 6, w: 1.15, t0: 4.4 });
    const headR = 300 * sc * .083, hx = J.head[0], hy = J.head[1];
    p.shape(U.catmull([[hx - headR * 1.3, hy + headR * .16], [hx - headR * 1.2, hy - headR * .6], [hx, hy - headR * 1.16], [hx + headR * 1.2, hy - headR * .6], [hx + headR * 1.3, hy + headR * .16]], 6, false),
      { closeShape: true, fill: 'fill', stroke: 'main', c: 3, w: 1.2, spacing: 12, angle: .7, t0: 4.6, t1: 5.4 });
    // вещмешок за плечом
    p.ellipse(J.sho[0] - 300 * sc * .16, J.sho[1] + 300 * sc * .12, 68 * sc, 50 * sc, { c: 6, fill: 'fill', spacing: 11, w: 1, t0: 5.0, t1: 5.8, over: .25 });
    // свет в окне тёплым пятном на земле
    p.shade(316, 1408, 150, 64, { angle: -.1, spacing: 16, alpha: .3, c: 2, t0: 5.6, t1: 6.6 });
    // птицы в небе
    for (let i = 0; i < 2; i++) p.bird(300 + i * 40, 470 + i * 30, 22, { ...p.seq(i, 5.4, .3, .6), w: .9, c: 4 });
    p.text('возвращение домой', 540, 1852, { size: 72, align: 'center', c: 0, t0: 7.6, t1: 9.2, underline: true });
  },
};

// ── 4. Вечный огонь ────────────────────────────────────────────────────────
const flame = {
  id: 'flame', name: 'Вечный огонь', tags: ['военный', 'память', 'честь'], dur: 14,
  draw(p, t, S) {
    const R = U.mulberry(733 + S.seed);
    // лучи памяти
    p.ray(540, 1020, -PI * .97, -PI * .03, 250, 486, 11, { c: 2, t0: .2, t1: 2.0, w: .9, alpha: .75 });
    // звезда
    p.star(540, 1020, 216, { c: 0, fill: 'fill', w: 2, deep: .46, t0: 1.0, t1: 2.8 });
    p.circle(540, 1020, 88, { c: 1, fill: 'fill', w: 1.3, spacing: 12, t0: 2.4, t1: 3.4 });
    // вечный огонь
    const fl = Math.sin(t * 7.4) * 16, f2 = Math.sin(t * 5.1 + 1.2) * 12;
    p.shape(U.catmull([[540, 1010], [498 + fl, 902], [520 + fl * .6, 812], [548, 728 + f2 * .4], [582 - fl, 826], [568, 908], [540, 1010]], 8, false),
      { closeShape: true, fill: 'fill', stroke: 'main', c: 1, w: 1.6, spacing: 14, angle: .9, t0: 3.0, t1: 4.4 });
    p.shape(U.catmull([[540, 986], [518 + fl * .5, 912], [540, 848 + f2 * .5], [562 - fl * .5, 916]], 7, false),
      { closeShape: true, fill: 'fill', stroke: 'accent', c: 2, w: 1.2, spacing: 10, angle: -.6, t0: 3.6, t1: 4.8 });
    // искры
    for (let i = 0; i < 7; i++) p.sparkle(540 + (R() - .5) * 200, 760 - R() * 240, 8 + R() * 9, { c: 1, alpha: .85, ...p.seq(i, 4.2, .22, .5) });
    // каска у подножия и гвоздики
    const hl = [316, 1520];
    p.shape(U.catmull([[hl[0] - 84, hl[1] + 10], [hl[0] - 78, hl[1] - 42], [hl[0] - 20, hl[1] - 80], [hl[0] + 46, hl[1] - 76], [hl[0] + 84, hl[1] - 26], [hl[0] + 80, hl[1] + 12]], 7, false),
      { closeShape: true, fill: 'fill', stroke: 'main', c: 3, w: 1.5, spacing: 14, angle: .5, t0: 4.6, t1: 5.8 });
    p.ink([[hl[0] - 88, hl[1] + 14], [hl[0] + 84, hl[1] + 16]], { w: 1.6, c: 3, t0: 5.4, t1: 5.9 });
    for (let i = 0; i < 3; i++) {
      const bx = 700 + i * 82, by = 1498 + (i % 2) * 16;
      p.ink([[bx, by + 60], [bx + (i - 1) * 12, by - 6]], { w: 1.4, c: 3, ...p.seq(i, 5.2, .2, .6) });
      p.shape(U.catmull([[bx - 26, by - 22], [bx - 20, by - 62], [bx, by - 46], [bx + 20, by - 62], [bx + 26, by - 22], [bx + 8, by - 4], [bx - 8, by - 4]], 6, true),
        { closeShape: true, fill: 'fill', stroke: 'main', c: 0, w: 1.2, spacing: 9, t0: 5.4 + i * .2, t1: 6.2 + i * .2 });
      p.leaf(bx + 30, by + 6, 46, PI * .38, { c: 3, w: 1, t0: 5.8 + i * .2, t1: 6.4 + i * .2 });
    }
    // постамент
    p.ink([[256, 1568], [330, 1560], [420, 1566], [560, 1556], [680, 1562], [826, 1556]], { w: 1.4, c: 6, smooth: .5, alpha: .85, t0: 5.6, t1: 6.6 });
    p.shade(240, 1620, 640, 84, { angle: -.1, spacing: 22, alpha: .28, c: 6, t0: 6.2, t1: 7.4 });
    p.text('помним', 540, 1852, { size: 76, align: 'center', c: 0, t0: 7.0, t1: 8.4, underline: true });
  },
};

export const SCENES_D = [soldier, letter, home, flame];
