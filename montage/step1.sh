#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=montage/a1; mkdir -p "$OUT"
exec > >(tee -a "$OUT/log.txt") 2>&1
set -x
. montage/common.sh
need_src
ffprobe -v error -print_format json -show_format -show_streams "$SRC" > "$OUT/info.json"
ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vf "fps=1/10,scale=320:-2,drawtext=text='%{pts\:hms}':x=5:y=5:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.55,tile=8x5" -frames:v 3 "$OUT/sheet-%02d.jpg"
ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vf "scale=960:-2" -c:v libx264 -preset veryfast -crf 30 -pix_fmt yuv420p -c:a aac -b:a 96k -movflags +faststart "$OUT/proxy.mp4"
[ -s "$OUT/scdet.txt" ] || ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vf "scdet=threshold=18,metadata=print:file=$OUT/scdet.txt" -an -f null -
timeout 600 python3 montage/shots.py "$OUT/scdet.txt" > "$OUT/shots.txt"
ls -la "$OUT"
push_dir "$OUT" "montage: разведка $(date -u +%H%M%S)"
