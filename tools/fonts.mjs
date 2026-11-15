// fonts.mjs — рукописный шрифт Neucha для Node-инструментов.
// Регистрирует assets/fonts/neucha-full.ttf, чтобы текст в рендере был
// детским почерком, а не печатными буквами системного шрифта.
import { GlobalFonts } from '@napi-rs/canvas';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

let done = false;
export function registerFonts() {
  if (done) return true;
  const p = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'assets', 'fonts', 'neucha-full.ttf');
  if (!existsSync(p)) { console.log('шрифт: assets/fonts/neucha-full.ttf не найден, буквы будут системными'); return false; }
  GlobalFonts.registerFromPath(p, 'Neucha');
  done = true;
  return true;
}
