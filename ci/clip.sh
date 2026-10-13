#!/usr/bin/env bash
# Стадия «клип»: полный рендер клипа по ci/scene-script.txt.
# Результат: out6/{клип.mp4, обложка.png, раскадровка.png, отчёт.json, logs.txt} — коммитится.
set -uo pipefail
cd "$(dirname "$0")/.." && . ci/lib.sh
OUT="$PWD/out6"; mkdir -p "$OUT"
exec >>"$OUT/logs.txt" 2>&1
set -x
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome
WORKSPACE="$PWD"
TRACK_ID=1eZRIngYXfQn7R8Yu9-IFOlQAhKUxSkfR
ZIP_ID=1a--SHk9H2qjD7VhupI-bzCnwOmL6CxKy

get_drive "$TRACK_ID" /tmp/track.mp3
ensure_ffmpeg
"$FFMPEG" -hide_banner -i /tmp/track.mp3 2>&1 | grep -E "Duration|Stream" | head -4 > "$OUT/track-info.txt" || true
cat "$OUT/track-info.txt"

get_drive "$ZIP_ID" /tmp/package.zip
rm -rf /tmp/pkg && mkdir -p /tmp/pkg && unzip -q -o /tmp/package.zip -d /tmp/pkg
PKG=/tmp/pkg/клипы
python3 "$WORKSPACE/ci/patch_scenes.py" "$PKG" "$WORKSPACE"
cp /tmp/track.mp3 "$PKG/трек.mp3"
(cd "$PKG" && npm init -y >/dev/null 2>&1; npm i puppeteer --no-audit --no-fund) >/dev/null 2>&1
export INKCLIP_DIR="$PKG/движок" PUPPETEER_DIR="$PKG" FFMPEG
python3 "$WORKSPACE/ci/make_config.py" "$PKG" "$WORKSPACE/ci/scene-script.txt" "$OUT"
cat "$PKG/конфиг.json"
cd "$PKG" && node tools/make-clip.mjs --проверить 2>&1 | tail -14

echo "=== полный рендер $(date -u +%H:%M:%S) ==="
timeout 5400 node tools/make-clip.mjs конфиг.json 2>&1 | tail -80 || echo "make-clip exit=$?"
ls -la готовые/ 2>/dev/null

# раскадровка: если полный рендер её не сделал — просим движок отдельно
if [ ! -f готовые/клип-раскадровка.png ]; then
  echo "=== раскадровка отдельно ==="
  timeout 1800 node tools/make-frame.mjs конфиг.json 2>&1 | tail -20 || echo "make-frame exit=$?"
fi

cp -f готовые/клип.mp4 "$OUT/клип.mp4" 2>/dev/null
cp -f готовые/клип-обложка.png "$OUT/обложка.png" 2>/dev/null
cp -f готовые/клип-раскадровка.png "$OUT/раскадровка.png" 2>/dev/null
cp -f готовые/клип-отчёт.json "$OUT/отчёт.json" 2>/dev/null
cp -f готовые/*кадр*.png "$OUT/" 2>/dev/null
cp -f готовые/клип-кадры/*.png "$OUT/" 2>/dev/null

# страховка по размеру: Диск принимает до 100 МБ
SZ=$(stat -c%s "$OUT/клип.mp4" 2>/dev/null || echo 0)
echo "размер клипа: $SZ байт"
if [ "$SZ" -gt 94371840 ]; then
  echo "слишком большой — пережимаю (crf 27)"
  "$FFMPEG" -y -loglevel error -i "$OUT/клип.mp4" -c:v libx264 -preset veryfast -crf 27 -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart "$OUT/клип-small.mp4" && mv "$OUT/клип-small.mp4" "$OUT/клип.mp4" || echo "пережать не вышло"
fi
echo "=== итог ==="
ls -la "$OUT"
set +x
cd "$WORKSPACE"
git add -f "$OUT"
git -c user.email=ci@local -c user.name=ci commit -m "ci: клип $(date -u +%H%M%S)" || echo "нечего коммитить"
git push || echo "push не прошёл"
