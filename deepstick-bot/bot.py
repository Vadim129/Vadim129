#!/usr/bin/env python3
"""Клон @DeepStickBot: фото -> стиль -> сценарий -> видеостикер + личный пак.

Режимы генерации:
  * локальный (по умолчанию, бесплатно): вырезание фона + Pillow-анимация;
  * нейро (AI_PROVIDER=replicate|fal): фото+промпт -> image-to-video модель,
    как у оригинала, результат перепаковывается в WebM-стикер.
Плюс: присланное видео/GIF конвертируется в видеостикер напрямую.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher, F  # noqa: E402
from aiogram.enums import ChatAction  # noqa: E402
from aiogram.exceptions import TelegramBadRequest  # noqa: E402
from aiogram.filters import Command, CommandStart  # noqa: E402
from aiogram.fsm.context import FSMContext  # noqa: E402
from aiogram.fsm.state import State, StatesGroup  # noqa: E402
from aiogram.types import (  # noqa: E402
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.ai_video import ai_enabled, generate_ai_video  # noqa: E402
from app.effects import prepare_subject, render_frames  # noqa: E402
from app.encode import convert_video, encode_frames  # noqa: E402
from app.packs import add_to_pack, send_last_sticker  # noqa: E402
from app.scenarios import (  # noqa: E402
    SCENARIOS,
    SCENARIOS_BY_ID,
    STYLES,
    STYLES_BY_ID,
    match_scenario,
)
from config import Config  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("deepstick")

CFG = Config.load()
dp = Dispatcher()
_sem = asyncio.Semaphore(2)  # не больше 2 генераций одновременно
BASE = Path(tempfile.gettempdir()) / "deepstick_jobs"
BASE.mkdir(parents=True, exist_ok=True)


class Flow(StatesGroup):
    waiting_photo = State()
    waiting_style = State()
    waiting_scenario = State()
    waiting_custom_text = State()


# ------------------------------------------------------------------ клавиатуры
def styles_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{s.emoji} {s.title}", callback_data=f"style:{s.id}")]
            for s in STYLES]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def scenarios_kb() -> InlineKeyboardMarkup:
    rows, row = [], []
    for s in SCENARIOS:
        row.append(InlineKeyboardButton(text=f"{s.emoji} {s.title}", callback_data=f"scen:{s.id}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✍️ Свой сценарий (текстом)", callback_data="scen:custom")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ------------------------------------------------------------------ генерация
def _render_local(photo: Path, style: str, effect: str, out: Path) -> None:
    from PIL import Image

    with Image.open(photo) as img:
        subject = prepare_subject(img.copy(), style=style, remove_bg=CFG.remove_bg)
    encode_frames(
        lambda: render_frames(subject, effect, CFG.sticker_fps, CFG.sticker_duration),
        out, fps=CFG.sticker_fps, duration=CFG.sticker_duration,
    )


async def _deliver(message: Message, webm: Path, emoji: str) -> None:
    user = message.from_user
    assert user
    pack_url = await add_to_pack(message.bot, user.id, user.first_name, webm, emoji)
    if pack_url and await send_last_sticker(message.bot, message.chat.id, user.id):
        await message.answer(f"✅ Готово! Твой пак:\n{pack_url}\n\nСделаем ещё? Просто пришли фото 📸")
    else:  # пак не завёлся — хотя бы файлом/стикером напрямую
        try:
            await message.answer_sticker(FSInputFile(webm))
        except TelegramBadRequest:
            await message.answer_document(FSInputFile(webm))
        await message.answer("✅ Готово! Пришли ещё фото 📸")


async def _generate(message: Message, photo: Path, style_id: str,
                    scenario_id: str | None, custom_text: str | None,
                    job_dir: Path) -> None:
    style = STYLES_BY_ID[style_id]
    scenario = SCENARIOS_BY_ID[scenario_id] if scenario_id else match_scenario(custom_text or "")
    emoji = scenario.emoji
    webm = job_dir / "sticker.webm"
    status = await message.answer("🎬 Генерирую видеостикер…")
    try:
        await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO)
        async with _sem:
            if ai_enabled():
                prompt = (
                    f"{style.ai_prompt}. The main character from the photo: "
                    f"{custom_text or scenario.ai_prompt}. "
                    "Keep the face and appearance of the person from the photo, "
                    "short seamless loop, no text, no watermark."
                )
                try:
                    mp4 = job_dir / "ai.mp4"
                    await generate_ai_video(photo, prompt, mp4)
                    await asyncio.to_thread(convert_video, mp4, webm)
                except Exception:
                    log.exception("AI-режим упал — откатываюсь на локальную анимацию")
                    await status.edit_text("⚠️ Нейросеть недоступна, делаю локальную анимацию…")
                    await asyncio.to_thread(_render_local, photo, style_id, scenario.effect, webm)
            else:
                await asyncio.to_thread(_render_local, photo, style_id, scenario.effect, webm)
        await status.delete()
        await _deliver(message, webm, emoji)
    except Exception as e:
        log.exception("Генерация упала")
        await status.edit_text(f"😖 Не получилось: {e}\nПопробуй другое фото.")
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


def _job_dir(user_id: int) -> Path:
    d = BASE / f"{user_id}_{uuid.uuid4().hex[:8]}"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ------------------------------------------------------------------ handlers
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.set_state(Flow.waiting_photo)
    mode = "🧠 нейро-режим (image-to-video)" if ai_enabled() else "🆓 локальный режим"
    await message.answer(
        "👋 Я делаю *персональные видеостикеры* из фото — как @DeepStickBot.\n\n"
        "📸 *Пришли фото* (лучше, где хорошо видно лицо/фигуру) — "
        "потом выберешь стиль и сценарий: полёт на ракете 🚀, танец 💃, портал 🌀…\n\n"
        f"Режим генерации: {mode}\n"
        "Ещё могу: пришли *видео или GIF* ≤3 c — превращу в видеостикер.",
        parse_mode="Markdown",
    )


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "/start — сделать стикер из фото\n"
        "Пришли видео/GIF — сделаю видеостикер из него\n"
        "/cancel — сбросить текущий сценарий"
    )


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Flow.waiting_photo)
    await message.answer("Ок, сбросил. Пришли фото 📸")


@dp.callback_query(F.data == "cancel")
async def cb_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Flow.waiting_photo)
    await cb.message.edit_text("Ок, сбросил. Пришли фото 📸")
    await cb.answer()


@dp.message(Flow.waiting_photo, F.photo)
@dp.message(F.photo)  # фото вне состояния — начинаем флоу с него
async def on_photo(message: Message, state: FSMContext) -> None:
    job = _job_dir(message.from_user.id)  # type: ignore[union-attr]
    photo_path = job / "photo.jpg"
    await message.bot.download(message.photo[-1], destination=photo_path)
    await state.update_data(photo=str(photo_path), job=str(job))
    await state.set_state(Flow.waiting_style)
    await message.answer("👍 Фото получил. Выбери *стиль*:", parse_mode="Markdown",
                         reply_markup=styles_kb())


@dp.callback_query(Flow.waiting_style, F.data.startswith("style:"))
async def on_style(cb: CallbackQuery, state: FSMContext) -> None:
    style_id = cb.data.split(":", 1)[1]
    await state.update_data(style=style_id)
    await state.set_state(Flow.waiting_scenario)
    await cb.message.edit_text(
        f"Стиль: {STYLES_BY_ID[style_id].title}\nТеперь выбери *сценарий* "
        "или опиши свой:", parse_mode="Markdown", reply_markup=scenarios_kb())
    await cb.answer()


@dp.callback_query(Flow.waiting_scenario, F.data == "scen:custom")
async def on_custom(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Flow.waiting_custom_text)
    await cb.message.edit_text(
        "✍️ Опиши сценарий одним предложением, например:\n"
        "«лечу на ракете», «открываю холодильник-портал», «дирижирую оркестром котов»")
    await cb.answer()


@dp.callback_query(Flow.waiting_scenario, F.data.startswith("scen:"))
async def on_scenario(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    await state.set_state(Flow.waiting_photo)
    await cb.answer("Генерирую…")
    await _generate(cb.message, Path(data["photo"]), data.get("style", "original"),
                    cb.data.split(":", 1)[1], None, Path(data["job"]))


@dp.message(Flow.waiting_custom_text, F.text)
async def on_custom_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = message.text or ""
    await state.clear()
    await state.set_state(Flow.waiting_photo)
    await _generate(message, Path(data["photo"]), data.get("style", "original"),
                    None, text, Path(data["job"]))


@dp.message(F.video | F.animation | F.document)
async def on_video(message: Message, state: FSMContext) -> None:
    media = message.video or message.animation or message.document
    if not media:
        return
    if message.document and (media.mime_type or "").startswith("image/"):  # фото файлом, без сжатия
        job = _job_dir(message.from_user.id)  # type: ignore[union-attr]
        photo_path = job / "photo.jpg"
        await message.bot.download(media, destination=photo_path)
        await state.update_data(photo=str(photo_path), job=str(job))
        await state.set_state(Flow.waiting_style)
        await message.answer("👍 Фото получил. Выбери *стиль*:", parse_mode="Markdown",
                             reply_markup=styles_kb())
        return
    if message.document and not (media.mime_type or "").startswith(("video/", "image/gif")):  # type: ignore[union-attr]
        await message.answer("Это не видео. Пришли 📸 фото или 🎞 видео/GIF.")
        return
    duration = getattr(media, "duration", None)
    if duration and duration > 10:
        await message.answer("Видео длинновато — видеостикер ≤3 c. Пришли покороче (обрежу до 3 c, если ≤10 c).")
        return
    job = _job_dir(message.from_user.id)  # type: ignore[union-attr]
    src = job / "input.mp4"
    status = await message.answer("🎞 Конвертирую в видеостикер…")
    try:
        await message.bot.download(media, destination=src)
        webm = job / "sticker.webm"
        async with _sem:
            await asyncio.to_thread(convert_video, src, webm)
        await status.delete()
        await _deliver(message, webm, "🎬")
    except Exception as e:
        log.exception("Конверсия видео упала")
        await status.edit_text(f"😖 Не получилось: {e}")
    finally:
        shutil.rmtree(job, ignore_errors=True)


@dp.message()
async def fallback(message: Message) -> None:
    await message.answer("Пришли 📸 фото — сделаю видеостикер, или 🎞 видео/GIF ≤3 c.")


def main() -> None:
    bot = Bot(CFG.token)
    dp.run_polling(bot)


if __name__ == "__main__":
    main()
