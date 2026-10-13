// render-photo.mjs — собирает клип из готовых кадров (нейросетевых картинок).
// Кадры «лежат на бумаге как страницы», движок сам листает их по таймингу песни,
// запись идёт в реальном времени с треком. Никаких печатных надписей: весь текст — на картинках.
//
// Запуск: node ci/render-photo.mjs <трек.mp3> <папка-с-кадрами> <frames.json> <папка-вывода>
import { spawn, spawnSync } from 'node:child_process';
import { createServer } from 'node:net';
import { readFile, writeFile, mkdir, copyFile, readdir, stat, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { resolve, join, basename } from 'node:path';
import { createRequire } from 'node:module';

const log = (...a) => console.log(new Date().toTimeString().slice(0, 8), ...a);
const [track, framesDir, planPath, outDirArg] = process.argv.slice(2);
const outDir = resolve(outDirArg);
const engineDir = process.env.INKCLIP_DIR;
const pupDir = process.env.PUPPETEER_DIR;
const FFMPEG = process.env.FFMPEG || 'ffmpeg';
const plan = JSON.parse(await readFile(planPath, 'utf8'));

await mkdir(outDir, { recursive: true });
if (!engineDir || !existsSync(join(engineDir, 'server.mjs'))) { console.error('нет INKCLIP_DIR'); process.exit(1); }
const req = createRequire(join(pupDir, 'noop.js'));
const puppeteer = req('puppeteer');

const freePort = () => new Promise(r => { const s = createServer(); s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => r(p)); }); });
const waitHttp = (url, ms = 20000) => new Promise((res, rej) => { const t0 = Date.now(); (async function tick() { try { const r = await fetch(url); if (r.ok) return res(true); } catch (e) {} if (Date.now() - t0 > ms) return rej(new Error('сервер не поднялся')); setTimeout(tick, 250); })(); });
const sleep = ms => new Promise(r => setTimeout(r, ms));

// кадры кладём внутрь движка, чтобы страница могла их забрать обычным fetch
const framesHost = join(engineDir, '.frames');
await rm(framesHost, { recursive: true, force: true });
await mkdir(framesHost, { recursive: true });
const files = [];
const missing = [];
for (const s of plan.scenes) if (!files.some(f => f.key === s.key)) files.push({ key: s.key, file: s.file });
for (const f of files) {
  const src = join(framesDir, f.file);
  if (!existsSync(src)) { missing.push(f.file); continue; }
  await copyFile(src, join(framesHost, f.file));
}
log('кадров на диске:', files.length, missing.length ? ('нет: ' + missing.join(', ')) : '');
if (missing.length) log('⚠ этих кадров нет — их сцены останутся пустыми');

const port = await freePort();
const srv = spawn(process.execPath, ['server.mjs', String(port)], { cwd: engineDir, stdio: 'ignore' });
const url = `http://127.0.0.1:${port}/`;
await waitHttp(url);

const browser = await puppeteer.launch({
  headless: true,
  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--autoplay-policy=no-user-gesture-required',
         '--disable-features=AudioServiceOutOfProcess', '--font-render-hinting=none'],
});
const report = { plan: planPath, frames: files.map(f => f.file), missing, scenes: [], warnings: [], errors: [] };
let code = 0;
try {
  const page = await browser.newPage();
  // скачивание файла записи прямо в папку вывода (без диалогов)
  let dlOk = false;
  try {
    const client = await page.target().createCDPSession();
    await client.send('Page.setDownloadBehavior', { behavior: 'allow', downloadPath: outDir });
    dlOk = true;
  } catch (e) { log('Page.setDownloadBehavior не сработал:', String(e.message).slice(0, 80)); }
  if (!dlOk) {
    try {
      const bclient = await browser.target().createCDPSession();
      await bclient.send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: outDir, eventsEnabled: true });
      dlOk = true;
    } catch (e) { log('Browser.setDownloadBehavior не сработал:', String(e.message).slice(0, 80)); }
  }
  if (!dlOk) throw new Error('браузер не отдаёт файл: не удалось настроить папку скачивания');
  log('папка скачивания настроена');
  await page.setViewport({ width: 900, height: 1600, deviceScaleFactor: 1 });
  const pageErrors = [];
  const extRequests = [];
  page.on('pageerror', e => pageErrors.push(String(e.message).slice(0, 300)));
  page.on('request', r => {
    const u = r.url();
    if (!/^(https?:\/\/(127\.0\.0\.1|localhost):\d+\/|blob:|data:|about:)/.test(u)) extRequests.push(u.slice(0, 140));
  });
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForFunction('window.INK && window.INK.state', { timeout: 60000 });
  log('приложение открыто');

  // 1) трек — как будто его выбрали руками в приложении
  const upDir = join(engineDir, '.kit-upload'); await mkdir(upDir, { recursive: true });
  const name = 'загрузка-' + Date.now() + '-' + basename(track);
  await copyFile(track, join(upDir, name));
  await page.evaluate(async ({ url, name, mime }) => {
    const blob = await (await fetch(url)).blob();
    const el = document.getElementById('mrFile');
    const dt = new DataTransfer(); dt.items.add(new File([blob], name, { type: mime }));
    el.files = dt.files; el.dispatchEvent(new Event('change'));
  }, { url: '/' + ['.kit-upload', name].map(encodeURIComponent).join('/'), name, mime: 'audio/mpeg' });
  const t0 = Date.now();
  for (;;) {
    const t = await page.$eval('#mrInfo', e => e.textContent).catch(() => '');
    if (/BPM|не смог/.test(t)) { log('трек принят:', t.trim().slice(0, 120)); report.track_info = t.trim(); if (/не смог/.test(t)) throw new Error('трек не читается'); break; }
    if (Date.now() - t0 > 90000) throw new Error('анализ трека не закончился');
    await sleep(400);
  }

  // 2) кадры — читаем тут, отдаём в страницу готовыми байтами (никаких сетевых сюрпризов)
  const payload = [];
  for (const f of files) {
    if (missing.includes(f.file)) continue;
    const buf = await readFile(join(framesDir, f.file));
    const magic = buf.subarray(0, 4).toString('hex');
    const mime = buf[0] === 0xff && buf[1] === 0xd8 ? 'image/jpeg'
      : magic.startsWith('89504e47') ? 'image/png'
      : buf.subarray(8, 12).toString('ascii') === 'WEBP' ? 'image/webp' : 'application/octet-stream';
    payload.push({ key: f.key, file: f.file, mime, b64: buf.toString('base64'), size: buf.length });
  }
  log('кадры прочитаны:', payload.length, 'шт,', (payload.reduce((a, f) => a + f.size, 0) / 1048576).toFixed(1), 'МБ');
  const loaded = await Promise.race([
    page.evaluate(async ({ payload }) => {
      window.__FRAMES = {};
      const info = [];
      const decode = (f) => new Promise((res, rej) => {
        try {
          const bin = atob(f.b64);
          const bytes = new Uint8Array(bin.length);
          for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
          const blob = new Blob([bytes], { type: f.mime });
          const url = URL.createObjectURL(blob);
          const img = new Image();
          const to = setTimeout(() => { URL.revokeObjectURL(url); rej(new Error('не открылась за 25 с')); }, 25000);
          img.onload = () => {
            clearTimeout(to);
            try {
              const c = document.createElement('canvas');
              c.width = 1080; c.height = Math.round(img.height * 1080 / img.width);
              const g = c.getContext('2d');
              g.imageSmoothingQuality = 'high';
              g.drawImage(img, 0, 0, c.width, c.height);
              res(c);
            } catch (e) { rej(e); } finally { URL.revokeObjectURL(url); }
          };
          img.onerror = () => { clearTimeout(to); URL.revokeObjectURL(url); rej(new Error('картинка не читается')); };
          img.src = url;
        } catch (e) { rej(e); }
      });
      for (const f of payload) {
        try {
          const c = await decode(f);
          window.__FRAMES[f.key] = c;
          info.push({ file: f.file, ok: true, mime: f.mime, size: f.size, canvas: [c.width, c.height] });
        } catch (e) {
          info.push({ file: f.file, ok: false, mime: f.mime, size: f.size, error: String(e && e.message ? e.message : e).slice(0, 120) });
        }
      }
      return info;
    }, { payload }),
    new Promise((_, rej) => setTimeout(() => rej(new Error('загрузка кадров в страницу не закончилась за 4 минуты')), 240000)),
  ]);
  const good = loaded.filter(r => r.ok).length;
  log('кадры загружены в страницу:', good, 'из', payload.length);
  for (const r of loaded) log('  ', r.file, r.ok ? `✓ ${r.mime} ${(r.size / 1024) | 0}КБ → ${r.canvas}` : ('⛔ ' + r.error));
  report.frames_loaded = loaded;
  if (!good) throw new Error('ни один кадр не загрузился');

  // 3) монтаж: раскладываем страницы по таймингу песни
  const scenes = plan.scenes.map((s, i) => {
    const even = i % 2 === 0;
    const cam = even
      ? { a: { nx: -0.015, ny: 0.01, z: 1.005, r: -0.003 }, b: { nx: 0.015, ny: -0.012, z: 1.065, r: 0.004 } }
      : { a: { nx: 0.015, ny: -0.01, z: 1.06, r: 0.004 }, b: { nx: -0.012, ny: 0.012, z: 1.0, r: -0.003 } };
    return { key: s.key, t0: s.t0, t1: s.t1, seed: 11 + i * 37, cam, transition: i === 0 ? 'cut' : 'flip' };
  });
  const mounted = await page.evaluate((spec) => window.INK.mount(spec), {
    duration: plan.duration, size: plan.size, profile: plan.profile, paper: plan.paper,
    palette: plan.palette, mood: plan.mood, dens: plan.dens, scenes,
  });
  log('монтаж:', JSON.stringify(mounted));

  // 4) контрольный лист и обложка — из самих кадров движка
  const shot = async (times, cols, tileW) => page.evaluate(async ({ times, cols, tileW }) => {
    const INK = window.INK, stage = document.getElementById('stage');
    const tileH = Math.round(tileW * stage.height / stage.width);
    const rows = Math.ceil(times.length / cols);
    const c = document.createElement('canvas');
    c.width = cols * tileW; c.height = rows * tileH;
    const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    for (let i = 0; i < times.length; i++) {
      INK.seek(times[i]);
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      g.drawImage(stage, (i % cols) * tileW, Math.floor(i / cols) * tileH, tileW, tileH);
    }
    return c.toDataURL('image/png');
  }, { times, cols, tileW });

  const save = async (dataUrl, file) => writeFile(join(outDir, file), Buffer.from(String(dataUrl).split(',')[1], 'base64'));
  await save(await shot(plan.storyboard_times, 4, 356), 'раскадровка.png');
  log('раскадровка готова');
  await save(await shot([plan.cover_at], 1, 720), 'обложка.png');
  log('обложка готова');

  if (process.env.SKIP_RECORD === '1') {
    log('SKIP_RECORD=1 — запись пропущена (проверка кадров и раскадровки)');
    report.skipped_record = true;
    throw { stop: true };
  }

  // 5) запись клипа в реальном времени
  const before = new Set((await readdir(outDir)).map(f => f));
  log('начинаю запись клипа (', plan.duration, 'с — реальное время )');
  await page.click('#btnExport');
  const rec0 = Date.now();
  for (;;) {
    const info = await page.$eval('#exportInfo', e => e.textContent).catch(() => '');
    const bar = await page.$eval('#clock', e => e.textContent).catch(() => '');
    if (Date.now() - rec0 > (plan.duration + 240) * 1000) throw new Error('запись не закончилась за отведённое время');
    if (/готово/.test(info)) { log('запись закончена:', info.slice(0, 160)); report.export_info = info.slice(0, 300); break; }
    if (/не получилось/.test(info)) throw new Error('запись упала: ' + info.slice(0, 300));
    if (Math.round((Date.now() - rec0) / 20000) !== Math.round((Date.now() - rec0 - 200) / 20000)) log('  ', bar);
    await sleep(1000);
  }
  // ждём появления файла скачивания
  let file = null;
  for (let i = 0; i < 120 && !file; i++) {
    const list = (await readdir(outDir)).filter(f => !before.has(f) && /\.(webm|mp4)$/i.test(f));
    if (list.length) {
      const p = join(outDir, list[0]);
      const s1 = await stat(p); await sleep(700); const s2 = await stat(p);
      if (s1.size === s2.size && s2.size > 1000) file = p;
    }
    if (!file) await sleep(1000);
  }
  if (!file) throw new Error('файл записи не появился в папке');
  log('файл записи:', basename(file), (await stat(file)).size, 'байт');
  report.raw = basename(file);
  report.raw_bytes = (await stat(file)).size;

  // 6) перегоняем в H.264/AAC — иначе телефон может не проиграть
  const mp4 = join(outDir, 'клип.mp4');
  const args = ['-y', '-loglevel', 'error', '-i', file, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
                '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', mp4];
  const r = spawnSync(FFMPEG, args, { stdio: 'inherit' });
  if (r.status !== 0 || !existsSync(mp4)) throw new Error('ffmpeg не перевёл запись');
  const st = await stat(mp4);
  report.bytes = st.size;
  log('клип:', (st.size / 1048576).toFixed(1), 'МБ');
  // ffprobe — кодек и длительность
  const probe = spawnSync(process.env.FFPROBE || 'ffprobe', ['-v', 'error', '-show_entries', 'stream=codec_name,duration', '-of', 'json', mp4]);
  try { report.probe = JSON.parse(probe.stdout.toString()); } catch (e) {}
  if (report.raw.endsWith('.webm')) await rm(file, { force: true });

  report.page_errors = pageErrors;
  report.external_requests = extRequests;
  report.scene_list = plan.scenes.map(s => `${s.t0.toFixed(1)}–${s.t1.toFixed(1)} ${s.key}`);
  log('чистота: ошибок страницы', pageErrors.length, ', внешних запросов', extRequests.length);
} catch (e) {
  if (e && e.stop) {
    // это не ошибка — проверочный прогон без записи
  } else {
    code = 1;
    report.errors.push(String(e && e.message ? e.message : e));
    console.error('\n⛔ ' + (e && e.message ? e.message : e));
  }
} finally {
  await browser.close().catch(() => {});
  srv.kill('SIGTERM');
  await rm(framesHost, { recursive: true, force: true }).catch(() => {});
  await rm(join(engineDir, '.kit-upload'), { recursive: true, force: true }).catch(() => {});
  await writeFile(join(outDir, 'отчёт.json'), JSON.stringify(report, null, 2)).catch(() => {});
}
process.exit(code);
