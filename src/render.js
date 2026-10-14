// render.js — сборка кадра: бумага + штрихи + камера + переворот страницы.
import * as U from './util.js';
import { Paint, grainCanvas, PROFILES, PALETTES } from './materials.js';
import { PAPERS, PAGE, paperTile, drawPaper, pageVignette } from './paper.js';
import { Pen } from './api.js';
import { MOODS } from './common.js';
import { segmentAt } from './timeline.js';

const TRANS = .58;   // длительность переворота страницы, сек

export function camMatrix(cam, W, H) {
  const s = (W / 1080) * cam.z;
  const co = Math.cos(cam.r) * s, si = Math.sin(cam.r) * s;
  return [co, si, -si, co, W / 2 - (co * cam.x - si * cam.y), H / 2 - (si * cam.x + co * cam.y)];
}

export class Renderer {
  constructor(canvas, opts = {}) {
    this.canvas = canvas;
    this.W = canvas.width; this.H = canvas.height;
    this.grain = grainCanvas(256, 77);
    this.tile = null; this.tileKey = '';
    this.paint = new Paint(this.W, this.H, this.grain);
    this.page = document.createElement('canvas'); this.page.width = this.W; this.page.height = this.H;
    this.pageCtx = this.page.getContext('2d');
    this.prevPage = document.createElement('canvas'); this.prevPage.width = this.W; this.prevPage.height = this.H;
    this.prevCtx = this.prevPage.getContext('2d');
    this.pen = new Pen(this.paint, opts);
    this.setStyle(opts);
    this.fpsAvg = 0;
  }
  setStyle(o = {}) {
    if (o.profile) this.pen.setProfile(o.profile, o.palette);
    if (o.paper && o.paper !== this.tileKey) { this.tileKey = o.paper; this.tile = paperTile(PAPERS[o.paper] || PAPERS.notebook, 11); }
    if (o.mood) this.pen.mood = o.mood;
  }
  camAt(seg, local, analysis) {
    const p = U.clamp(local / Math.max(.2, seg.dur));
    const k = U.easeIO(p);
    const drift = Math.sin(local * .35) * .06;
    const z0 = U.lerp(seg.cam.a.z, seg.cam.b.z, k) + drift * .01;
    const nx = U.clamp(U.lerp(seg.cam.a.nx, seg.cam.b.nx, k) + drift * .1, -1, 1);
    const ny = U.clamp(U.lerp(seg.cam.a.ny, seg.cam.b.ny, k) + drift * .08, -1, 1);
    const r = U.lerp(seg.cam.a.r, seg.cam.b.r, k) + Math.sin(local * .27) * .004;
    const e = analysis && analysis.energyAt ? analysis.energyAt(seg.t0 + local) : .5;
    const pulse = analysis && analysis.pulse ? analysis.pulse(seg.t0 + local) : 0;
    const shake = e > .55 ? pulse * .01 * (e - .55) * 3 : 0;
    const z = z0 + shake;
    return { z, r: r + shake * .4, x: 540 + nx * (z - 1) * 540 + shake * 90, y: 960 + ny * (z - 1) * 960 };
  }
  sceneCtxs(cm) {
    const keys = this.pen.profile.layers;
    for (const k of keys) {
      const g = this.paint.layer(k);
      g.setTransform(...cm); g.lineCap = 'round'; g.lineJoin = 'round'; g.globalAlpha = 1; g.globalCompositeOperation = 'source-over';
      g.strokeStyle = g.fillStyle = this.pen.profile.mono ? (this.pen.profile.main.color) : '#333';
    }
  }
  // нарисовать одну «страницу» в this.page
  renderPage(seg, local, analysis, tl) {
    const cm = camMatrix(this.camAt(seg, local, analysis), this.W, this.H);
    const style = PAPERS[tl.paper] || PAPERS.notebook;
    this.paint.clear();
    this.sceneCtxs(cm);
    const p = this.pen;
    p.rasters.length = 0;      // картинки не переезжают из кадра в кадр
    p.paper = tl.paper;
    p.now = local;
    p.seed = (seg.seed || 1) % 100000;
    p.hashSeed = U.hash(seg.seed || 1) * 10;
    const scene = tl.scenesById[seg.id];
    const S = {
      seed: seg.seed, R: U.mulberry(seg.seed || 1), mood: tl.mood, dens: tl.dens,
      bpm: analysis.bpm, params: seg.params || {},
      beatDur: () => analysis.beatLen, beat: t => analysis.beat(seg.t0 + t), pulse: t => analysis.pulse(seg.t0 + t),
      energy: t => analysis.energyAt(seg.t0 + t),
    };
    if (scene) scene.draw(p, local, S);
    const g = this.pageCtx;
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, this.W, this.H);
    g.setTransform(...cm);
    drawPaper(g, style, this.tile, {});
    const rast = this.pen.rasters;
    if (rast.length) {
      for (const r of rast) {
        g.save();
        g.translate(r.x + r.w / 2, r.y + r.h / 2);
        g.rotate(r.rot);
        g.globalAlpha = r.alpha;
        try { g.drawImage(r.canvas, -r.w / 2, -r.h / 2, r.w, r.h); } catch (e) {}
        g.restore();
      }
    }
    g.setTransform(1, 0, 0, 1, 0, 0);
    if (rast.length) {   // зерно бумаги ложится и на картинку
      const pat = g.createPattern(this.tile, 'repeat');
      if (pat) { g.globalCompositeOperation = 'multiply'; g.globalAlpha = .17; g.fillStyle = pat; g.fillRect(0, 0, this.W, this.H); g.globalAlpha = 1; g.globalCompositeOperation = 'source-over'; }
    }
    this.paint.compose(g, cm, this.pen.profile.layers, style.light ? 'screen' : 'multiply');
  }
  frame(T, tl) {
    const seg = segmentAt(tl, T);
    if (!seg) return;
    const local = seg.local(T);
    const prev = tl.segments[seg.index - 1];
    const inTrans = prev && seg.transition === 'flip' && local < TRANS;
    const cm = camMatrix(this.camAt(seg, local, tl.analysis), this.W, this.H);
    if (inTrans && !this.cached) {   // один раз отрисовать уходящую страницу
      this.renderPage(prev, prev.dur, tl.analysis, tl);
      this.prevCtx.setTransform(1, 0, 0, 1, 0, 0);
      this.prevCtx.clearRect(0, 0, this.W, this.H);
      this.prevCtx.drawImage(this.page, 0, 0);
      this.cached = { index: prev.index };
    }
    if (!inTrans && this.cached && (!prev || this.cached.index !== prev.index)) this.cached = null;
    this.renderPage(seg, local, tl.analysis, tl);
    const c = this.canvas.getContext('2d');
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.clearRect(0, 0, this.W, this.H);
    if (inTrans) {
      // входящая страница снизу
      c.drawImage(this.page, 0, 0);
      // уходящая листается влево, вокруг корешка
      const k = U.easeIO(local / TRANS), a = -k * 1.42, sx = Math.max(.02, Math.cos(k * Math.PI * .5));
      c.save();
      c.translate(-this.W * .04, this.H * .5);
      c.rotate(a * .32);
      c.scale(sx, 1);
      c.translate(this.W * .04, -this.H * .5);
      c.globalAlpha = 1 - k * .15;
      c.shadowColor = 'rgba(40,26,10,.45)'; c.shadowBlur = 60 * (1 - k * .5); c.shadowOffsetX = 30;
      c.drawImage(this.prevPage, 0, 0);
      c.restore();
      // блик по сгибу
      c.save();
      const gr = c.createLinearGradient(0, 0, this.W * .5, 0);
      gr.addColorStop(0, `rgba(255,250,235,0)`); gr.addColorStop(1, `rgba(90,60,20,${.18 * (1 - k)})`);
      c.fillStyle = gr; c.fillRect(0, 0, this.W, this.H);
      c.restore();
    } else {
      c.drawImage(this.page, 0, 0);
    }
    pageVignette(c, cm, this.W, this.H, (PAPERS[tl.paper] || PAPERS.notebook).light);
    return seg;
  }
}
