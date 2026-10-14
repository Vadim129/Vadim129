// asset.mjs — свои картинки для Node-инструментов: грузит файлы с диска,
// строит ассет (как в браузере после загрузки) и регистрирует сцены
// my_photo (полароид) и my_trace (обводка).
import { loadImage } from '@napi-rs/canvas';
import { toCanvas, traceImage, shadingStrokes } from '../src/image.js';
import { makePhotoScene, makeTraceScene } from '../src/scenes3.js';

export async function loadAsset(path) {
  const img = await loadImage(path);
  const c = toCanvas(img, 420);
  const trace = traceImage(c, { keep: .32, mode: 'auto', minPath: 12, maxStrokes: 420, blur: 1.4 });
  const shading = shadingStrokes(c, {});
  console.log(`картинка: ${path} → штрихов ${trace.strokes.length}, режим ${trace.mode}`);
  return { canvas: c, w: trace.w, h: trace.h, strokes: trace.strokes, shading, name: path };
}

// paths[0] → полароид, paths[1] (или та же) → обводка
export async function registerAssetScenes(byId, paths) {
  if (!paths.length) return;
  const a0 = await loadAsset(paths[0]);
  byId.my_photo = makePhotoScene(a0);
  byId.my_trace = makeTraceScene(paths[1] ? await loadAsset(paths[1]) : a0);
}

// повторяющийся флаг: --img a.png --img b.png
export function collectImgs(argv) {
  const out = [];
  for (let i = 2; i < argv.length; i++) if (argv[i] === '--img' && argv[i + 1]) out.push(argv[++i]);
  return out;
}
