#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.." && . ci/lib.sh
OUT="$PWD/out3"; mkdir -p "$OUT"; LOG="$OUT/logs.txt"
exec >>"$LOG" 2>&1
set -x
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome
WORKSPACE="$PWD"
get_drive 1eZRIngYXfQn7R8Yu9-IFOlQAhKUxSkfR /tmp/track.mp3
get_ffmpeg /tmp/track.mp3 | tee "$OUT/track-info.txt"
get_drive 1a--SHk9H2qjD7VhupI-bzCnwOmL6CxKy /tmp/package.zip
rm -rf /tmp/pkg && mkdir -p /tmp/pkg && unzip -q -o /tmp/package.zip -d /tmp/pkg
PKG=/tmp/pkg/клипы
python3 "$WORKSPACE/ci/patch_scenes.py" "$PKG" "$WORKSPACE"
cp /tmp/track.mp3 "$PKG/трек.mp3"
(cd "$PKG/движок" && bash tools/fetch-whisper-assets.sh >/dev/null 2>&1)
(cd "$PKG" && npm init -y >/dev/null 2>&1; npm i puppeteer --no-audit --no-fund) >/dev/null 2>&1
echo "puppeteer: $(cd "$PKG" && node -e "console.log(require.resolve('puppeteer'))" 2>&1)"
python3 - "$PKG" <<'PY'
import json, sys, pathlib
pkg = pathlib.Path(sys.argv[1])
script = """стиль: цветные
бумага: клетка
палитра: тёплая
настроение: день
плотность: 1.08
вариант: 8
переход: flip

солдат 0:00-0:16
дождь 0:16-0:30
дорога 0:30-0:46
костёр 0:46-1:02
снег 1:02-1:18
письмо 1:18-1:34
город 1:34-1:48
сердце 1:48-2:02
солдат 2:02-2:18
звёзды 2:18-2:32
цветы 2:32-2:46
память 2:46-3:02
возвращение 3:02-3:18
кофе 3:18-3:32
танец 3:32-3:48
финал 3:48-4:16"""
cfg = {
  "engine": "движок",
  "track": "трек.mp3",
  "profile": "color", "paper": "grid", "palette": "warm", "mood": "day",
  "dens": 1.08, "seed": 8, "quality": "720x1280",
  "compress": "auto", "crf": 23, "preset": "veryfast",
  "whisper": False, "cover_at": 8,
  "script_text": script,
  "out": "готовые/клип.mp4",
}
(pkg / 'конфиг.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
print('config written')
PY
cat "$PKG/конфиг.json"
export INKCLIP_DIR="$PKG/движок" PUPPETEER_DIR="$PKG" FFMPEG
cd "$PKG"
echo "=== кадры-раскадровка (быстрая проверка) ==="
timeout 900 node tools/make-frame.mjs конфиг.json 2>&1 | tail -12 || echo "make-frame exit=$?"
ls -la готовые/ 2>/dev/null
echo "=== полный рендер ==="
timeout 3000 node tools/make-clip.mjs конфиг.json 2>&1 | tail -60 || echo "make-clip exit=$?"
ls -la готовые/ 2>/dev/null
cp -f готовые/клип.mp4 "$OUT/clip.mp4" 2>/dev/null
cp -f готовые/клип-обложка.png "$OUT/cover.png" 2>/dev/null
cp -f готовые/клип-раскадровка.png "$OUT/storyboard.png" 2>/dev/null
cp -f готовые/клип-отчёт.json "$OUT/report.json" 2>/dev/null
cp -f готовые/*-кадр-*.png "$OUT/" 2>/dev/null
# страховка по размеру: не больше 90 МБ (лимит загрузки на Диск — 100 МБ)
SZ=$(stat -c%s "$OUT/clip.mp4" 2>/dev/null || echo 0)
echo "размер клипа: $SZ байт"
if [ "$SZ" -gt 94371840 ]; then
  echo "слишком большой — пережимаю (crf 27)"
  "$FFMPEG" -y -loglevel error -i "$OUT/clip.mp4" -c:v libx264 -preset veryfast -crf 27 -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart "$OUT/clip-small.mp4" && mv "$OUT/clip-small.mp4" "$OUT/clip.mp4" || echo "пережать не вышло"
  stat -c%s "$OUT/clip.mp4"
fi
echo "=== итог ==="
ls -la "$OUT"
set +x
cd "$WORKSPACE"
enc_payload out3
