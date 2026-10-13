#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.." && . ci/lib.sh
OUT="$PWD/out2"; mkdir -p "$OUT"; LOG="$OUT/logs.txt"
exec >>"$LOG" 2>&1
set -x
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome
WORKSPACE="$PWD"
get_drive 1eZRIngYXfQn7R8Yu9-IFOlQAhKUxSkfR /tmp/track.mp3
get_drive 1a--SHk9H2qjD7VhupI-bzCnwOmL6CxKy /tmp/package.zip
rm -rf /tmp/pkg && mkdir -p /tmp/pkg && unzip -q -o /tmp/package.zip -d /tmp/pkg
PKG=/tmp/pkg/клипы
(cd "$PKG/движок" && bash tools/fetch-whisper-assets.sh >/dev/null 2>&1)
(cd "$PKG" && npm init -y >/dev/null 2>&1; npm i puppeteer --no-audit --no-fund) >/dev/null 2>&1
export INKCLIP_DIR="$PKG/движок" PUPPETEER_DIR="$PKG"
timeout 2400 node "$WORKSPACE/ci/whisper-ru.mjs" /tmp/track.mp3 "$OUT" 2>&1 | tail -60 || echo "whisper-ru exit=$?"
ls -la "$OUT"
set +x
cd "$WORKSPACE"
enc_payload out2
