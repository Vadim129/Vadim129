// Подключение Capacitor внутри Android-обёртки (в браузере просто ничего не делает).
// Так app.js видит window.Capacitor и сохраняет клипы в «Документы» телефона.
if (typeof window !== 'undefined') {
  window.__INKCLIP_NATIVE__ = true;
  // Capacitor сам подставит window.Capacitor, если собрано через npx cap sync.
}
