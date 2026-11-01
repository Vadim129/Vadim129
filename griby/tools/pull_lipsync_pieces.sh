#!/usr/bin/env bash
# Забирает готовые куски липсинка из ветки (dist/lipsync) в workspace и печатает список новых
set -u
BR="arena/7213a08a-vadim129"
DST="/home/user/Vadim129/griby/05_Клип/липсинк-куски"
mkdir -p "$DST"
names=$(curl -s -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/Vadim129/Vadim129/contents/dist/lipsync?ref=$BR" \
  | python3 -c "import sys,json;
d=json.load(sys.stdin)
print('\n'.join(f\"{x['name']}|{x['size']}\" for x in d if isinstance(d,list)))" 2>/dev/null)
[ -z "${names:-}" ] && { echo "пока пусто"; exit 0; }
echo "$names" | while IFS='|' read -r n s; do
  [ -f "$DST/$n" ] && { echo "есть: $n"; continue; }
  curl -sL -H "Accept: application/vnd.github.raw" \
    "https://api.github.com/repos/Vadim129/Vadim129/contents/dist/lipsync/$n?ref=$BR" -o "$DST/$n"
  echo "скачал: $n ($(du -h "$DST/$n" | cut -f1))"
done
