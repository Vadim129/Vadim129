#!/usr/bin/env python3
"""Живая проверка стикерпаков на реальном Telegram Bot API (из CI).

Создаёт тестовый пак на владельца, добавляет второй стикер, копирует стикер
по file_id, удаляет отдельный стикер, переименовывает пак, удаляет пак.
Отдельно проверяет ОСНОВНОЙ путь бота (packs.add_to_pack в личный пак)
и аккуратно откатывает свои следы. Вердикты — аннотации ::notice/::error,
чтобы настоящая причина отказа Telegram была видна без логов.

Владелец паков: PROBE_USER_ID, иначе первый пользователь из БД бота
(файл data/bot.db восстанавливается из кэша данных бота в workflow).
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FAILURES: list[str] = []


def note(kind: str, title: str, msg: str) -> None:
    flat = " | ".join(str(msg).splitlines())[:900]
    print(f"::{kind} title={title}::{flat}", flush=True)


def check(title: str, ok: bool, detail: str = "") -> bool:
    note("notice" if ok else "error", f"Packs probe: {title}",
         detail or ("OK" if ok else "FAIL"))
    if not ok:
        FAILURES.append(title)
    return ok


def resolve_user_id() -> int:
    raw = os.getenv("PROBE_USER_ID", "").strip()
    if raw:
        return int(raw)
    db_path = Path(__file__).resolve().parent.parent / "data" / "bot.db"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT user_id FROM users ORDER BY created_at LIMIT 1").fetchone()
            if row:
                return int(row[0])
        finally:
            conn.close()
    return 0


def make_webm(path: Path, color: tuple[int, int, int]) -> Path:
    from PIL import Image, ImageDraw

    from app.encode import encode_frames

    def frames():
        for i in range(10):
            img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse([90 + i * 22, 150, 290 + i * 22, 350], fill=color + (255,))
            d.ellipse([150 + i * 22, 210, 210 + i * 22, 270], fill=(255, 255, 255, 255))
            yield img

    encode_frames(frames, path, fps=10, duration=1.0)
    return path


async def amain() -> int:
    from aiogram import Bot

    from app import packs

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        note("error", "Packs probe", "Нет секрета BOT_TOKEN")
        return 1
    uid = resolve_user_id()
    if not uid:
        note("error", "Packs probe",
             "Не нашёл владельца паков: задай секрет PROBE_USER_ID (твой Telegram ID) "
             "или запусти бота хотя бы раз, чтобы он записал тебя в БД")
        return 1
    note("notice", "Packs probe", f"владелец паков: {str(uid)[:3]}***{str(uid)[-2:]}")

    webm1 = make_webm(Path("/tmp/probe_pack1.webm"), (220, 60, 60))
    webm2 = make_webm(Path("/tmp/probe_pack2.webm"), (60, 160, 60))
    bot = Bot(token=token)
    try:
        me = await bot.get_me()
        username = me.username or "bot"
        test_name = f"dstest{uuid.uuid4().hex[:8]}_by_{username.lower()}"
        note("notice", "Packs probe", f"бот @{username}, тестовый пак {test_name}")

        # --- именной пак: полный цикл
        ok, err = await packs.create_pack_webm(bot, uid, test_name,
                                               "🧪 DeepStick probe", webm1, "🧪")
        if not check("создание пака (createNewStickerSet)", ok, err or test_name):
            return 1
        pack = await packs.get_pack_by_name(bot, test_name)
        check("пак читается, 1 стикер", bool(pack) and len(pack.stickers) == 1,
              f"стикеров: {len(pack.stickers) if pack else 'нет пака'}")

        ok, err = await packs.add_webm_to_pack(bot, uid, test_name, webm2, "🔥")
        check("добавление второго стикера файлом", ok, err or "")
        pack = await packs.get_pack_by_name(bot, test_name)
        n2 = len(pack.stickers) if pack else 0
        check("в паке стало 2 стикера", n2 == 2, f"стикеров: {n2}")

        first_id = pack.stickers[0].file_id if pack and pack.stickers else ""
        ok, err = await packs.add_file_to_pack(bot, uid, test_name, first_id, "🔥")
        note("notice", "Packs probe: копирование по file_id",
             "OK" if ok else f"не критично для теста, Telegram: {err}")

        pack = await packs.get_pack_by_name(bot, test_name)
        before = len(pack.stickers) if pack else 0
        victim = pack.stickers[0].file_id if pack and pack.stickers else ""
        ok, err = await packs.delete_sticker(bot, victim)
        pack = await packs.get_pack_by_name(bot, test_name)
        after = len(pack.stickers) if pack else 0
        check("удаление отдельного стикера", ok and after == before - 1,
              err or f"было {before}, стало {after}")

        ok, err = await packs.rename_pack_by_name(bot, test_name, "🧪 DeepStick renamed")
        pack = await packs.get_pack_by_name(bot, test_name)
        check("переименование пака",
              ok and pack is not None and pack.title == "🧪 DeepStick renamed",
              err or (pack.title if pack else "нет пака"))

        ok, err = await packs.delete_pack(bot, test_name)
        gone = await packs.get_pack_by_name(bot, test_name) is None
        check("удаление пака целиком", ok and gone, err or "")

        # --- основной путь бота: личный пак через add_to_pack
        main_name = packs.pack_name(uid, username)
        before_pack = await packs.get_pack_by_name(bot, main_name)
        before_n = len(before_pack.stickers) if before_pack else 0
        url, _fid, err = await packs.add_to_pack(bot, uid, "Probe", webm1, "🧪")
        after_pack = await packs.get_pack_by_name(bot, main_name)
        after_n = len(after_pack.stickers) if after_pack else 0
        check("ОСНовной флоу: add_to_pack в личный пак",
              bool(url) and after_n == before_n + 1,
              err or f"{url}; стикеров {before_n} -> {after_n}")
        # откат: не трогаем чужие стикеры — убираем только наш тестовый
        if after_pack and after_n > before_n:
            if before_pack is None:
                await packs.delete_pack(bot, main_name)  # пака не было — удаляем наш
            else:
                await packs.delete_sticker(bot, after_pack.stickers[-1].file_id)
    finally:
        await bot.session.close()
    note("notice", "Packs probe итог",
         "ВСЁ РАБОТАЕТ" if not FAILURES else f"провалено шагов: {len(FAILURES)}: {FAILURES}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
