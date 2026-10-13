#!/usr/bin/env bash
# МОСТ: скачать пакет клипов + трек с Google Drive и вернуть материалы зашифрованными.
set -uo pipefail
OUT="$PWD/out"; PAYLOAD="$PWD/payload"
mkdir -p "$OUT" "$PAYLOAD"
LOG="$OUT/logs.txt"
say(){ echo "$@" | tee -a "$LOG"; }

say "== node/npm/python =="
node -v | tee -a "$LOG"; npm -v | tee -a "$LOG"; python3 -V | tee -a "$LOG"
which google-chrome google-chrome-stable chromium ffmpeg ffprobe | tee -a "$LOG"

say "== pip gdown =="
python3 -m pip install --quiet --break-system-packages gdown 2>&1 | tail -3 | tee -a "$LOG"

say "== download package zip =="
cd /tmp
gdown "1a--SHk9H2qjD7VhupI-bzCnwOmL6CxKy" -O package.zip 2>&1 | tail -5 | tee -a "$LOG" || \
  curl -sL "https://drive.google.com/uc?export=download&id=1a--SHk9H2qjD7VhupI-bzCnwOmL6CxKy" -o package.zip
ls -la package.zip | tee -a "$LOG"

say "== download track =="
gdown "1eZRIngYXfQn7R8Yu9-IFOlQAhKUxSkfR" -O track.mp3 2>&1 | tail -5 | tee -a "$LOG" || \
  curl -sL "https://drive.google.com/uc?export=download&id=1eZRIngYXfQn7R8Yu9-IFOlQAhKUxSkfR" -o track.mp3
ls -la track.mp3 | tee -a "$LOG"
ffprobe -v error -show_entries format=duration,bit_rate -of default=nw=1 track.mp3 2>&1 | tee -a "$LOG"

say "== unzip =="
rm -rf /tmp/pkg && mkdir -p /tmp/pkg
unzip -q -o package.zip -d /tmp/pkg
find /tmp/pkg -maxdepth 3 | head -80 | tee -a "$LOG"

say "== tree with sizes (top 200) =="
cd /tmp/pkg
find . -type f -printf '%10s  %p\n' | sort -k2 | head -200 | tee -a "$LOG"
echo "--- total files:" $(find . -type f | wc -l) | tee -a "$LOG"
echo "--- dirs:" | tee -a "$LOG"; find . -maxdepth 2 -type d | tee -a "$LOG"

# --- собрать исходники движка/инструментов/доков (без тяжёлых бинарей) в out/engine-src
mkdir -p "$OUT/engine-src"
cd /tmp/pkg
# копируем всё, кроме тяжёлых каталогов и медиа
rsync -a --prune-empty-dirs \
  --exclude 'node_modules' --exclude '.git' --exclude 'models' --exclude 'vendor' \
  --exclude '*.mp4' --exclude '*.mp3' --exclude '*.zip' --exclude '*.png' --exclude '*.jpg' --exclude '*.jpeg' \
  ./ "$OUT/engine-src/" 2>&1 | tail -3 | tee -a "$LOG" || true
du -sh "$OUT/engine-src" | tee -a "$LOG"

# --- зашифровать и выложить
say "== encrypt =="
cd "$PWD" 2>/dev/null || cd "$OLDPWD"
[ -n "${GITHUB_WORKSPACE:-}" ] && cd "$GITHUB_WORKSPACE"
OUT="$PWD/out"; PAYLOAD="$PWD/payload"; mkdir -p "$PAYLOAD"
openssl rand 32 > /tmp/aes.key
openssl pkeyutl -encrypt -pubin -inkey ci/pub.pem -in /tmp/aes.key -out "$PAYLOAD/aes.key.enc"
tar -czf /tmp/payload.tar.gz -C "$(dirname "$OUT")" "$(basename "$OUT")"
openssl enc -aes-256-cbc -pbkdf2 -in /tmp/payload.tar.gz -out "$PAYLOAD/payload.enc" -pass file:/tmp/aes.key
ls -la "$PAYLOAD" | tee -a "$LOG" 2>/dev/null
