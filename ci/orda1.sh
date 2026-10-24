#!/usr/bin/env bash
# Стадия «Орда-1»: забирает из папки Drive дорожку и референсы персонажей,
# делает Whisper-разметку строк и сетку битов. Результат — папка orda/ в ветке.
set -uo pipefail
cd "$(dirname "$0")/.." && . ci/lib.sh
OUT="$PWD/orda"
mkdir -p "$OUT/refs" "$OUT/analysis"
exec >>"$OUT/logs.txt" 2>&1
set -x
git config user.email "ci@local"
git config user.name "ci"

push_safe() {
  cd "${GITHUB_WORKSPACE:-$PWD}"
  local err=""
  for i in 1 2 3 4 5; do
    git pull --rebase --no-edit -q || true
    err=$(git push 2>&1)
    if [ $? -eq 0 ]; then echo "push ок (попытка $i)"; rm -f "$OUT/ошибка-push.txt"; return 0; fi
    echo "push не прошёл — попытка $i: $err"
    sleep 8
  done
  printf '%s\n' "$err" > "$OUT/ошибка-push.txt"
  return 1
}
commit_out() {
  cd "${GITHUB_WORKSPACE:-$PWD}"
  git add -f "$OUT" || true
  git commit -q -m "ci: $1 $(date -u +%H%M%S)" || echo "нечего коммитить"
  push_safe || true
}

# исходники из папки пользователя
get_drive 14OPoL0FOzTlowCUPGNMg-kaI1KNfBLOl "$OUT/song.mp3"
get_drive 1pgtuYZJ5fJWXNUspwkFVu-ODjKkc2xpY "$OUT/refs/ref-01.jpg"
get_drive 1Qwj_PHUJIVfbFXU6SsWK6aBPsZ06EjAN "$OUT/refs/ref-02.jpg"
ls -la "$OUT" "$OUT/refs"

ensure_ffmpeg
"$FFMPEG" -hide_banner -i "$OUT/song.mp3" 2>&1 | grep -E "Duration|Stream" > "$OUT/track-info.txt" || true
cat "$OUT/track-info.txt"

echo "=== зависимость whisper ==="
python3 -m pip install --quiet --break-system-packages faster-whisper 2>&1 | tail -3 || pip install --quiet faster-whisper 2>&1 | tail -3
python3 -c "import faster_whisper; print('faster-whisper', faster_whisper.__version__)" || echo "нет faster-whisper"

echo "=== разметка ==="
export FFMPEG
python3 ci/orda_analyze.py "$OUT" 2>&1 | tail -120 || echo "разметка exit=$?"

ls -la "$OUT" "$OUT/analysis"
head -c 4000 "$OUT/analysis/расшифровка.txt" 2>/dev/null
set +x
commit_out "орда: разметка"
