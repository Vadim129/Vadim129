# общие функции для этапов сборки
enc_payload() {   # $1 = папка с результатами (относительно workspace)
  [ -n "${GITHUB_WORKSPACE:-}" ] && cd "$GITHUB_WORKSPACE"
  local OUT="$1"
  mkdir -p payload
  openssl rand 32 > /tmp/aes.key
  openssl pkeyutl -encrypt -pubin -inkey ci/pub.pem -in /tmp/aes.key -out payload/aes.key.enc
  tar -czf /tmp/payload.tar.gz -C "$(dirname "$OUT")" "$(basename "$OUT")"
  openssl enc -aes-256-cbc -pbkdf2 -in /tmp/payload.tar.gz -out payload/payload.enc -pass file:/tmp/aes.key
  ls -la payload
}
get_drive() {   # $1 = id, $2 = имя файла
  python3 -m pip install --quiet --break-system-packages gdown >/dev/null 2>&1 || pip install --quiet gdown
  gdown "$1" -O "$2" || curl -sL "https://drive.google.com/uc?export=download&id=$1" -o "$2"
  ls -la "$2"
}
get_ffmpeg() {
  python3 -m pip install --quiet --break-system-packages imageio-ffmpeg >/dev/null 2>&1 || pip install --quiet imageio-ffmpeg
  export FFMPEG="$(python3 -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')"
  echo "ffmpeg: $FFMPEG"
  # ffprobe-подобное: длительность/битрейт из stderr ffmpeg
  "$FFMPEG" -hide_banner -i "$1" 2>&1 | grep -E "Duration|bitrate|Stream" | head -5
}
