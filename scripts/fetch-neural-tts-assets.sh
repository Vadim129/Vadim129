#!/usr/bin/env bash
# Fetches reproducible, checksum-pinned assets required by the offline Piper TTS.
# The large runtime and models are intentionally not stored in Git.
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
LIBS="$ROOT/app/libs"
ASSETS="$ROOT/app/src/main/assets/piper"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fetch() {
  local url="$1" output="$2" checksum="$3"
  curl --fail --location --retry 3 --connect-timeout 30 --output "$output" "$url"
  printf '%s  %s\n' "$checksum" "$output" | sha256sum --check --status
}

mkdir -p "$LIBS" "$ASSETS"

fetch \
  'https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.8/sherpa-onnx-1.13.8.aar' \
  "$LIBS/sherpa-onnx-1.13.8.aar" \
  '633c24321e06b1fe79feafa03ea16cbc0f8a286641e2da3559bac91bdb13bd96'

fetch_voice() {
  local id archive checksum
  id="$1"
  checksum="$2"
  archive="$TMP/$id.tar.bz2"
  fetch \
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-ru_RU-${id}-medium-int8.tar.bz2" \
    "$archive" "$checksum"
  mkdir -p "$TMP/$id" "$ASSETS/$id"
  tar -xjf "$archive" -C "$TMP/$id"
  # Archives published over the years have used both a top-level directory and
  # a flat layout. Locate the actual ONNX model rather than relying on either.
  local model source
  model="$(find "$TMP/$id" -type f -name '*.onnx' | head -n 1)"
  if [[ -z "$model" || ! -f "$model" ]]; then
    echo "Piper archive for $id has no ONNX model" >&2
    find "$TMP/$id" -maxdepth 3 -print >&2 || true
    exit 1
  fi
  source="$(dirname "$model")"
  rm -rf "$ASSETS/$id"
  mkdir -p "$ASSETS/$id"
  cp -a "$model" "$ASSETS/$id/model.onnx"
  cp -a "$source/tokens.txt" "$ASSETS/$id/tokens.txt"
  # The two Russian Piper archives carry byte-identical eSpeak data. Keep it
  # once instead of packaging it twice; both voices use this shared directory.
  if [[ ! -d "$ASSETS/espeak-ng-data" ]]; then
    cp -a "$source/espeak-ng-data" "$ASSETS/espeak-ng-data"
  fi
  test -f "$ASSETS/$id/model.onnx"
  test -f "$ASSETS/$id/tokens.txt"
  test -d "$ASSETS/espeak-ng-data"
}

# Always refresh shared pronunciation data together with the pinned voice release.
rm -rf "$ASSETS/espeak-ng-data"
fetch_voice irina 'b0000a509f7551a80742eed5c43b8eb03f469cb9f0a42f6feee96ce0da0ebab8'
fetch_voice dmitri '7636793307f634ce54c6e65528a91a61683114f1a6635a08caf64ba6c54e6a63'

echo "Neural TTS runtime and Russian Piper voices are ready."
