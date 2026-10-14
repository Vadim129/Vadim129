# Шрифт клипа — Neucha (детский рукописный)

`neucha-full.ttf` — шрифт **Neucha** (автор Jovanny Lemonad, лицензия SIL Open Font
License 1.1), латиница + кириллица в одном файле. Собран из subsets пакета
`@fontsource/neucha` (`fonttools merge`), чтобы движок нигде не откатывался
на печатные буквы.

Использование:
- браузер/приложение: `@font-face` в `index.html`, в APK попадает через `build-www.mjs`;
- Node-рендер: `tools/fonts.mjs` регистрирует файл через `GlobalFonts`.

Весь текст в клипе рисуется этим шрифтом (`Pen.font` в `src/api.js`).
