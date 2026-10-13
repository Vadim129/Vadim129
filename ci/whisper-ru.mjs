// whisper-ru.mjs — как tools/whisper-words.mjs, но принудительно по-русски и без «сценария по словам».
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { readFile, writeFile, mkdir, copyFile, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { resolve, dirname, join, basename } from 'node:path';
import { createRequire } from 'node:module';

const log = (...a) => console.log(new Date().toTimeString().slice(0, 8), ...a);
const MIMES = { '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4', '.aac': 'audio/aac', '.ogg': 'audio/ogg', '.flac': 'audio/flac' };
const mimeFor = (p) => MIMES[('.' + p.split('.').pop()).toLowerCase()] || 'audio/mpeg';
const engineDir = process.env.INKCLIP_DIR;
const pupDir = process.env.PUPPETEER_DIR;
const track = process.argv[2];
const outDir = resolve(process.argv[3]);
if (!engineDir || !existsSync(join(engineDir, 'server.mjs'))) { console.error('нет INKCLIP_DIR'); process.exit(1); }
const req = createRequire(join(pupDir, 'noop.js'));
const puppeteer = req('puppeteer');
const freePort = () => new Promise(r => { const s = createServer(); s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => r(p)); }); });
const waitHttp = (url, ms = 20000) => new Promise((res, rej) => { const t0 = Date.now(); (async function tick() { try { const r = await fetch(url); if (r.ok) return res(true); } catch (e) {} if (Date.now() - t0 > ms) return rej(new Error('сервер не поднялся')); setTimeout(tick, 250); })(); });
await mkdir(outDir, { recursive: true });
const port = await freePort();
const srv = spawn(process.execPath, ['server.mjs', String(port)], { cwd: engineDir, stdio: 'ignore' });
const url = `http://127.0.0.1:${port}/`;
await waitHttp(url);
const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
let code = 0;
try {
  const page = await browser.newPage();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForFunction('window.INK && window.INK.state', { timeout: 60000 });
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const upDir = join(engineDir, '.kit-upload'); await mkdir(upDir, { recursive: true });
  const name = 'загрузка-' + Date.now() + '-' + basename(track);
  await copyFile(track, join(upDir, name));
  await page.evaluate(async ({ url, name, mime }) => {
    const blob = await (await fetch(url)).blob();
    const el = document.getElementById('mrFile');
    const dt = new DataTransfer(); dt.items.add(new File([blob], name, { type: mime }));
    el.files = dt.files; el.dispatchEvent(new Event('change'));
  }, { url: '/' + ['.kit-upload', name].map(encodeURIComponent).join('/'), name, mime: mimeFor(track) });
  const t0 = Date.now();
  for (;;) {
    const t = await page.$eval('#mrInfo', e => e.textContent).catch(() => '');
    if (/BPM|не смог/.test(t)) { log('трек:', t.trim()); if (/не смог/.test(t)) throw new Error('трек не читается'); break; }
    if (Date.now() - t0 > 90000) throw new Error('анализ трека не закончился');
    await sleep(400);
  }
  // язык — русский, модель остаётся в памяти (keep) чтобы не запускать дважды
  await page.evaluate(() => {
    const s = document.getElementById('whLang'); if (s) { s.value = 'russian'; s.dispatchEvent(new Event('change')); }
    const k = document.getElementById('whKeep'); if (k) { k.checked = true; k.dispatchEvent(new Event('change')); }
  });
  log('распознаю слова (русский, офлайн)…');
  await page.click('#btnWhisper');
  const w0 = Date.now();
  for (;;) {
    const st = await page.$eval('#whStatus', e => e.textContent).catch(() => '');
    process.stdout.write('\r  ' + st.slice(0, 110) + '                ');
    if (/готово за/.test(st)) { console.log(''); log('готово:', st.trim().replace(/\s+/g, ' ')); break; }
    if (/не вышло/.test(st)) throw new Error('распознавание не вышло: ' + st);
    if (Date.now() - w0 > 900000) throw new Error('распознавание не закончилось за 15 минут');
    await sleep(1500);
  }
  const words = await page.evaluate(() => (window.INK.state.words || []).map(w => ({ w: w.w ?? w.text, t0: w.t0 ?? w.start, t1: w.t1 ?? w.end })));
  const text = await page.$eval('#whInfo', e => e.textContent).catch(() => '');
  const clean = text.replace(/^текст:\s*/, '').trim();
  await writeFile(join(outDir, 'track-расшифровка.txt'), clean + '\n');
  await writeFile(join(outDir, 'track-слова.json'), JSON.stringify({ text: clean, words }, null, 2));
  log(`слов: ${words.length}`);
  console.log('\nтекст:\n' + clean.slice(0, 1500));
} catch (e) { code = 1; console.error('\n⛔ ' + (e && e.message ? e.message : e)); }
finally { await browser.close().catch(() => {}); srv.kill('SIGTERM'); await rm(join(engineDir, '.kit-upload'), { recursive: true, force: true }).catch(() => {}); }
process.exit(code);
