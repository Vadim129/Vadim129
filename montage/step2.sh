#!/usr/bin/env bash
# Транскрипция речи.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=montage/a2; mkdir -p "$OUT"
exec > >(tee -a "$OUT/log.txt") 2>&1
set -x
. montage/common.sh
need_src
python3 -m pip install --quiet -U faster-whisper "av>=13" numpy
python3 -c "import faster_whisper, av; print('fw ok', av.__version__)"
timeout 1200 python3 montage/transcribe.py "$AUD" "$OUT"
ls -la "$OUT"
push_dir "$OUT" "montage: речь $(date -u +%H%M%S)"
