// build-www.mjs — собрать папку www/ для Android-обёртки (и для любого статического хостинга).
import { cp, mkdir, rm, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';

const ROOT = import.meta.dirname, OUT = `${ROOT}/www`;
await rm(OUT, { recursive: true, force: true });
await mkdir(OUT, { recursive: true });
await cp(`${ROOT}/index.html`, `${OUT}/index.html`);
await cp(`${ROOT}/src`, `${OUT}/src`, { recursive: true });
await cp(`${ROOT}/capacitor-native.js`, `${OUT}/capacitor-native.js`);
for (const f of ['manifest.json', 'sw.js', 'icon-192.png', 'icon-512.png', 'icon-192-maskable.png', 'icon-512-maskable.png']) {
  if (existsSync(`${ROOT}/${f}`)) await cp(`${ROOT}/${f}`, `${OUT}/${f}`);
}
if (existsSync(`${ROOT}/samples`)) await cp(`${ROOT}/samples`, `${OUT}/samples`, { recursive: true });
// рукописный шрифт клипа (иначе в APK буквы станут печатными)
if (existsSync(`${ROOT}/assets/fonts`)) await cp(`${ROOT}/assets/fonts`, `${OUT}/assets/fonts`, { recursive: true });
// Whisper целиком внутри приложения: библиотека + wasm + модель (работает офлайн)
if (existsSync(`${ROOT}/vendor`)) await cp(`${ROOT}/vendor`, `${OUT}/vendor`, { recursive: true });
if (existsSync(`${ROOT}/models`)) await cp(`${ROOT}/models`, `${OUT}/models`, { recursive: true });
const files = await readdir(OUT, { recursive: true });
console.log(`www/ готово: файлов ${files.length}`);
