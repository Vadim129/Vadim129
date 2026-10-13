#!/usr/bin/env bash
# Стадия «клип из кадров»: кадры из ci/frames (нейросетевые рисунки) раскладываются
# движком по таймингу песни, движок сам листает страницы и записывает клип.
# Результат: out8/{клип.mp4, обложка.png, раскадровка.png, отчёт.json} — коммитится.
set -uo pipefail
cd "$(dirname "$0")/.." && . ci/lib.sh
OUT="$PWD/out8"; mkdir -p "$OUT"
exec >>"$OUT/logs.txt" 2>&1
set -x
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome
WORKSPACE="$PWD"
TRACK_ID=1eZRIngYXfQn7R8Yu9-IFOlQAhKUxSkfR
ZIP_ID=1a--SHk9H2qjD7VhupI-bzCnwOmL6CxKy
git config user.email "ci@local"
git config user.name "ci"

push_safe() {   # повторяем push: ветка бывает занята чужим коммитом
  cd "$WORKSPACE"
  for i in 1 2 3 4 5; do
    git pull --rebase --no-edit -q || true
    if git push; then echo "push ок (попытка $i)"; return 0; fi
    echo "push не прошёл — попытка $i"; sleep 8
  done
  echo "push так и не прошёл"
  return 1
}

commit_out() {   # $1 = сообщение
  cd "$WORKSPACE"
  git add -f "$OUT" || true
  git commit -q -m "ci: $1 $(date -u +%H%M%S)" || echo "нечего коммитить"
  push_safe || true
}

get_drive "$TRACK_ID" /tmp/track.mp3
ensure_ffmpeg
"$FFMPEG" -hide_banner -i /tmp/track.mp3 2>&1 | grep -E "Duration|Stream" > "$OUT/track-info.txt" || true
cat "$OUT/track-info.txt"

get_drive "$ZIP_ID" /tmp/package.zip
rm -rf /tmp/pkg && mkdir -p /tmp/pkg && unzip -q -o /tmp/package.zip -d /tmp/pkg
PKG=/tmp/pkg/клипы
python3 "$WORKSPACE/ci/patch_scenes.py" "$PKG" "$WORKSPACE" || echo "патч движка: есть замечания (см. выше)"
(cd "$PKG" && npm init -y >/dev/null 2>&1; npm i puppeteer --no-audit --no-fund) >/dev/null 2>&1
export INKCLIP_DIR="$PKG/движок" PUPPETEER_DIR="$PKG" FFMPEG
ls -la "$WORKSPACE/ci/frames" > "$OUT/frames-list.txt"
export SKIP_RECORD="${SKIP_RECORD:-0}"   # 1 — только проверка кадров, без записи клипа

node "$WORKSPACE/ci/render-photo.mjs" /tmp/track.mp3 "$WORKSPACE/ci/frames" "$WORKSPACE/ci/frames.json" "$OUT" 2>&1 | tail -80 || echo "render-photo exit=$?"
ls -la "$OUT"
commit_out "клип-кадры-отчёт"          # логи и отчёт пушим сразу — чтобы они не потерялись

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
commit_out "клип из кадров"
