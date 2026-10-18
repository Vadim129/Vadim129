#!/usr/bin/env bash
# Первичная разведка исходника: метаданные, контактные листы, аудиоанализ, расшифровка.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=montage/probe; rm -rf "$OUT"; mkdir -p "$OUT"
exec >>"$OUT/log.txt" 2>&1
set -x
SRC=/home/runner/montage-src.mp4
: "${FILE_ID:=14w459uIJuDZTB5A7fj2E54gS3tOPLLhJ}"

if [ ! -s "$SRC" ]; then
  python3 -m pip install --quiet gdown
  gdown "https://drive.google.com/uc?id=$FILE_ID" -O "$SRC" || \
  gdown --fuzzy "https://drive.google.com/file/d/$FILE_ID/view" -O "$SRC"
fi
ls -la "$SRC"

ffprobe -v error -print_format json -show_format -show_streams "$SRC" > "$OUT/info.json"
ffprobe -v error -show_entries format=duration,size,bit_rate -show_entries stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,bit_rate,duration -of default=noprint_wrappers=1 "$SRC" > "$OUT/info.txt" 2>&1

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$SRC")
echo "duration=$DUR" >> "$OUT/info.txt"

# контактные листы: кадр каждые 10 с, время в углу
ffmpeg -hide_banner -loglevel error -i "$SRC" -vf "fps=1/10,scale=360:-2,drawtext=text='%{pts\:hms}':x=6:y=6:fontsize=22:fontcolor=yellow:box=1:boxcolor=black@0.55,tile=6x5" -frames:v 4 "$OUT/sheet-%02d.jpg"
# крупные кадры: каждые 30 с
ffmpeg -hide_banner -loglevel error -i "$SRC" -vf "fps=1/30,scale=900:-2,drawtext=text='%{pts\:hms}':x=10:y=10:fontsize=30:fontcolor=yellow:box=1:boxcolor=black@0.55" -q:v 3 "$OUT/frame-%03d.jpg"

# аудио
ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vn -ac 1 -ar 16000 -c:a pcm_s16le /tmp/a.wav
ls -la /tmp/a.wav

python3 -m pip install --quiet numpy scipy pillow
python3 montage/audio_probe.py /tmp/a.wav "$OUT" >> "$OUT/log.txt" 2>&1 || echo "audio_probe failed"

# расшифровка (faster-whisper, CPU)
python3 -m pip install --quiet faster-whisper >> "$OUT/log.txt" 2>&1
python3 montage/transcribe.py "$SRC" "$OUT" >> "$OUT/log.txt" 2>&1 || echo "transcribe failed"

ls -la "$OUT"
