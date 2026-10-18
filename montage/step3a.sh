#!/usr/bin/env bash
# Шаг 3a: звуковые события, первая половина.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=montage/analysis; mkdir -p "$OUT"
exec > >(tee -a "$OUT/log3a.txt") 2>&1
set -x
AUD=/home/runner/montage-audio.wav
[ -s "$AUD" ] || { python3 -m pip install --quiet gdown; gdown "https://drive.google.com/uc?id=14w459uIJuDZTB5A7fj2E54gS3tOPLLhJ" -O /home/runner/montage-src.mp4; ffmpeg -hide_banner -loglevel error -y -i /home/runner/montage-src.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le "$AUD"; }
python3 -m pip install --quiet numpy scipy librosa soundfile
timeout 1500 python3 montage/sfx.py "$AUD" "$OUT" 0 430 > "$OUT/sfx-a.txt" 2>&1 || echo "sfx exit=$?"
tail -3 "$OUT/sfx-a.txt"
bash montage/push.sh montage/analysis "montage: шаг3a $(date -u +%H%M%S)"
