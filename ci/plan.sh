#!/usr/bin/env bash
# Стадия «план»: приносит трек и пакет с Диска, патчит военные сцены,
# рисует раскадровку (9 кадров) и распознаёт слова трека (офлайн Whisper).
# Всё складывает в out5/ и коммитит — это транспорт обратно в песочницу.
set -uo pipefail
cd "$(dirname "$0")/.." && . ci/lib.sh
OUT="$PWD/out5"; mkdir -p "$OUT"
exec >>"$OUT/logs.txt" 2>&1
set -x
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome
WORKSPACE="$PWD"
TRACK_ID=1eZRIngYXfQn7R8Yu9-IFOlQAhKUxSkfR
ZIP_ID=1a--SHk9H2qjD7VhupI-bzCnwOmL6CxKy

get_drive "$TRACK_ID" /tmp/track.mp3
get_ffmpeg /tmp/track.mp3 | tee "$OUT/track-info.txt"
get_drive "$ZIP_ID" /tmp/package.zip
rm -rf /tmp/pkg && mkdir -p /tmp/pkg && unzip -q -o /tmp/package.zip -d /tmp/pkg
PKG=/tmp/pkg/клипы
ls -la "$PKG" > "$OUT/package-list.txt"
python3 "$WORKSPACE/ci/patch_scenes.py" "$PKG" "$WORKSPACE"
cp /tmp/track.mp3 "$PKG/трек.mp3"
(cd "$PKG" && npm init -y >/dev/null 2>&1; npm i puppeteer --no-audit --no-fund) >/dev/null 2>&1
echo "puppeteer: $(cd "$PKG" && node -e "console.log(require.resolve('puppeteer'))" 2>&1)"
export INKCLIP_DIR="$PKG/движок" PUPPETEER_DIR="$PKG" FFMPEG
python3 "$WORKSPACE/ci/make_config.py" "$PKG" "$WORKSPACE/ci/scene-script.txt" "$OUT"
cat "$PKG/конфиг.json"

echo "=== проверка окружения ==="
cd "$PKG" && node tools/make-clip.mjs --проверить 2>&1 | tail -14

echo "=== раскадровка (быстрая проверка) ==="
timeout 1800 node tools/make-frame.mjs конфиг.json 2>&1 | tail -30 || echo "make-frame exit=$?"
ls -la готовые/ 2>/dev/null
cp -f готовые/*раскадровка*.png "$OUT/storyboard.png" 2>/dev/null
cp -f готовые/*отчёт*.json "$OUT/report-story.png" 2>/dev/null
cp -f готовые/*кадр*.png "$OUT/" 2>/dev/null

echo "=== слова трека (Whisper, русский, офлайн) ==="
timeout 2400 node "$WORKSPACE/ci/whisper-ru.mjs" /tmp/track.mp3 "$OUT" 2>&1 | tail -40 || echo "whisper exit=$?"
ls -la "$OUT"
set +x
cd "$WORKSPACE"
git add -f "$OUT"
git -c user.email=ci@local -c user.name=ci commit -m "ci: план $(date -u +%H%M%S)" || echo "нечего коммитить"
git push || echo "push не прошёл"
