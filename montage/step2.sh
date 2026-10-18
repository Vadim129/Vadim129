#!/usr/bin/env bash
# Шаг 2: расшифровка речи с точными таймингами.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=montage/analysis; mkdir -p "$OUT"
exec > >(tee -a "$OUT/log2.txt") 2>&1
set -x
AUD=/home/runner/montage-audio.wav
python3 -m pip install --quiet -U faster-whisper "av>=13"

timeout 1500 python3 montage/transcribe.py "$AUD" "$OUT" || echo "transcribe exit=$?"
ls -la "$OUT"
git add -f montage/analysis
git commit -q -m "montage: шаг2 $(date -u +%H%M%S)" || echo "нечего коммитить"
git push || echo "push не прошёл"
