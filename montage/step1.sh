#!/usr/bin/env bash
# Шаг 1: скачать исходник, сведения о нём, прокси для просмотра, границы склеек.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=montage/analysis; mkdir -p "$OUT"
exec > >(tee -a "$OUT/log1.txt") 2>&1
set -x
SRC=/home/runner/montage-src.mp4
AUD=/home/runner/montage-audio.wav

if [ ! -s "$SRC" ]; then
  python3 -m pip install --quiet gdown
  gdown "https://drive.google.com/uc?id=14w459uIJuDZTB5A7fj2E54gS3tOPLLhJ" -O "$SRC"
fi
ls -la "$SRC"

if [ ! -s "$AUD" ]; then
  ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vn -ac 1 -ar 16000 -c:a pcm_s16le "$AUD"
fi
ls -la "$AUD"

ffprobe -v error -print_format json -show_format -show_streams "$SRC" > "$OUT/info.json"
ffprobe -v error -show_entries format=duration,size,bit_rate -show_entries stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,bit_rate,duration -of default=noprint_wrappers=1 "$SRC" > "$OUT/info.txt" 2>&1

# прокси 960px — только для просмотра
ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vf "scale=960:-2" -c:v libx264 -preset veryfast -crf 30 -pix_fmt yuv420p -c:a aac -b:a 96k -movflags +faststart "$OUT/proxy.mp4"
ls -la "$OUT/proxy.mp4"

# контактные листы (10 с) и покадровые превью вокруг склеек — позже
ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vf "fps=1/10,scale=320:-2,drawtext=text='%{pts\:hms}':x=5:y=5:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.55,tile=8x5" -frames:v 3 "$OUT/sheet-%02d.jpg"

# склейки
ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vf "scdet=threshold=18,metadata=print:file=$OUT/scdet.txt" -an -f null -
timeout 900 python3 montage/shots.py "$OUT/scdet.txt" > "$OUT/shots.txt"

git add -f montage/analysis
git commit -q -m "montage: шаг1 $(date -u +%H%M%S)" || echo "нечего коммитить"
git push || echo "push не прошёл"
