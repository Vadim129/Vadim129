#!/usr/bin/env bash
# Стадия «исходники»: вытаскивает тексты движка (js/html) в out7/engine — чтобы
# поправить фразы сцен под тему. Плюс сохраняет, где встречаются «фразы-подушки».
set -uo pipefail
cd "$(dirname "$0")/.." && . ci/lib.sh
OUT="$PWD/out7"; mkdir -p "$OUT"
exec >>"$OUT/logs.txt" 2>&1
set -x
ZIP_ID=1a--SHk9H2qjD7VhupI-bzCnwOmL6CxKy
get_drive "$ZIP_ID" /tmp/package.zip
rm -rf /tmp/pkg && mkdir -p /tmp/pkg && unzip -q -o /tmp/package.zip -d /tmp/pkg
PKG=/tmp/pkg/клипы
mkdir -p "$OUT/engine"
(cd "$PKG/движок" && find . -type f \( -name '*.js' -o -name '*.mjs' -o -name '*.html' \) \
  -not -path './node_modules/*' -not -path './vendor/*' -not -path './models/*' -not -path './.git/*' -size -200k \
  | while read -r f; do mkdir -p "$OUT/engine/$(dirname "$f")"; cp -f "$f" "$OUT/engine/$f"; done)
echo "=== где живут фразы-подушки ==="
grep -rn "сегодня\|можно\|подушк\|фраз" "$OUT/engine" 2>/dev/null | head -40 > "$OUT/фразы.txt" || true
cat "$OUT/фразы.txt"
echo "=== подписи сцен (p.text) ==="
grep -rn "p\.text(" "$OUT/engine" 2>/dev/null | head -80 >> "$OUT/фразы.txt" || true
tail -60 "$OUT/фразы.txt"
echo "=== размер выгрузки ==="
du -sh "$OUT/engine"; find "$OUT/engine" -type f | wc -l
set +x
cd "${GITHUB_WORKSPACE:-$PWD}"
git add -f "$OUT"
git -c user.email=ci@local -c user.name=ci commit -m "ci: исходники движка $(date -u +%H%M%S)" || echo "нечего коммитить"
git push || echo "push не прошёл"
