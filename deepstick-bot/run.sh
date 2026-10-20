#!/usr/bin/env bash
# Запуск без Docker: ./run.sh
set -e
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Создал .env — впиши BOT_TOKEN от @BotFather и запусти снова."
  exit 1
fi
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements-rembg.txt
fi
exec .venv/bin/python bot.py
