# общие функции этапов сборки (без вложенных tee — вместо этого exec >> лог)
enc_payload() {   # $1 = папка с результатами (относительно workspace)
  cd "${GITHUB_WORKSPACE:-$PWD}"
  local OUT="$1"
  mkdir -p payload
  openssl rand 32 > /tmp/aes.key
  openssl pkeyutl -encrypt -pubin -inkey ci/pub.pem -in /tmp/aes.key -out payload/aes.key.enc
  tar -czf /tmp/payload.tar.gz -C "$(dirname "$OUT")" "$(basename "$OUT")"
  openssl enc -aes-256-cbc -pbkdf2 -in /tmp/payload.tar.gz -out payload/payload.enc -pass file:/tmp/aes.key
  ls -la payload
}
get_drive() {   # $1 = id, $2 = имя файла
  python3 -m pip install --quiet --break-system-packages gdown 2>/dev/null || pip install --quiet gdown
  gdown "$1" -O "$2" 2>&1 | tail -2 || curl -sL "https://drive.google.com/uc?export=download&id=$1" -o "$2"
  ls -la "$2"
}
ensure_ffmpeg() {   # ставит ffmpeg/ffprobe (apt → imageio-ffmpeg) и экспортирует FFMPEG/FFPROBE
  if ! command -v ffmpeg >/dev/null 2>&1; then
    (sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg) >/dev/null 2>&1 || true
  fi
  if command -v ffmpeg >/dev/null 2>&1; then
    export FFMPEG=ffmpeg
    command -v ffprobe >/dev/null 2>&1 && export FFPROBE=ffprobe
  else
    python3 -m pip install --quiet --break-system-packages imageio-ffmpeg 2>/dev/null || pip install --quiet imageio-ffmpeg
    export FFMPEG="$(python3 -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')"
  fi
  echo "ffmpeg: $FFMPEG"
  "$FFMPEG" -hide_banner -version 2>&1 | head -1
}

get_ffmpeg() {
  python3 -m pip install --quiet --break-system-packages imageio-ffmpeg 2>/dev/null || pip install --quiet imageio-ffmpeg
  export FFMPEG="$(python3 -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')"
  echo "ffmpeg: $FFMPEG"
  "$FFMPEG" -hide_banner -i "$1" 2>&1 | grep -E "Duration|bitrate|Stream" | head -4
}
