"""Личный видеостикерпак пользователя: `ds_<user_id>_by_<bot>`.

Результат — не просто файл, а стикер в паке: его можно слать из панели
стикеров и шарить ссылкой https://t.me/addstickers/<name>.
Управление паком: добавить, показать, удалить последний стикер, переименовать.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InputSticker, StickerSet

log = logging.getLogger(__name__)


def pack_name(user_id: int, bot_username: str) -> str:
    suffix = re.sub(r"[^a-z0-9_]", "", bot_username.lower())
    return f"ds_{user_id}_by_{suffix}"


async def _name(bot: Bot, user_id: int) -> str:
    me = await bot.get_me()
    return pack_name(user_id, me.username or "bot")


async def get_pack(bot: Bot, user_id: int) -> StickerSet | None:
    try:
        return await bot.get_sticker_set(await _name(bot, user_id))
    except TelegramBadRequest:
        return None


async def add_to_pack(bot: Bot, user_id: int, first_name: str,
                      webm: Path, emoji: str) -> tuple[str | None, str | None]:
    """Добавить стикер (создать пак при первом разе) -> (ссылка, file_id стикера)."""
    name = await _name(bot, user_id)
    sticker = InputSticker(sticker=FSInputFile(webm), format="video", emoji_list=[emoji])
    try:
        await bot.add_sticker_to_set(user_id=user_id, name=name, sticker=sticker)
    except TelegramBadRequest as e:
        msg = str(e).lower()
        if "stickerset_invalid" in msg or "not found" in msg or "invalid" in msg:
            try:
                await bot.create_new_sticker_set(
                    user_id=user_id, name=name,
                    title=f"🎬 Мои стикеры — {first_name}"[:64],
                    stickers=[sticker], sticker_type="regular",
                )
            except TelegramBadRequest:
                log.exception("Не удалось создать стикерпак %s", name)
                return None, None
        else:
            log.exception("Не удалось добавить стикер в пак %s", name)
            return None, None
    pack = await get_pack(bot, user_id)
    file_id = pack.stickers[-1].file_id if pack and pack.stickers else None
    return f"https://t.me/addstickers/{name}", file_id


async def delete_last_sticker(bot: Bot, user_id: int) -> bool:
    pack = await get_pack(bot, user_id)
    if not pack or not pack.stickers:
        return False
    try:
        await bot.delete_sticker_from_set(pack.stickers[-1].file_id)
        return True
    except TelegramBadRequest:
        log.exception("Не удалось удалить стикер из пака")
        return False


async def rename_pack(bot: Bot, user_id: int, title: str) -> bool:
    try:
        await bot.set_sticker_set_title(await _name(bot, user_id), title[:64])
        return True
    except TelegramBadRequest:
        log.exception("Не удалось переименовать пак")
        return False
