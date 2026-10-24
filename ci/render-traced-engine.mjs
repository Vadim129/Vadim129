// Render lyric-timed picture scenes through the Drive project's InkClip engine.
// Each source illustration is loaded with the engine's built-in trace mode and
// revealed as actual pencil strokes on a blank page; this is not a slideshow.
import { spawn, spawnSync } from 'node:child_process';
import { createServer } from 'node:net';
import { readFile, writeFile, mkdir, copyFile, readdir, stat, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { resolve, join, basename } from 'node:path';
import { createRequire } from 'node:module';

const ROOT = resolve(import.meta.dirname, '..');
const PROJECT = join(ROOT, 'projects/three-zero-zero-eight');
const ENGINE = resolve(process.env.INKCLIP_DIR || join(ROOT, 'out7/engine'));
const PUPPETEER_DIR = resolve(process.env.PUPPETEER_DIR || '/tmp/whisper-align');
const TRACK = resolve(process.env.TRACK || join(PROJECT, 'song.mp3'));
const PLAN_PATH = resolve(process.env.PLAN || join(PROJECT, 'ink-engine-plan.json'));
const OUT = resolve(process.env.OUT || join(PROJECT, 'render-engine'));
const FFMPEG = process.env.FFMPEG || 'ffmpeg';
const PORT = await new Promise(r => { const s = createServer(); s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => r(p)); }); });
const plan = JSON.parse(await readFile(PLAN_PATH, 'utf8'));
const require = createRequire(join(PUPPETEER_DIR, 'noop.js'));
let puppeteer, chromium = null, chromiumModule = null;
try { puppeteer = require('puppeteer'); } catch { puppeteer = require('puppeteer-core'); }
try { chromiumModule = require('@sparticuz/chromium'); chromium = chromiumModule.default || chromiumModule; } catch {}
const log = (...a) => console.log(new Date().toTimeString().slice(0, 8), ...a);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const waitHttp = async url => {
  const start = Date.now();
  while (Date.now() - start < 30000) {
    try { const r = await fetch(url); if (r.ok) return; } catch {}
    await sleep(250);
  }
  throw new Error('InkClip server did not start');
};

if (!existsSync(join(ENGINE, 'server.mjs'))) throw new Error(`InkClip engine not found: ${ENGINE}`);
if (!existsSync(TRACK)) throw new Error(`Track not found: ${TRACK}`);
if (!plan.scenes?.length || plan.scenes.at(-1).t1 <= plan.scenes.at(-1).t0) throw new Error('Invalid timeline plan');
await mkdir(OUT, { recursive: true });
const stageDir = join(ENGINE, '.trace-upload');
await rm(stageDir, { recursive: true, force: true });
await mkdir(stageDir, { recursive: true });
const uniqueFiles = [...new Set(plan.scenes.map(s => s.file))];
for (const rel of uniqueFiles) {
  const src = resolve(PROJECT, 'art', rel);
  if (!src.startsWith(resolve(PROJECT, 'art') + '/') || !existsSync(src)) throw new Error(`Missing or unsafe artwork path: ${rel}`);
  await copyFile(src, join(stageDir, basename(rel)));
}
const trackName = `track-${Date.now()}.mp3`;
await copyFile(TRACK, join(stageDir, trackName));
const server = spawn(process.execPath, ['server.mjs', String(PORT)], { cwd: ENGINE, stdio: 'ignore' });
const url = `http://127.0.0.1:${PORT}/`;
let browser;
const report = { engine: ENGINE, plan: PLAN_PATH, track: basename(TRACK), scenes: plan.scenes, trace: [], warnings: [], errors: [] };
let exitCode = 0;
try {
  await waitHttp(url);
  if (!process.env.PUPPETEER_EXECUTABLE_PATH && chromiumModule?.inflate) {
    const libs = await chromiumModule.inflate(join(PUPPETEER_DIR, 'node_modules/@sparticuz/chromium/bin/al2023.tar.br'));
    const libPath = join(libs, 'lib');
    process.env.LD_LIBRARY_PATH = [libPath, process.env.LD_LIBRARY_PATH].filter(Boolean).join(':');
    process.env.FONTCONFIG_PATH ||= join(libs, 'fonts');
  }
  const chromePath = process.env.PUPPETEER_EXECUTABLE_PATH || (chromium ? await chromium.executablePath() : undefined);
  browser = await puppeteer.launch({
    headless: true,
    executablePath: chromePath,
    args: [...(chromium?.args || []), '--no-sandbox', '--disable-dev-shm-usage', '--autoplay-policy=no-user-gesture-required', '--disable-features=AudioServiceOutOfProcess'],
  });
  const page = await browser.newPage();
  page.setDefaultTimeout(300000);
  await page.setViewport({ width: 900, height: 1600, deviceScaleFactor: 1 });
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(String(e.message).slice(0, 240)));
  try {
    const client = await page.target().createCDPSession();
    await client.send('Page.setDownloadBehavior', { behavior: 'allow', downloadPath: OUT });
  } catch (e) { throw new Error(`Cannot configure browser download folder: ${e.message}`); }
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForFunction('window.INK && window.INK.state && window.INK.audio', { timeout: 60000 });

  // Load the original MP3 through the app's own upload control and audio analyser.
  await page.evaluate(async ({ url, name }) => {
    const blob = await (await fetch(url)).blob();
    const el = document.getElementById('mrFile');
    const dt = new DataTransfer(); dt.items.add(new File([blob], name, { type: 'audio/mpeg' }));
    el.files = dt.files; el.dispatchEvent(new Event('change'));
  }, { url: `/.trace-upload/${encodeURIComponent(trackName)}`, name: trackName });
  await page.waitForFunction('window.INK.audio.buffer && window.INK.audio.analysis', { timeout: 90000 });
  const audioDuration = await page.evaluate(() => window.INK.audio.buffer.duration);
  report.audio_duration = audioDuration;
  log('трек загружен через InkClip:', audioDuration.toFixed(3), 'с');

  // Ask InkClip's own image loader to extract contour and pencil-shading strokes.
  const assetInfo = {};
  for (const rel of uniqueFiles) {
    const file = basename(rel);
    const info = await page.evaluate(async ({ url, file }) => {
      const blob = await (await fetch(url)).blob();
      const image = new File([blob], file, { type: 'image/png' });
      window.INK.state.trMode = 'edges';
      window.INK.state.trKeep = 0.22;
      window.INK.state.shade = true;
      await window.INK.handleImage(image);
      const asset = window.INK.state.asset;
      if (!asset || !asset.strokes?.length) throw new Error(`InkClip tracing returned no strokes for ${file}`);
      // Keep the strongest 140 outlines and simplify each to at most eight points;
      // add color-sensitive pencil hatches from source pigments (never a raster overlay).
      // The engine itself deposits every mark through Pen.ink on the blank page.
      asset.strokes = asset.strokes.slice(0, 140).map(stroke => {
        if(stroke.length<=8)return stroke;
        const out=[]; for(let i=0;i<8;i++)out.push(stroke[Math.round(i*(stroke.length-1)/7)]); return out;
      });
      const engineShadeRaw=asset.shading||[];
      const imageData = asset.canvas.getContext('2d').getImageData(0,0,asset.canvas.width,asset.canvas.height).data;
      const colorHatches=[]; let seed=0;
      for(const ch of file) seed=(seed*33+ch.charCodeAt(0))>>>0;
      const rnd=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
      const w=asset.canvas.width,h=asset.canvas.height,step=7;
      for(let y=3;y<h-3;y+=step) for(let x=3;x<w-3;x+=step){
        const k=(y*w+x)*4,r=imageData[k],g=imageData[k+1],b=imageData[k+2];
        const lum=.299*r+.587*g+.114*b,chroma=Math.max(r,g,b)-Math.min(r,g,b);
        if(lum>248&&chroma<12)continue;
        const probability=Math.min(.72,Math.max(0,(248-lum)/145+chroma/360));
        if(rnd()>probability)continue;
        const angle=-.62+(rnd()-.5)*.56,length=4+rnd()*7,dx=Math.cos(angle)*length/(2*w),dy=Math.sin(angle)*length/(2*h);
        colorHatches.push([[x/w-dx,y/h-dy],[x/w+dx,y/h+dy]]);
      }
      if(colorHatches.length>220){const every=colorHatches.length/220;asset.shading=colorHatches.filter((_,i)=>Math.floor(i/every)!==Math.floor((i-1)/every));}
      else asset.shading=colorHatches;
      const engineShade=engineShadeRaw.filter((_,i)=>i%8===0).slice(0,60);
      asset.shading.push(...engineShade);
      window.__TRACE_BASES ||= {};
      window.__TRACE_ASSETS ||= {};
      window.__TRACE_BASES[file] = window.INK.byId.my_trace;
      window.__TRACE_ASSETS[file] = asset;
      return { file, width: asset.w, height: asset.h, strokes: asset.strokes.length, shading: asset.shading.length, mode: asset.mode };
    }, { url: `/.trace-upload/${encodeURIComponent(file)}`, file });
    assetInfo[file] = info;
    report.trace.push(info);
    log('InkClip trace:', file, '—', info.strokes, 'contours,', info.shading, 'shading strokes');
  }

  // Configure the linked engine's built-in trace scene per lyric-timed page.
  await page.evaluate(async ({ plan, audioDuration }) => {
    const materials = await import('/src/materials.js');
    materials.MAT.colored.pass = 1;
    materials.MAT.colored.alpha = 0.65;
    materials.MAT.colored.grain = 0.72;
    const I = window.INK, state = I.state;
    state.profile = 'color';       // InkClip's colored-pencil profile
    state.paper = 'plain';         // clean sheet, no grid or preprinted image
    state.palette = 'bright';
    state.mood = 'day';
    state.dens = 1;
    state.seed = 3008;
    state.mode = 'auto';
    state.transition = 'flip';
    state.quality = '720x1280';
    state.script = '';
    I.build();
    const palette = ['#e2402f','#f2a52b','#f4dd3b','#43a35f','#2f8fd0','#8a5bd0','#e052a0'];
    const rgb = hex => [parseInt(hex.slice(1,3),16),parseInt(hex.slice(3,5),16),parseInt(hex.slice(5,7),16)];
    const paletteRgb = palette.map(rgb);
    const closest = (r,g,b) => {
      let best=0, score=Infinity;
      for (let i=0;i<paletteRgb.length;i++) { const q=paletteRgb[i], d=(r-q[0])**2+(g-q[1])**2+(b-q[2])**2; if(d<score){score=d;best=i;} }
      return best;
    };
    for (const s of plan.scenes) {
      const file = s.file.split('/').at(-1);
      const base = window.__TRACE_BASES[file], asset = window.__TRACE_ASSETS[file];
      if (!base || !asset) throw new Error(`Trace data missing for ${file}`);
      const canvas = asset.canvas, ctx = canvas.getContext('2d'), imageData = ctx.getImageData(0,0,canvas.width,canvas.height).data;
      const rect=[130,400,950,1500], rw=rect[2]-rect[0], rh=rect[3]-rect[1];
      const scale=Math.min(rw/asset.w,rh/asset.h), bw=asset.w*scale, bh=asset.h*scale;
      const bx=rect[0]+(rw-bw)/2, by=rect[1]+(rh-bh)/2;
      const duration=Math.max(0.15,s.t1-s.t0), revealWindow=13.0;
      const custom={ id:s.id, name:s.key, tags:['lyrics','trace'], dur:duration, dynamic:true,
        draw(p, local, S) {
          const oldNow=p.now, oldInk=p.ink;
          const scaled=Math.min(revealWindow,Math.max(0,local*revealWindow/duration));
          p.now=scaled;
          p.ink=function(points, opts={}) {
            const role=opts.role||'main';
            const next={...opts};
            if (!next.color && role==='main') next.color='#3a3a44';
            else if (!next.color && (role==='fill'||role==='accent')) {
              let x=0,y=0,n=0;
              for (const q of points) { x+=q[0];y+=q[1];n++; }
              x=n?Math.round((x/n-bx)/bw*canvas.width):-1;
              y=n?Math.round((y/n-by)/bh*canvas.height):-1;
              if (x>=0&&x<canvas.width&&y>=0&&y<canvas.height) {
                const k=(y*canvas.width+x)*4, r=imageData[k],g=imageData[k+1],b=imageData[k+2];
                const chroma=Math.max(r,g,b)-Math.min(r,g,b), lum=.299*r+.587*g+.114*b;
                if(chroma>=8&&lum<250) next.c=closest(r,g,b);
                else next.color=lum<220?'#77736e':'#c7b99d';
              } else next.c=2;
            }
            return oldInk.call(this,points,next);
          };
          try { base.draw(p,scaled,S); }
          finally { p.ink=oldInk; p.now=oldNow; }
        }
      };
      I.byId[s.id]=custom;
    }
    const tl=I.tl;
    tl.duration=audioDuration;
    tl.profile='color'; tl.paper='plain'; tl.palette='bright'; tl.mood='day'; tl.dens=1;
    tl.scenesById=I.byId;
    tl.segments=plan.scenes.map((s,i)=>{
      const t1=i+1<plan.scenes.length?plan.scenes[i+1].t0:audioDuration;
      const dur=Math.max(.05,t1-s.t0);
      const even=i%2===0;
      const cam=even
        ? {a:{nx:-.012,ny:.008,z:1.005,r:-.002},b:{nx:.012,ny:-.008,z:1.035,r:.003}}
        : {a:{nx:.012,ny:-.008,z:1.035,r:.003},b:{nx:-.01,ny:.01,z:1.005,r:-.002}};
      return {id:s.id,t0:s.t0,t1,cam,params:{},seed:3008+i*37,index:i,transition:i===0?'cut':'flip',dur,local:t=>Math.max(0,Math.min(dur,t-s.t0))};
    });
    I.seek(0);
    const q=document.getElementById('selQuality'); if(q) q.value='720x1280';
  }, { plan, audioDuration });

  const sceneList=await page.evaluate(()=>window.INK.tl.segments.map(s=>({id:s.id,t0:s.t0,t1:s.t1,dur:s.dur})));
  report.scene_list=sceneList;
  report.page_errors=pageErrors;
  if (sceneList.length!==plan.scenes.length || sceneList.at(-1).t1<audioDuration-.1) throw new Error('InkClip timeline did not cover the whole song');
  log('точек входа сцен:', sceneList.length, '— заданы Whisper-таймкодами по фразам');

  // Save a review storyboard directly from the InkClip renderer, after real trace strokes begin.
  const storyboard=await page.evaluate(async times=>{
    const stage=document.getElementById('stage'), tileW=300, tileH=Math.round(tileW*stage.height/stage.width), cols=4;
    const c=document.createElement('canvas'); c.width=cols*tileW; c.height=Math.ceil(times.length/cols)*tileH;
    const g=c.getContext('2d'); g.fillStyle='#fff';g.fillRect(0,0,c.width,c.height);
    for(let i=0;i<times.length;i++){
      window.INK.seek(times[i]);
      g.drawImage(stage,(i%cols)*tileW,Math.floor(i/cols)*tileH,tileW,tileH);
    }
    return c.toDataURL('image/png');
  }, plan.storyboard_times);
  await writeFile(join(OUT,'раскадровка-engine.png'),Buffer.from(storyboard.split(',')[1],'base64'));
  await writeFile(join(OUT,'таймлайн.json'),JSON.stringify({duration:audioDuration,profile:'color',paper:'plain',palette:'bright',scenes:plan.scenes.map((s,i)=>({...s,t1:sceneList[i].t1}))},null,2));
  log('контрольная раскадровка InkClip сохранена');

  if (process.env.SKIP_RECORD==='1') {
    report.skipped_record=true;
    log('SKIP_RECORD=1 — проверка движка и тайминга завершена без записи полного клипа');
  } else {
    await rm(join(OUT,'download'),{force:true});
    const before=new Set(await readdir(OUT));
    log('запись клипа через InkClip MediaRecorder (реальное время:',audioDuration.toFixed(2),'с)');
    await page.click('#btnExport');
    const t0=Date.now(); let lastLog=0;
    for(;;){
      const info=await page.$eval('#exportInfo',e=>e.textContent).catch(()=>''), clock=await page.$eval('#clock',e=>e.textContent).catch(()=>''), elapsed=(Date.now()-t0)/1000;
      if(elapsed>audioDuration+300) throw new Error('InkClip export timed out');
      if(/готово/.test(info)){report.export_info=info;log('запись завершена:',info.slice(0,180));break;}
      if(/не получилось/.test(info)) throw new Error('InkClip export failed: '+info.slice(0,250));
      if(elapsed-lastLog>=20){log('  запись:',clock||info||`${Math.round(elapsed)}с`);lastLog=elapsed;}
      await sleep(1000);
    }
    let raw=null;
    for(let i=0;i<120&&!raw;i++){
      const list=(await readdir(OUT)).filter(f=>!before.has(f)&&(/\.(webm|mp4)$/i.test(f)||f==='download'));
      if(list.length){const p=join(OUT,list[0]),a=await stat(p);await sleep(700);const b=await stat(p);if(a.size===b.size&&b.size>1000)raw=p;}
      if(!raw)await sleep(1000);
    }
    if(!raw)throw new Error('InkClip recording download did not appear');
    report.raw=basename(raw);report.raw_bytes=(await stat(raw)).size;
    const mp4=join(PROJECT,'final-clip-v3.mp4');
    const r=spawnSync(FFMPEG,['-y','-loglevel','error','-i',raw,'-vf','tpad=stop_mode=clone:stop_duration=3','-r','30','-fps_mode','cfr','-shortest','-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',mp4],{stdio:'inherit'});
    if(r.status!==0||!existsSync(mp4))throw new Error(`ffmpeg conversion failed (status ${r.status})`);
    report.output=mp4;report.bytes=(await stat(mp4)).size;
    await rm(raw,{force:true});
    const probe=spawnSync(FFMPEG,['-i',mp4,'-f','null','-'],{encoding:'utf8'});
    report.ffmpeg_summary=(probe.stderr||'').split('\n').filter(x=>/Duration:|Video:|Audio:/.test(x)).slice(0,4);
    log('готов MP4:',mp4,(report.bytes/1048576).toFixed(1),'МБ');
  }
} catch(e) {
  exitCode=1;report.errors.push(String(e?.stack||e));console.error('\n⛔',e?.stack||e);
} finally {
  if(browser)await browser.close().catch(()=>{});
  server.kill('SIGTERM');
  await rm(stageDir,{recursive:true,force:true}).catch(()=>{});
  report.completed_at=new Date().toISOString();
  await writeFile(join(OUT,'отчёт-engine.json'),JSON.stringify(report,null,2)).catch(()=>{});
}
process.exit(exitCode);
