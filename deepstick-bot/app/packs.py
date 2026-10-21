"""Стикерпаки пользователя.

Основной личный пак: `ds_<user_id>_by_<bot>` — создаётся автоматически
с первым стикером. Плюс именные паки `ds_<user_id>_p<tag>_by_<bot>`,
которые пользователь создаёт сам («Создать пак»): в любой пак можно
добавлять стикеры (из истории генераций или только что сделанный),
удалять отдельные стикеры и удалять пак целиком.
Ссылка на пак: https://t.me/addstickers/<name>.
"""
from __future__ import annotations

import logging
import re
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


def _err(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"[:220]


async def add_to_named_pack(bot: Bot, user_id: int, name: str, webm: Path, emoji: str,
                            create_title: str | None = None,
                            ) -> tuple[str | None, str | None, str | None]:
    """Добавить стикер файлом в пак `name` -> (ссылка, file_id, ошибка).

    Если пака нет и задан create_title — создаёт пак с этим стикером.
    """
    sticker = InputSticker(sticker=FSInputFile(webm), format="video", emoji_list=[emoji])
    try:
        await bot.add_sticker_to_set(user_id=user_id, name=name, sticker=sticker)
    except TelegramBadRequest as e:
        msg = str(e).lower()
        missing = "stickerset_invalid" in msg or "not found" in msg
        if missing and create_title:
            try:
                await bot.create_new_sticker_set(
                    user_id=user_id, name=name, title=create_title[:64],
                    stickers=[sticker], sticker_type="regular",
                )
            except TelegramBadRequest as e2:
                log.exception("Не удалось создать стикерпак %s", name)
                return None, None, _err(e2)
        else:
            log.exception("Не удалось добавить стикер в пак %s", name)
            return None, None, _err(e)
    pack = await get_pack_by_name(bot, name)
    file_id = pack.stickers[-1].file_id if pack and pack.stickers else None
    return f"https://t.me/addstickers/{name}", file_id, None


async def add_to_pack(bot: Bot, user_id: int, first_name: str,
                      webm: Path, emoji: str) -> tuple[str | None, str | None, str | None]:
    """Добавить стикер в основной личный пак (создать при первом разе)."""
    name = await _name(bot, user_id)
    return await add_to_named_pack(
        bot, user_id, name, webm, emoji,
        create_title=f"🎬 Мои стикеры — {first_name}")


async def rename_pack(bot: Bot, user_id: int, title: str) -> tuple[bool, str | None]:
    return await rename_pack_by_name(bot, await _name(bot, user_id), title)


# ---------------------------------------------------------- именные паки юзера
def custom_pack_name(user_id: int, bot_username: str, tag: str) -> str:
    """Имя дополнительного пака: ds_<uid>_p<tag>_by_<bot> (<=64, [a-z0-9_])."""
    suffix = re.sub(r"[^a-z0-9_]", "", bot_username.lower())
    tag = re.sub(r"[^a-z0-9]", "", tag.lower())[:8]
    return f"ds_{user_id}_p{tag}_by_{suffix}"[:64]


async def get_pack_by_name(bot: Bot, name: str) -> StickerSet | None:
    try:
        return await bot.get_sticker_set(name)
    except TelegramBadRequest:
        return None


async def create_pack_with_file(bot: Bot, user_id: int, name: str, title: str,
                                file_id: str, emoji: str) -> tuple[bool, str | None]:
    """Создать пак, первый стикер — уже существующий file_id (пак не бывает пустым)."""
    sticker = InputSticker(sticker=file_id, format="video", emoji_list=[emoji])
    try:
        await bot.create_new_sticker_set(
            user_id=user_id, name=name, title=title[:64],
            stickers=[sticker], sticker_type="regular")
        return True, None
    except TelegramBadRequest as e:
        log.exception("Не удалось создать пак %s", name)
        return False, _err(e)


async def create_pack_webm(bot: Bot, user_id: int, name: str, title: str,
                           webm: Path, emoji: str) -> tuple[bool, str | None]:
    """Создать пак, первый стикер — видеофайл webm."""
    sticker = InputSticker(sticker=FSInputFile(webm), format="video", emoji_list=[emoji])
    try:
        await bot.create_new_sticker_set(
            user_id=user_id, name=name, title=title[:64],
            stickers=[sticker], sticker_type="regular")
        return True, None
    except TelegramBadRequest as e:
        log.exception("Не удалось создать пак %s", name)
        return False, _err(e)


async def add_file_to_pack(bot: Bot, user_id: int, name: str,
                           file_id: str, emoji: str) -> tuple[bool, str | None]:
    """Добавить в пак копию стикера по его file_id."""
    sticker = InputSticker(sticker=file_id, format="video", emoji_list=[emoji])
    try:
        await bot.add_sticker_to_set(user_id=user_id, name=name, sticker=sticker)
        return True, None
    except TelegramBadRequest as e:
        log.exception("Не удалось добавить стикер в пак %s", name)
        return False, _err(e)


async def add_webm_to_pack(bot: Bot, user_id: int, name: str,
                           webm: Path, emoji: str) -> tuple[bool, str | None]:
    """Добавить в пак стикер видеофайлом webm."""
    sticker = InputSticker(sticker=FSInputFile(webm), format="video", emoji_list=[emoji])
    try:
        await bot.add_sticker_to_set(user_id=user_id, name=name, sticker=sticker)
        return True, None
    except TelegramBadRequest as e:
        log.exception("Не удалось добавить стикер в пак %s", name)
        return False, _err(e)


async def delete_sticker(bot: Bot, file_id: str) -> tuple[bool, str | None]:
    """Удалить конкретный стикер из его пака."""
    try:
        await bot.delete_sticker_from_set(file_id)
        return True, None
    except TelegramBadRequest as e:
        log.exception("Не удалось удалить стикер из пака")
        return False, _err(e)


async def delete_pack(bot: Bot, name: str) -> tuple[bool, str | None]:
    """Удалить пак целиком (Bot API: deleteStickerSet)."""
    try:
        await bot.delete_sticker_set(name)
        return True, None
    except (TelegramBadRequest, AttributeError) as e:
        log.exception("Не удалось удалить пак %s", name)
        return False, _err(e)


async def rename_pack_by_name(bot: Bot, name: str, title: str) -> tuple[bool, str | None]:
    try:
        await bot.set_sticker_set_title(name, title[:64])
        return True, None
    except TelegramBadRequest as e:
        log.exception("Не удалось переименовать пак %s", name)
        return False, _err(e)


_PACK_LINK_RE = re.compile(r"addstickers/([A-Za-z0-9_]{3,64})")


def parse_pack_name(text: str) -> str | None:
    """Извлечь имя набора: ссылка t.me/addstickers/<name>, просто имя или None."""
    text = (text or "").strip()
    m = _PACK_LINK_RE.search(text)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_]{3,64}", text):
        return text
    return None


def alive_pack_name(src_name: str, bot_username: str) -> str:
    """Имя нового «оживлённого» набора: <src>_alive_by_<bot>, безопасно и <=64."""
    base = re.sub(r"[^A-Za-z0-9_]", "_", src_name)[:36].strip("_") or "pack"
    return f"{base}_alive_by_{bot_username}"[:64]
