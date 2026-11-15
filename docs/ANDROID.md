# Android-приложение из этого движка

Приложение — обёртка WebView вокруг того же кода (Capacitor). Отдельный код писать не нужно:
клипы считаются на телефоне, сохраняются в «Документы».

## Готовый APK

`../apk/чернильный-клип-0.4.apk` (собран под Java 17 + Android SDK 34, подписан отладочным ключом).
Просто перекинь на телефон и установи (разреши «установка из неизвестных источников»).
Такой APK годится для себя и друзей; для Google Play нужен свой релизный ключ (`./gradlew bundleRelease`).

## Что нужно один раз поставить (для сборки своими руками)

1. **Node.js 18+** — https://nodejs.org
2. **Java 17** (JDK) и **Android SDK 34** — проще всего через
   [Android Studio](https://developer.android.com/studio), либо JDK 17 + command-line tools.
   Проверка: `java -version` должен показать 17, а в проекте лежать `android/local.properties` со строкой
   `sdk.dir=/путь/к/Android/Sdk`.

## Сборка (на компьютере, в папке проекта)

```bash
cd inkclip
npm install                       # поставит Capacitor и плагины
npm run build:www                 # соберёт папку www/ из index.html и src/
npx cap add android               # создаст папку android/ (один раз)
npm run android:sync              # скопирует www/ в проект Android
npm run android:apk               # соберёт debug-APK
```

APK появится здесь: `android/app/build/outputs/apk/debug/app-debug.apk`.
Скопировать на телефон и установить (нужно разрешить установку из неизвестных источников).

Открыть проект в Android Studio (для запуска на телефоне в один клик):

```bash
npm run android:open
```

## Что уже настроено

* `capacitor.config.json` — appId `ru.inkclip.app`, имя «Чернильный клип», webDir `www`.
* `src/native.js` — сохранение клипа через плагин Filesystem в «Документы»; в браузере — обычное скачивание.
* Плагины в `package.json`: filesystem (сохранение), share (отправить клип в другое приложение — можно вызывать
  через `Capacitor.Plugins.Share`), core, android.

## Разрешения

* Android 9 и ниже просит `WRITE_EXTERNAL_STORAGE` при сохранении — плагин сам запросит.
* Интернет приложению **не нужен вообще**: Whisper (библиотека + wasm + модель) лежит внутри
  приложения в `www/vendor` и `www/models`, поэтому слова трека считаются и в самолёте.

## Что стоит доделать в приложении

* Кнопка «поделиться» рядом с сохранением (`Capacitor.Plugins.Share.share({ files: [uri] })`).
* Экспорт по умолчанию 720×1280 (уже стоит) — на телефоне 1080×1920 записывается медленнее реального времени.
* Фоновый рендер с блокировкой экрана, если понадобится.
