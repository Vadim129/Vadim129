"""Диагностика: сколько стикеров в паке по данным Telegram (getStickerSet).

Запуск: BOT_TOKEN=... python tools/pack_info.py <pack_name> [pack_name...]
"""
import json
import os
import sys
import urllib.request

token = os.environ["BOT_TOKEN"]
for name in sys.argv[1:]:
    url = f"https://api.telegram.org/bot{token}/getStickerSet?name={name}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            res = json.loads(r.read())
    except Exception as e:
        print(name, "ERROR", e)
        continue
    if not res.get("ok"):
        print(name, "NOT OK:", str(res)[:200])
        continue
    stickers = res["result"]["stickers"]
    video = sum(1 for s in stickers if s.get("is_video"))
    anim = sum(1 for s in stickers if s.get("is_animated"))
    line = (f"{name}: title={res['result'].get('title')!r} total={len(stickers)} "
            f"video={video} animated_tgs={anim} static={len(stickers) - video - anim}")
    print(line)
    print(f"::error title=PACKINFO::{line}")  # аннотация job: видна через API
