# общие шаги: исходник и 16 кГц моно wav
SRC=/home/runner/montage-src.mp4; AUD=/home/runner/montage-audio.wav
need_src() {
  if [ ! -s "$SRC" ]; then
    python3 -m pip install --quiet gdown
    gdown "https://drive.google.com/uc?id=14w459uIJuDZTB5A7fj2E54gS3tOPLLhJ" -O "$SRC"
  fi
  if [ ! -s "$AUD" ]; then
    ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vn -ac 1 -ar 16000 -c:a pcm_s16le "$AUD"
  fi
  ls -la "$SRC" "$AUD"
}
push_dir() {   # $1 = папка, $2 = сообщение
  cd "$(dirname "$0")/.."
  git config user.email "ci@local"; git config user.name "ci"
  git add -f "$1" || true
  git commit -q -m "$2" || { echo "нечего коммитить"; exit 0; }
  for i in 1 2 3 4 5 6 7 8; do
    if git push 2>/tmp/push.err; then echo "push ок ($i)"; exit 0; fi
    echo "push отказ ($i): $(tail -2 /tmp/push.err)"
    git pull --rebase --autostash --no-edit -q || git rebase --abort || true
    sleep 4
  done
  exit 1
}
