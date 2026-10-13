#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.." && . ci/lib.sh
OUT="$PWD/out2"; mkdir -p "$OUT"; LOG="$OUT/logs.txt"
exec >>"$LOG" 2>&1
set -x
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome
echo "=== скачиваю трек ==="
get_drive 1eZRIngYXfQn7R8Yu9-IFOlQAhKUxSkfR /tmp/track.mp3
get_ffmpeg /tmp/track.mp3
echo "=== скачиваю пакет клипов ==="
get_drive 1a--SHk9H2qjD7VhupI-bzCnwOmL6CxKy /tmp/package.zip
rm -rf /tmp/pkg && mkdir -p /tmp/pkg && unzip -q -o /tmp/package.zip -d /tmp/pkg
PKG=/tmp/pkg/клипы
echo "=== whisper assets ==="
(cd "$PKG/движок" && bash tools/fetch-whisper-assets.sh) 2>&1 | tail -25
du -sh "$PKG/движок/vendor" "$PKG/движок/models" 2>/dev/null
ls -la "$PKG/движок/models/whisper-tiny/onnx" 2>/dev/null
echo "=== puppeteer ==="
(
  cd "$PKG" || exit 9
  npm init -y >/dev/null 2>&1; echo "npm init exit=$?"
  npm i puppeteer --no-audit --no-fund 2>&1 | tail -12; echo "npm i exit=${PIPESTATUS[0]}"
  ls node_modules | head -5
  node -e "console.log('resolve:', require.resolve('puppeteer'))"
) 2>&1 | tail -30
echo "=== распознавание (whisper) ==="
export INKCLIP_DIR="$PKG/движок"
export FFMPEG
export PUPPETEER_DIR="$PKG"
(cd "$PKG" && timeout 2400 node tools/whisper-words.mjs /tmp/track.mp3 "$OUT") 2>&1 | tail -80
echo "=== результат ==="
ls -la "$OUT"
for f in "$OUT"/*.txt "$OUT"/*.json; do echo "----- $f"; head -c 6000 "$f"; echo; done
set +x
cd "${GITHUB_WORKSPACE:-$PWD}"
tail -c 8000 "$LOG" > "$OUT/../tail.txt" 2>/dev/null
enc_payload out2
