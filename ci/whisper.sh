set -uo pipefail
cd "$(dirname "$0")/.." && . ci/lib.sh
OUT="$PWD/out2"; mkdir -p "$OUT"; LOG="$OUT/logs.txt"
say(){ echo "$@" | tee -a "$LOG"; }
{
echo "=== node/npm/chrome ==="; node -v; npm -v; ls -la /usr/bin/google-chrome* 2>/dev/null
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome
say "=== скачиваю трек ==="
get_drive 1eZRIngYXfQn7R8Yu9-IFOlQAhKUxSkfR /tmp/track.mp3
get_ffmpeg /tmp/track.mp3
say "=== скачиваю пакет клипов ==="
get_drive 1a--SHk9H2qjD7VhupI-bzCnwOmL6CxKy /tmp/package.zip
rm -rf /tmp/pkg && mkdir -p /tmp/pkg && unzip -q -o /tmp/package.zip -d /tmp/pkg
PKG=/tmp/pkg/клипы
say "=== whisper assets ==="
cd "$PKG/движок" && bash tools/fetch-whisper-assets.sh 2>&1 | tail -20
ls -la models/whisper-tiny/onnx 2>/dev/null | head; du -sh vendor models 2>/dev/null
say "=== puppeteer ==="
cd "$PKG" && npm init -y >/dev/null 2>&1 && npm i puppeteer --no-audit --no-fund 2>&1 | tail -3
say "=== запускаю распознавание ==="
cd "$PKG" && timeout 1800 node tools/whisper-words.mjs /tmp/track.mp3 "$OUT" 2>&1 | tail -40
say "=== результаты ==="
ls -la "$OUT" | tee -a "$LOG"
for f in "$OUT"/*.txt; do echo "----- $f"; head -c 4000 "$f"; echo; done | tee -a "$LOG"
} 2>&1 | tee -a "$LOG"
cd "$(dirname "$0")/.." 2>/dev/null || cd "$GITHUB_WORKSPACE"
cp -r "$OUT" /tmp/out2keep 2>/dev/null
enc_payload out2
