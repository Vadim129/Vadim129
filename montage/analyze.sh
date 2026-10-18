#!/usr/bin/env bash
# Разбор исходника: монтажные склейки, расшифровка, звуковые события, прокси для просмотра.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=montage/analysis; rm -rf "$OUT"; mkdir -p "$OUT"
exec >>"$OUT/log.txt" 2>&1
set -x
SRC=/home/runner/montage-src.mp4
if [ ! -s "$SRC" ]; then
  python3 -m pip install --quiet gdown
  gdown "https://drive.google.com/uc?id=14w459uIJuDZTB5A7fj2E54gS3tOPLLhJ" -O "$SRC" || \
  gdown --fuzzy "https://drive.google.com/file/d/14w459uIJuDZTB5A7fj2E54gS3tOPLLhJ/view" -O "$SRC"
fi

D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$SRC")
echo "duration=$D" > "$OUT/info.txt"

# прокси для просмотра (не для финала)
ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vf "scale=960:-2" -c:v libx264 -preset veryfast -crf 30 -pix_fmt yuv420p -c:a aac -b:a 96k -movflags +faststart "$OUT/proxy.mp4"
ls -la "$OUT/proxy.mp4"

# звук для анализа
ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vn -ac 2 -ar 44100 -c:a pcm_s16le /tmp/full.wav
ffmpeg -hide_banner -loglevel error -y -i /tmp/full.wav -ac 1 -ar 16000 -c:a pcm_s16le /tmp/a16.wav

# склейки
ffmpeg -hide_banner -i "$SRC" -vf "scdet=threshold=18,metadata=print:file=$OUT/scdet.txt" -an -f null - >/dev/null 2>&1
python3 montage/shots.py "$OUT/scdet.txt" > "$OUT/shots.txt" 2>>"$OUT/log.txt"

# расшифровка
python3 -m pip install --quiet faster-whisper >>"$OUT/log.txt" 2>&1
python3 montage/transcribe.py /tmp/a16.wav "$OUT" >> "$OUT/log.txt" 2>&1 || echo "transcribe failed"

# звуковые события
python3 -m pip install --quiet librosa soundfile scipy numpy >>"$OUT/log.txt" 2>&1
python3 montage/sfx.py /tmp/full.wav "$OUT" >> "$OUT/log.txt" 2>&1 || echo "sfx failed"

# спектрограммы по всему клипу
python3 montage/audio_probe.py /tmp/a16.wav "$OUT" >> "$OUT/log.txt" 2>&1 || true
rm -rf "$OUT/spectro"   # спектрограммы тяжёлые, при нужде пересоберём

ls -la "$OUT"
