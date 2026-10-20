"""Личный видеостикерпак пользователя: `ds_<user_id>_by_<bot>`.

Так делает и оригинал: результат не просто файл, а стикер в паке,
который можно слать из панели стикеров и шарить ссылкой
https://t.me/addstickers/<name>.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InputSticker

log = logging.getLogger(__name__)


def pack_name(user_id: int, bot_username: str) -> str:
    suffix = re.sub(r"[^a-z0-9_]", "", bot_username.lower())
    return f"ds_{user_id}_by_{suffix}"


async def add_to_pack(bot: Bot, user_id: int, first_name: str,
                      webm: Path, emoji: str) -> str | None:
    """Добавить стикер в пак (создать пак при первом разе). Вернуть ссылку или None."""
    me = await bot.get_me()
    name = pack_name(user_id, me.username or "bot")
    sticker = InputSticker(sticker=FSInputFile(webm), format="video", emoji_list=[emoji])
    try:
        await bot.add_sticker_to_set(user_id=user_id, name=name, sticker=sticker)
    except TelegramBadRequest as e:
        msg = str(e).lower()
        if "stickerset_invalid" in msg or "not found" in msg or "invalid" in msg:
            try:
                await bot.create_new_sticker_set(
                    user_id=user_id, name=name,
                    title=f"🎬 Мои DeepStick — {first_name}"[:64],
                    stickers=[sticker], sticker_type="regular",
                )
            except TelegramBadRequest:
                log.exception("Не удалось создать стикерпак %s", name)
                return None
        else:
            log.exception("Не удалось добавить стикер в пак %s", name)
            return None
    return f"https://t.me/addstickers/{name}"


async def send_last_sticker(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Прислать именно стикером из пака (кликабельным), а не файлом."""
    try:
        me = await bot.get_me()
        sticker_set = await bot.get_sticker_set(pack_name(user_id, me.username or "bot"))
        if sticker_set.stickers:
            await bot.send_sticker(chat_id, sticker_set.stickers[-1].file_id)
            return True
    except Exception:
        log.exception("Не удалось прислать стикер из пака")
    return False
