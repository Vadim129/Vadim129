#!/usr/bin/env bash
# Шаг 3: звуковые события и оценка «эффектности» каждого звука.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=montage/analysis; mkdir -p "$OUT"
exec > >(tee -a "$OUT/log3.txt") 2>&1
set -x
AUD=/home/runner/montage-audio.wav
if [ ! -s "$AUD" ]; then
  ffmpeg -hide_banner -loglevel error -y -i /home/runner/montage-src.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le "$AUD"
fi
python3 -m pip install --quiet numpy scipy librosa soundfile
timeout 1500 python3 montage/sfx.py "$AUD" "$OUT" || echo "sfx exit=$?"
git add -f montage/analysis
git commit -q -m "montage: шаг3 $(date -u +%H%M%S)" || echo "нечего коммитить"
git push || echo "push не прошёл"
