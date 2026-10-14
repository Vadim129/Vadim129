// server.mjs — локальный сервер для разработки: node server.mjs [port]
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { resolve, extname, relative } from 'node:path';

const ROOT = import.meta.dirname;
const PORT = Number(process.argv[2] || 8000);
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.json': 'application/json', '.css': 'text/css', '.png': 'image/png', '.jpg': 'image/jpeg', '.mp4': 'video/mp4', '.webm': 'video/webm', '.wasm': 'application/wasm', '.onnx': 'application/octet-stream', '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4', '.txt': 'text/plain; charset=utf-8', '.svg': 'image/svg+xml' };

createServer(async (req, res) => {
  try {
    let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    if (p === '/' || p === '') p = '/index.html';
    const f = resolve(ROOT, '.' + p);
    if (relative(ROOT, f).startsWith('..')) return res.writeHead(403).end('no');
    const st = await stat(f).catch(() => null);
    if (!st || st.isDirectory()) return res.writeHead(404).end('404');
    const type = TYPES[extname(f)] || 'application/octet-stream';
    // CORS: нужно, чтобы приложение работало внутри встроенных предпросмотров (у них «пустой» origin)
    res.setHeader('access-control-allow-origin', '*');
    res.setHeader('access-control-expose-headers', 'content-length, content-range, accept-ranges');
    const range = req.headers.range;
    if (range) {                       // докачка по частям (модели по 30 МБ, аудио)
      const m = /bytes=(\d*)-(\d*)/.exec(range);
      const start = m && m[1] ? Number(m[1]) : 0;
      const end = m && m[2] ? Number(m[2]) : st.size - 1;
      const body = (await readFile(f)).subarray(start, end + 1);
      return res.writeHead(206, {
        'content-type': type, 'content-length': body.length, 'cache-control': 'no-store',
        'accept-ranges': 'bytes', 'content-range': `bytes ${start}-${end}/${st.size}`,
      }).end(body);
    }
    const body = await readFile(f);
    res.writeHead(200, { 'content-type': type, 'content-length': body.length, 'cache-control': 'no-store', 'accept-ranges': 'bytes' }).end(body);
  } catch (e) { res.writeHead(500).end(String(e.message)); }
}).listen(PORT, '0.0.0.0', () => console.log(`http://0.0.0.0:${PORT}/`));
