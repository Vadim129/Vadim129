#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=montage/a3b; mkdir -p "$OUT"
exec > >(tee -a "$OUT/log.txt") 2>&1
set -x
. montage/common.sh
need_src
python3 -m pip install --quiet numpy scipy librosa soundfile
timeout 1200 python3 montage/sfx.py "$AUD" "$OUT" 430 900
ls -la "$OUT"
push_dir "$OUT" "montage: фоли 430-900 $(date -u +%H%M%S)"
