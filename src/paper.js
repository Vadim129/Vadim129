// paper.js — бумага. Тайл с волокнами и зерном + линовка/клетка/поле, нарисованные в мировых координатах.
import { TAU, clamp, lerp, hash, mulberry, R01, vn } from './util.js';

export const PAGE = { w: 1080, h: 1920, x0: 104, x1: 976, yTop: 196, yBot: 1790, rule: 72 };

export const PAPERS = {
  notebook: { id: 'notebook', name: 'Тетрадь в линейку', base: '#f4eddd', rule: 1, line: 'rgba(96,142,196,.40)', margin: 'rgba(210,92,106,.42)', ink: '#1d38a6' },
  plain:    { id: 'plain',    name: 'Чистый лист',       base: '#f6f0e1', rule: 0, ink: '#2a2a33' },
  grid:     { id: 'grid',     name: 'Клетка',            base: '#f6f2e6', rule: 2, line: 'rgba(112,146,186,.26)', margin: 'rgba(210,92,106,.30)', ink: '#1d38a6' },
  kraft:    { id: 'kraft',    name: 'Крафт',             base: '#c9a97c', rule: 0, ink: '#3a2a18' },
  dark:     { id: 'dark',     name: 'Тёмный лист',       base: '#1a2130', rule: 0, light: 1, ink: '#f6f3ea' },
};

export function paperTile(style, seed = 11) {   // 1024×1024: основа, зерно, волокна (линовка — отдельно, в мировых координатах)
  const w = 1024, h = 1024, c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d'), R = mulberry(seed);
  g.fillStyle = style.base; g.fillRect(0, 0, w, h);
  const id = g.getImageData(0, 0, w, h), d = id.data;
  const dark = !!style.light;
  for (let i = 0; i < d.length; i += 4) {
    const v = (R() - .5) * (dark ? 20 : 15);
    d[i] += v; d[i + 1] += v; d[i + 2] += v * .92;
  }
  g.putImageData(id, 0, 0);
  for (let k = 0; k < w * h / 240; k++) {
    const x = R() * w, y = R() * h, a = R() * TAU, l = 4 + R() * 17, dk = R() < .5;
    g.strokeStyle = dark
      ? (dk ? `rgba(0,0,0,${.05 + R() * .07})` : `rgba(190,205,225,${.05 + R() * .07})`)
      : (dk ? `rgba(112,96,72,${.03 + R() * .05})` : `rgba(255,255,250,${.14 + R() * .22})`);
    g.lineWidth = .5 + R() * .9;
    for (const [dx, dy] of [[0, 0], [-w, 0], [0, -h], [-w, -h]]) {
      g.beginPath(); g.moveTo(x + dx, y + dy);
      g.quadraticCurveTo(x + dx + Math.cos(a + .6) * l * .5, y + dy + Math.sin(a + .6) * l * .5, x + dx + Math.cos(a) * l, y + dy + Math.sin(a) * l);
      g.stroke();
    }
  }
  return c;
}

// бумага на весь холст (мир = координаты страницы, вызывать под трансформом камеры)
export function drawPaper(ctx, style, tile, o = {}) {
  const z = o.zoom || 1;
  const x0 = o.x0 ?? -2000 / z, y0 = o.y0 ?? -2000 / z, x1 = o.x1 ?? PAGE.w + 2000 / z, y1 = o.y1 ?? PAGE.h + 2000 / z;
  const pat = ctx.createPattern(tile, 'repeat'); try { pat.setTransform(new DOMMatrix([1, 0, 0, 1, 0, 0])); } catch (e) {}
  ctx.fillStyle = pat; ctx.fillRect(x0, y0, x1 - x0, y1 - y0);

  if (style.rule === 1) {
    ctx.lineCap = 'butt';
    for (let y = PAGE.yTop; y < PAGE.yBot + 40; y += PAGE.rule) {
      ctx.strokeStyle = style.line; ctx.lineWidth = 1.6 / Math.max(1, Math.sqrt(z) * .9);
      ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y + .6); ctx.stroke();
    }
    ctx.strokeStyle = style.margin; ctx.lineWidth = 2.2;
    ctx.beginPath(); ctx.moveTo(PAGE.x0, y0); ctx.lineTo(PAGE.x0, y1); ctx.stroke();
    ctx.lineWidth = 1.3; ctx.globalAlpha = .6;
    ctx.beginPath(); ctx.moveTo(PAGE.x0 + 8, y0); ctx.lineTo(PAGE.x0 + 8, y1); ctx.stroke();
    ctx.globalAlpha = 1;
    // отверстия от дырокола
    for (let i = 0; i < 3; i++) {
      const y = PAGE.h * (.25 + .25 * i);
      const gr = ctx.createRadialGradient(PAGE.x0 * .45, y, 2, PAGE.x0 * .45, y, 22);
      gr.addColorStop(0, 'rgba(60,48,32,.30)'); gr.addColorStop(1, 'rgba(60,48,32,0)');
      ctx.fillStyle = gr; ctx.beginPath(); ctx.arc(PAGE.x0 * .45, y, 22, 0, TAU); ctx.fill();
      ctx.fillStyle = style.base; ctx.beginPath(); ctx.arc(PAGE.x0 * .45, y, 9, 0, TAU); ctx.fill();
    }
  } else if (style.rule === 2) {
    ctx.lineCap = 'butt';
    for (let x = PAGE.x0; x < PAGE.x1 + 40; x += PAGE.rule) { ctx.strokeStyle = style.line; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x, y1); ctx.stroke(); }
    for (let y = PAGE.yTop; y < PAGE.yBot + 40; y += PAGE.rule) { ctx.strokeStyle = style.line; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke(); }
    ctx.strokeStyle = style.margin; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(PAGE.x0, y0); ctx.lineTo(PAGE.x0, y1); ctx.stroke();
  }
}

// мягкая тень по краям листа и лёгкая неравномерность освещения — «снято на телефон»
export function pageVignette(ctx, camMat, W, H, light = 0) {
  const g = ctx;
  g.save(); g.setTransform(1, 0, 0, 1, 0, 0);
  const gr = g.createRadialGradient(W * .5, H * .42, Math.min(W, H) * .32, W * .5, H * .5, Math.max(W, H) * .78);
  gr.addColorStop(0, 'rgba(0,0,0,0)');
  gr.addColorStop(1, light ? 'rgba(0,0,0,.42)' : 'rgba(70,50,25,.30)');
  g.fillStyle = gr; g.fillRect(0, 0, W, H);
  g.restore();
}
