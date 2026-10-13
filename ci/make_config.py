#!/usr/bin/env python3
"""Собирает конфиг.json для движка «Чернильный клип».

Использование:
  python3 ci/make_config.py <папка-пакета> <файл-сценария> <папка-вывода>

Файл сценария — это то, что агент пишет по документам пакета:
  строки настроек («стиль: цветные», «бумага: клетка»…),
  затем строки сцен («солдат 0:00-0:16», «картинка: подпись 0:48-1:04»).
Настройки по умолчанию задают «цветные карандаши про военного».
"""
import json, pathlib, sys

pkg = pathlib.Path(sys.argv[1])          # .../клипы (внутри — движок/)
script_file = pathlib.Path(sys.argv[2])
out_dir = pathlib.Path(sys.argv[3]).resolve()

script_text = script_file.read_text(encoding='utf-8')

cfg = {
    "engine": "движок",
    "track": "трек.mp3",
    "profile": "color",          # цветные карандаши
    "paper": "grid",             # клетка
    "palette": "warm",           # тёплая
    "mood": "day",               # день
    "dens": 1.1,
    "seed": 8,
    "quality": "720x1280",
    "compress": "auto",
    "crf": 23,
    "preset": "veryfast",
    "whisper": False,            # сцены расставлены по времени вручную
    "cover_at": 8,
    "script_text": script_text,
    "out": "готовые/клип.mp4",
}

(pkg / 'конфиг.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
print('конфиг собран:', pkg / 'конфиг.json')
