#!/usr/bin/env bash
# Шаг 3b: звуковые события, вторая половина.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=montage/analysis; mkdir -p "$OUT"
exec > >(tee -a "$OUT/log3b.txt") 2>&1
set -x
AUD=/home/runner/montage-audio.wav
[ -s "$AUD" ] || { python3 -m pip install --quiet gdown; gdown "https://drive.google.com/uc?id=14w459uIJuDZTB5A7fj2E54gS3tOPLLhJ" -O /home/runner/montage-src.mp4; ffmpeg -hide_banner -loglevel error -y -i /home/runner/montage-src.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le "$AUD"; }
python3 -m pip install --quiet numpy scipy librosa soundfile
timeout 1500 python3 montage/sfx.py "$AUD" "$OUT" 430 900 > "$OUT/sfx-b.txt" 2>&1 || echo "sfx exit=$?"
tail -3 "$OUT/sfx-b.txt"
bash montage/push.sh montage/analysis "montage: шаг3b $(date -u +%H%M%S)"
