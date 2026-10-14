// sw.js — офлайн-кэш приложения (без модели Whisper: её браузер кэширует сам).
const CACHE = 'inkclip-v0.3.1';
const LOCAL = [
  './', './index.html', './manifest.json',
  './src/app.js', './src/api.js', './src/audio.js', './src/common.js', './src/export.js', './src/image.js',
  './src/materials.js', './src/native.js', './src/paper.js', './src/render.js', './src/scenes1.js',
  './src/scenes2.js', './src/scenes3.js', './src/script.js', './src/timeline.js', './src/util.js', './src/whisper.js',
  './icon-192.png', './icon-512.png',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(LOCAL).catch(() => {})).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  // чужие домены (модель Whisper, transformers.js) — только сеть, кэш браузера и так работает
  if (url.origin !== location.origin) return;
  // модель и движок ONNX не кладём в кэш сервис-воркера: они и так лежат в приложении,
  // а 67 МБ кэша на телефоне — лишняя память и повод для вылетов
  if (/\/(models|vendor)\//.test(url.pathname)) return;
  e.respondWith(
    caches.match(e.request).then(hit => hit || fetch(e.request).then(res => {
      const copy = res.clone();
      caches.open(CACHE).then(c => c.put(e.request, copy)).catch(() => {});
      return res;
    }).catch(() => caches.match('./index.html')))
  );
});
