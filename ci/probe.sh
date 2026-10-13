#!/usr/bin/env bash
set -x
node -v; python3 -V
pip install --quiet gdown 2>&1 | tail -2
gdown --version 2>&1 || true
gdown "1eZRIngYXfQn7R8Yu9-IFOlQAhKUxSkfR" -O track.mp3 || curl -sL "https://drive.google.com/uc?export=download&id=1eZRIngYXfQn7R8Yu9-IFOlQAhKUxSkfR" -o track.mp3
ls -la track.mp3; file track.mp3 | head -2
echo "--- mp3 duration via ffprobe ---"
ffprobe -v error -show_entries format=duration,bit_rate -of default=nw=1 track.mp3 || echo "no ffprobe"
