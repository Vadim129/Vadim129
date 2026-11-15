// native.js — сохранение файла: в браузере скачивание, в Android-приложении — в «Документы».
import { download } from './export.js';

export function isNative() {
  try { return !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform()); } catch (e) { return false; }
}

export async function saveBlob(blob, name) {
  if (!isNative()) { download(blob, name); return { where: 'скачано в загрузки', path: name }; }
  const FS = window.Capacitor.Plugins && window.Capacitor.Plugins.Filesystem;
  if (!FS) { download(blob, name); return { where: 'скачано (плагин Filesystem не подключён)', path: name }; }
  const b64 = await new Promise((res, rej) => {
    const fr = new FileReader();
    fr.onload = () => res(String(fr.result).split(',')[1]);
    fr.onerror = () => rej(new Error('не удалось прочитать blob'));
    fr.readAsDataURL(blob);
  });
  await FS.writeFile({ path: name, data: b64, directory: 'DOCUMENTS', recursive: true });
  let uri = '';
  try { const u = await FS.getUri({ path: name, directory: 'DOCUMENTS' }); uri = u.uri; } catch (e) {}
  return { where: 'сохранено в «Документы»', path: uri || name };
}
