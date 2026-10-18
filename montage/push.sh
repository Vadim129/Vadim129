#!/usr/bin/env bash
# $1 = путь, который коммитим; $2 = сообщение
cd "$(dirname "$0")/.."
git config user.email "ci@local"; git config user.name "ci"
git add -f "$1" || true
git commit -q -m "$2" || { echo "нечего коммитить"; return 0 2>/dev/null || exit 0; }
for i in 1 2 3 4 5 6; do
  if git push 2>/tmp/push.err; then echo "push ок ($i)"; exit 0; fi
  echo "push отказ ($i): $(tail -2 /tmp/push.err)"
  git pull --rebase --no-edit -q || git rebase --abort || true
  sleep 5
done
exit 1
