// image.js — свои картинки: фото в кадр и обводка рисунка в штрихи.
// Всё считается на устройстве: уменьшение, размытие, границы Собеля, скелет,
// сборка в цепочки-полилинии и штриховка по темноте. Никаких библиотек.
import { clamp, lerp, mulberry } from './util.js';

export function loadImageFromFile(file) {
  return new Promise((res, rej) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { res({ img, url }); };
    img.onerror = e => { URL.revokeObjectURL(url); rej(new Error('не удалось прочитать картинку')); };
    img.src = url;
  });
}

export function toCanvas(img, maxSide = 360) {
  const k = Math.min(1, maxSide / Math.max(img.width, img.height));
  const w = Math.max(8, Math.round(img.width * k)), h = Math.max(8, Math.round(img.height * k));
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d');
  g.imageSmoothingQuality = 'high';
  g.drawImage(img, 0, 0, w, h);
  return c;
}

// ── яркость + размытие ──────────────────────────────────────────────────────
export function grayOf(canvas, blur = 2) {
  const w = canvas.width, h = canvas.height, g = canvas.getContext('2d');
  const d = g.getImageData(0, 0, w, h).data;
  const a = new Float32Array(w * h);
  for (let i = 0, p = 0; i < d.length; i += 4, p++) a[p] = (.299 * d[i] + .587 * d[i + 1] + .114 * d[i + 2]) / 255;
  return blur > 0 ? blurF(a, w, h, blur) : a;
}
function blurF(a, w, h, rIn) {   // раздельное размытие по Гауссу (радиус — целое)
  const r = Math.max(1, Math.round(rIn));
  const k = [];
  let sum = 0;
  for (let i = -r; i <= r; i++) { const v = Math.exp(-(i * i) / (2 * r * r / 2.2)); k.push(v); sum += v; }
  for (let i = 0; i < k.length; i++) k[i] /= sum;
  const t = new Float32Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let v = 0;
    for (let i = -r; i <= r; i++) v += a[y * w + clamp(x + i, 0, w - 1)] * k[i + r];
    t[y * w + x] = v;
  }
  const out = new Float32Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let v = 0;
    for (let i = -r; i <= r; i++) v += t[clamp(y + i, 0, h - 1) * w + x] * k[i + r];
    out[y * w + x] = v;
  }
  return out;
}

// ── границы Собеля ─────────────────────────────────────────────────────────
export function sobel(gray, w, h) {
  const mag = new Float32Array(w * h), ang = new Float32Array(w * h);
  for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
    const i = y * w + x;
    const gx = -gray[i - w - 1] - 2 * gray[i - 1] - gray[i + w - 1] + gray[i - w + 1] + 2 * gray[i + 1] + gray[i + w + 1];
    const gy = -gray[i - w - 1] - 2 * gray[i - w] - gray[i - w + 1] + gray[i + w - 1] + 2 * gray[i + w] + gray[i + w + 1];
    mag[i] = Math.hypot(gx, gy);
    ang[i] = Math.atan2(gy, gx);
  }
  let mx = 0;
  for (let i = 0; i < mag.length; i++) if (mag[i] > mx) mx = mag[i];
  if (mx > 0) for (let i = 0; i < mag.length; i++) mag[i] /= mx;
  return { mag, ang };
}

// порог по Оцу: делит гистограмму градиента на «шум» и «границы»
export function otsuThr(mag) {
  const hist = new Uint32Array(256);
  let total = 0;
  for (let i = 0; i < mag.length; i++) {
    const v = Math.min(255, Math.max(0, Math.round(mag[i] * 255)));
    hist[v]++; total++;
  }
  let sum = 0;
  for (let v = 0; v < 256; v++) sum += v * hist[v];
  let sumB = 0, wB = 0, best = -1, thr = 128;
  for (let v = 0; v < 256; v++) {
    wB += hist[v]; if (wB === 0) continue;
    const wF = total - wB; if (wF === 0) break;
    sumB += v * hist[v];
    const mB = sumB / wB, mF = (sum - sumB) / wF;
    const between = wB * wF * (mB - mF) * (mB - mF);
    if (between > best) { best = between; thr = v; }
  }
  return thr / 255;
}

// порог: берём такой, чтобы осталось примерно `keep` самых сильных пикселей
export function thresholdOf(mag, keep = .1) {
  const hist = new Uint32Array(256);
  let n = 0;
  for (let i = 0; i < mag.length; i++) { const v = Math.min(255, Math.round(mag[i] * 255)); hist[v]++; if (v > 6) n++; }
  let acc = 0;
  for (let v = 255; v >= 0; v--) {
    acc += hist[v];
    if (acc >= n * keep) return v / 255;
  }
  return .18;
}

// скелет: оставляем только локальные максимумы вдоль градиента
export function thin(mag, ang, w, h, thr) {
  const e = new Uint8Array(w * h);
  for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
    const i = y * w + x;
    if (mag[i] < thr) continue;
    const a = ((ang[i] * 180 / Math.PI) + 180) % 180;
    let n1, n2;
    if (a < 22.5 || a >= 157.5) { n1 = mag[i - 1]; n2 = mag[i + 1]; }
    else if (a < 67.5) { n1 = mag[i - w + 1]; n2 = mag[i + w - 1]; }
    else if (a < 112.5) { n1 = mag[i - w]; n2 = mag[i + w]; }
    else { n1 = mag[i - w - 1]; n2 = mag[i + w + 1]; }
    if (mag[i] >= n1 && mag[i] >= n2) e[i] = 1;
  }
  return e;
}

// ── цепочки: собираем пиксели в полилинии ───────────────────────────────────
export function chain(e, w, h, o = {}) {
  const minLen = o.minLen ?? 7, maxLen = o.maxLen ?? 500;
  const seen = new Uint8Array(w * h);
  const strokes = [];
  const N8 = [[-1, -1], [0, -1], [1, -1], [1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0]];
  const neighbours = (x, y) => {
    const out = [];
    for (const [dx, dy] of N8) {
      const nx = x + dx, ny = y + dy;
      if (nx < 1 || ny < 1 || nx >= w - 1 || ny >= h - 1) continue;
      if (e[ny * w + nx] && !seen[ny * w + nx]) out.push([nx, ny, dx, dy]);
    }
    return out;
  };
  const count = (x, y) => {
    let c = 0;
    for (const [dx, dy] of N8) { const nx = x + dx, ny = y + dy; if (nx < 1 || ny < 1 || nx >= w - 1 || ny >= h - 1) continue; if (e[ny * w + nx]) c++; }
    return c;
  };
  // сначала концы линий (у них 1 сосед), потом всё остальное
  const starts = [];
  for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) { const i = y * w + x; if (e[i] && !seen[i] && count(x, y) <= 1) starts.push([x, y]); }
  for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) { const i = y * w + x; if (e[i] && !seen[i]) starts.push([x, y]); }

  for (const [sx, sy] of starts) {
    if (seen[sy * w + sx]) continue;
    const chainPts = [[sx, sy]];
    seen[sy * w + sx] = 1;
    let dir = null, guard = 0;
    let cx = sx, cy = sy;
    while (guard++ < maxLen) {
      const nb = neighbours(cx, cy);
      if (!nb.length) break;
      let pickPt;
      if (!dir) pickPt = nb[0];
      else {
        let best = -2;
        for (const q of nb) {
          const dot = q[2] * dir[0] + q[3] * dir[1];
          const pen = -0.35 * (q[2] * dir[1] - q[3] * dir[0]);   // чуть штрафуем повороты
          const sc = dot + pen;
          if (sc > best) { best = sc; pickPt = q; }
        }
      }
      seen[pickPt[1] * w + pickPt[0]] = 1;
      chainPts.push([pickPt[0], pickPt[1]]);
      dir = [pickPt[2], pickPt[3]];
      cx = pickPt[0]; cy = pickPt[1];
      if (nb.length > 2) {   // развилка: закончим здесь, соседи расцепятся дальше сами
        const more = neighbours(cx, cy);
        if (more.length > 1 && chainPts.length > minLen) break;
      }
    }
    if (chainPts.length >= minLen) strokes.push(chainPts);
  }
  return joinStrokes(strokes, o.join ?? 3.0);
}

// склеиваем обрывки: конец одной линии рядом с концом другой
export function joinStrokes(list, maxGap = 3) {
  const out = list.map(s => s.slice());
  let changed = true, guard = 0;
  while (changed && guard++ < 60) {
    changed = false;
    for (let i = 0; i < out.length && !changed; i++) {
      for (let j = i + 1; j < out.length; j++) {
        const A = out[i], B = out[j];
        const ends = [
          [A[0], B[0], 1, 1], [A[0], B[B.length - 1], 1, -1],
          [A[A.length - 1], B[0], -1, 1], [A[A.length - 1], B[B.length - 1], -1, -1],
        ];
        for (const [ea, eb, ka, kb] of ends) {
          if (Math.hypot(ea[0] - eb[0], ea[1] - eb[1]) > maxGap) continue;
          const partA = ka > 0 ? A.slice().reverse() : A.slice();
          const partB = kb < 0 ? B.slice().reverse() : B.slice();
          out[i] = partA.concat(partB);
          out.splice(j, 1);
          changed = true;
          break;
        }
        if (changed) break;
      }
    }
  }
  return out;
}

// упрощение линии (Дуглас-Пекер): оставляем только важные точки
export function simplify(pts, eps = 1.4) {
  if (pts.length < 3) return pts;
  const keep = new Uint8Array(pts.length); keep[0] = 1; keep[pts.length - 1] = 1;
  const stack = [[0, pts.length - 1]];
  while (stack.length) {
    const [a, b] = stack.pop();
    if (b - a < 2) continue;
    const [ax, ay] = pts[a], [bx, by] = pts[b];
    const dx = bx - ax, dy = by - ay, L = Math.hypot(dx, dy) || 1;
    let far = -1, fd = -1;
    for (let i = a + 1; i < b; i++) {
      const d = Math.abs((pts[i][0] - ax) * dy - (pts[i][1] - ay) * dx) / L;
      if (d > fd) { fd = d; far = i; }
    }
    if (fd > eps) { keep[far] = 1; stack.push([a, far], [far, b]); }
  }
  const out = [];
  for (let i = 0; i < pts.length; i++) if (keep[i]) out.push(pts[i]);
  return out;
}


// ── штриховые рисунки: скелет тёмных линий (без «двойных краёв») ─────────────
export function darkMask(gray, w, h, thr = .6) {
  const m = new Uint8Array(w * h);
  let dark = 0;
  for (let i = 0; i < gray.length; i++) { if (gray[i] < thr) { m[i] = 1; dark++; } }
  return { mask: m, frac: dark / (w * h) };
}

// утоньшение Зонга-Суня: от толстой линии остаётся середина в 1 пиксель
export function zhangSuen(mask, w, h, maxPass = 24) {
  const m = mask.slice();
  const at = (x, y) => (x < 0 || y < 0 || x >= w || y >= h) ? 0 : m[y * w + x];
  const P = [[0, -1], [1, -1], [1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1]];
  let pass = 0, changed = true;
  const toRemove = [];
  while (changed && pass++ < maxPass) {
    changed = false;
    for (const step of [0, 1]) {
      toRemove.length = 0;
      for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
        if (!m[y * w + x]) continue;
        const n = P.map(([dx, dy]) => at(x + dx, y + dy));
        const B = n.reduce((a, b) => a + b, 0);
        if (B < 2 || B > 6) continue;
        let A = 0;
        for (let i = 0; i < 8; i++) if (n[i] === 0 && n[(i + 1) % 8] === 1) A++;
        if (A !== 1) continue;
        const [p2, p3, p4, p5, p6, p7, p8, p9] = [n[0], n[1], n[2], n[3], n[4], n[5], n[6], n[7]];
        if (step === 0) { if (p2 * p4 * p6 || p4 * p6 * p8) continue; }
        else { if (p2 * p4 * p8 || p2 * p6 * p8) continue; }
        toRemove.push(y * w + x);
      }
      if (toRemove.length) { changed = true; for (const i of toRemove) m[i] = 0; }
    }
  }
  return m;
}

// разложить картинку в штрихи: line-art — по тёмным линиям, фото — по краям
export function traceSmart(canvas, o = {}) {
  const w = canvas.width, h = canvas.height;
  const gray = grayOf(canvas, o.blur ?? 1.2);
  const { mask, frac } = darkMask(gray, w, h, o.darkThr ?? .62);
  const mode = o.mode && o.mode !== 'auto' ? o.mode : (frac > .02 && frac < .35 ? 'lines' : 'edges');
  let chains;
  if (mode === 'lines') {
    const sk = zhangSuen(mask, w, h);
    chains = chain(sk, w, h, { minLen: o.minLen ?? 5, maxLen: o.maxLen ?? 420, join: o.join ?? 2.6 });
  } else {
    const { mag, ang } = sobel(gray, w, h);
    const thr = o.thr ?? Math.min(o.maxThr ?? .42, Math.max(.055, otsuThr(mag) * (o.keep ?? .42)));
    const e = thin(mag, ang, w, h, thr);
    chains = chain(e, w, h, { minLen: o.minLen ?? 6, maxLen: o.maxLen ?? 420, join: o.join ?? 3 });
  }
  let strokes = chains.filter(s => pathLen(s) > (o.minPath ?? 13));
  strokes.sort((a, b) => pathLen(b) - pathLen(a));
  const cap = o.maxStrokes ?? 420;
  if (strokes.length > cap) strokes = strokes.slice(0, cap);
  const norm = strokes.map(s => simplify(s, o.eps ?? 1.5).map(q => [q[0] / w, q[1] / h]));
  return { strokes: norm, source: canvas, w, h, count: norm.length, mode, darkFrac: frac };
}

// ── контуры из картинки ─────────────────────────────────────────────────────
export function traceImage(canvas, o = {}) { return traceSmart(canvas, o); }

// ── штриховка по темноте: тени как в карандашном рисунке ────────────────────
export function shadingStrokes(canvas, o = {}) {
  const w = canvas.width, h = canvas.height, g = canvas.getContext('2d');
  const d = g.getImageData(0, 0, w, h).data;
  const R = mulberry(o.seed ?? 12345);
  const block = o.block ?? 7, out = [];
  const ang = o.angle ?? -.6;
  const dx = Math.cos(ang), dy = Math.sin(ang);
  for (let by = 0; by < h; by += block) {
    for (let bx = 0; bx < w; bx += block) {
      let sum = 0, n = 0;
      for (let y = by; y < Math.min(by + block, h); y += 2) for (let x = bx; x < Math.min(bx + block, w); x += 2) {
        const i = (y * w + x) * 4;
        sum += (.299 * d[i] + .587 * d[i + 1] + .114 * d[i + 2]) / 255; n++;
      }
      const v = n ? sum / n : 1;
      const dark = 1 - v;
      if (dark < (o.min ?? .42)) continue;
      if (dark < .72 && R() > (dark - (o.min ?? .42)) * 2.6) continue;   // реже — светлее
      const len = block * (.9 + dark * 1.6) * (.7 + R() * .6);
      const cx = bx + block / 2 + dx * (dark - .5) * block * .8, cy = by + block / 2 + dy * (dark - .5) * block * .8;
      out.push([[cx / w - dx * len / 2 / w, cy / h - dy * len / 2 / h], [cx / w + dx * len / 2 / w, cy / h + dy * len / 2 / h]]);
    }
  }
  return out;
}
function pathLength(p) { let L = 0; for (let i = 1; i < p.length; i++) L += Math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]); return L; }
function pathLen(p) { return pathLength(p); }

// ── разложить нормализованные штрихи в прямоугольник страницы ───────────────
export function fitStrokes(strokes, rect) {
  const [x0, y0, x1, y1] = rect;
  const w = x1 - x0, h = y1 - y0;
  return strokes.map(s => s.map(p => [x0 + p[0] * w, y0 + p[1] * h]));
}

export function fitBox(srcW, srcH, rect) {   // вписать с сохранением пропорций
  const [x0, y0, x1, y1] = rect, w = x1 - x0, h = y1 - y0;
  const k = Math.min(w / srcW, h / srcH);
  const bw = srcW * k, bh = srcH * k;
  const cx = x0 + (w - bw) / 2, cy = y0 + (h - bh) / 2;
  return [cx, cy, bw, bh];
}
