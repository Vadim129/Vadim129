#!/usr/bin/env python3
"""Клон @DeepStickBot (все функции, кроме оплаты): фото -> стиль -> сценарий ->
эмодзи -> видеостикер в личном паке пользователя.

Возможности:
  * фото (обычное, файлом, альбомом), стикер и видео/GIF как исходник;
  * 17 сценариев, 7 стилей, свой сценарий текстом, выбор эмодзи стикера;
  * личный стикерпак: посмотреть, переименовать, удалить последний стикер;
  * история генераций с повторной отправкой, «повторить» и «другой сценарий»;
  * настройки: вырезание фона, автодобавление в пак;
  * отмена текущей генерации, одна активная генерация на пользователя;
  * админ-статистика /stats (ADMIN_IDS). Оплаты и платных лимитов нет.

Генерация: локальная нейросеть вырезания фона (rembg/u2net) + анимация;
опционально image-to-video провайдер (AI_PROVIDER=hf бесплатно / replicate / fal).
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher, F  # noqa: E402
from aiogram.enums import ChatAction  # noqa: E402
from aiogram.exceptions import TelegramBadRequest, TelegramUnauthorizedError  # noqa: E402
from aiogram.filters import Command, CommandStart  # noqa: E402
from aiogram.fsm.context import FSMContext  # noqa: E402
from aiogram.fsm.state import State, StatesGroup  # noqa: E402
from aiogram.types import (  # noqa: E402
    BotCommand,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from app import packs  # noqa: E402
from app.ai_video import ai_enabled, generate_ai_video  # noqa: E402
from app.db import Database  # noqa: E402
from app.effects import prepare_subject, render_frames  # noqa: E402
from app.encode import convert_video, encode_frames  # noqa: E402
from app.matting import matte_encode  # noqa: E402
from app.scenarios import (  # noqa: E402
    SCENARIOS,
    SCENARIOS_BY_ID,
    STYLES,
    STYLES_BY_ID,
    build_prompt,
    match_scenario,
)
from config import Config  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("deepstick")

CFG = Config.load()
DB = Database(CFG.data_dir / "bot.db")
dp = Dispatcher()
BASE = Path(tempfile.gettempdir()) / "deepstick_jobs"
BASE.mkdir(parents=True, exist_ok=True)
USERS_DIR = CFG.data_dir / "users"

_tasks: dict[int, asyncio.Task] = {}       # одна активная генерация на юзера
_seen_albums: dict[str, float] = {}        # media_group_id -> когда видели

MENU_NEW = "🎬 Сделать стикер"
MENU_PACK = "📦 Мой пак"
MENU_HISTORY = "🕐 История"
MENU_SETTINGS = "⚙️ Настройки"
MENU_HELP = "ℹ️ Помощь"

EMOJIS = ["😂", "😍", "😮", "🔥", "😎", "🤬", "🥺", "👍",
          "💃", "🚀", "😴", "🏆", "💸", "😭", "🤪"]


class Flow(StatesGroup):
    waiting_photo = State()
    waiting_style = State()
    waiting_scenario = State()
    waiting_custom_text = State()
    waiting_emoji = State()
    waiting_pack_title = State()


# ------------------------------------------------------------------ клавиатуры
def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_NEW)],
            [KeyboardButton(text=MENU_PACK), KeyboardButton(text=MENU_HISTORY)],
            [KeyboardButton(text=MENU_SETTINGS), KeyboardButton(text=MENU_HELP)],
        ], resize_keyboard=True)


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


def emoji_kb(auto_emoji: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"✨ Авто ({auto_emoji})", callback_data="emoji:auto")]]
    row = []
    for e in EMOJIS:
        row.append(InlineKeyboardButton(text=e, callback_data=f"emoji:{e}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ К сценариям", callback_data="back:scenarios")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def generating_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏹ Отменить генерацию", callback_data="gen:cancel")]])


def after_kb(pack_url: str | None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔁 Повторить", callback_data="again:repeat"),
         InlineKeyboardButton(text="🎲 Другой сценарий", callback_data="again:scenario")],
        [InlineKeyboardButton(text="🎨 Сменить стиль", callback_data="again:style"),
         InlineKeyboardButton(text="🕐 История", callback_data="nav:history")],
    ]
    if pack_url:
        rows.append([InlineKeyboardButton(text="📦 Открыть мой пак", url=pack_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_kb(user_id: int) -> InlineKeyboardMarkup:
    s = DB.get_settings(user_id)
    mark = {True: "✅ вкл", False: "❌ выкл"}
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✂️ Вырезать фон: {mark[s['remove_bg']]}",
                              callback_data="set:remove_bg")],
        [InlineKeyboardButton(text=f"📦 Добавлять в пак: {mark[s['auto_pack']]}",
                              callback_data="set:auto_pack")],
        [InlineKeyboardButton(text="✏️ Переименовать пак", callback_data="pack:rename")],
    ])


# ------------------------------------------------------------------ middleware
async def _user_middleware(handler, event, data):  # noqa: ANN001, ANN202
    user = getattr(event, "from_user", None)
    if user:
        DB.ensure_user(user.id, user.first_name or "", user.username or "")
    return await handler(event, data)


dp.message.outer_middleware(_user_middleware)
dp.callback_query.outer_middleware(_user_middleware)


# ------------------------------------------------------------------ helpers
def _job_dir(user_id: int) -> Path:
    d = BASE / f"{user_id}_{uuid.uuid4().hex[:8]}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _last_photo(user_id: int) -> Path:
    return USERS_DIR / str(user_id) / "last_photo.jpg"


async def _accept_photo(message: Message, state: FSMContext, downloadable, suffix=".jpg") -> None:  # noqa: ANN001
    """Любой исходник-картинка -> сохраняем и спрашиваем стиль."""
    user = message.from_user
    assert user
    last = _last_photo(user.id)
    last.parent.mkdir(parents=True, exist_ok=True)
    tmp = last.with_suffix(suffix)
    await message.bot.download(downloadable, destination=tmp)
    if suffix != ".jpg":
        from PIL import Image

        with Image.open(tmp) as img:
            img.convert("RGB").save(last, format="JPEG", quality=92)
        tmp.unlink(missing_ok=True)
    else:
        shutil.copy(tmp, last) if tmp != last else None
    await state.update_data(photo=str(last))
    await state.set_state(Flow.waiting_style)
    await message.answer("👍 Фото получил. Выбери *стиль*:", parse_mode="Markdown",
                         reply_markup=styles_kb())


def _render_local(photo: Path, style: str, effect: str, out: Path, remove_bg: bool) -> None:
    from PIL import Image

    with Image.open(photo) as img:
        subject = prepare_subject(img.copy(), style=style, remove_bg=remove_bg)
    encode_frames(
        lambda: render_frames(subject, effect, CFG.sticker_fps, CFG.sticker_duration),
        out, fps=CFG.sticker_fps, duration=CFG.sticker_duration,
    )


async def _deliver(message: Message, webm: Path, emoji: str, kind: str,
                   scenario_title: str, style_id: str) -> None:
    """Отправить готовый стикер (+в пак по настройке) и записать в историю."""
    user = message.from_user
    assert user
    settings = DB.get_settings(user.id)
    pack_url, file_id = None, None
    if settings["auto_pack"]:
        pack_url, file_id = await packs.add_to_pack(
            message.bot, user.id, user.first_name, webm, emoji)
    if file_id:
        await message.bot.send_sticker(message.chat.id, file_id)
    else:
        try:
            sent = await message.answer_sticker(FSInputFile(webm))
            file_id = sent.sticker.file_id if sent.sticker else None
        except TelegramBadRequest:
            doc = await message.answer_document(FSInputFile(webm))
            file_id = None
            log.info("стикер файлом не ушёл, отправил документом msg=%s", doc.message_id)
    DB.log_generation(user.id, kind, scenario_title, style_id, emoji, file_id)
    text = "✅ Готово!"
    if pack_url:
        text += f"\nТвой пак: {pack_url}"
    await message.answer(text, reply_markup=after_kb(pack_url))


# ------------------------------------------------------------------ генерация
async def _generate(message: Message, src_photo: Path, style_id: str,
                    scenario_id: str | None, custom_text: str | None, emoji_choice: str) -> None:
    user = message.from_user
    assert user
    style = STYLES_BY_ID[style_id]
    scenario = SCENARIOS_BY_ID[scenario_id] if scenario_id else match_scenario(custom_text or "")
    emoji = scenario.emoji if emoji_choice == "auto" else emoji_choice
    DB.set_last_job(user.id, str(src_photo), style_id, scenario_id, custom_text, emoji_choice)
    job = _job_dir(user.id)
    photo = job / "photo.jpg"
    shutil.copy(src_photo, photo)
    webm = job / "sticker.webm"
    status = await message.answer(
        f"🎬 Генерирую: {scenario.emoji} «{custom_text or scenario.title}»…\n"
        + ("🧠 Нейросеть создаёт движения персонажа по твоему сценарию.\n"
           "Бесплатная очередь: обычно 1–10 минут, не пугайся."
           if ai_enabled() else "Обычно 5–15 секунд."),
        reply_markup=generating_kb())

    progress_task: asyncio.Task | None = None
    if ai_enabled():
        async def _progress() -> None:
            started = time.monotonic()
            while True:
                await asyncio.sleep(45)
                mins = (time.monotonic() - started) / 60
                try:
                    await status.edit_text(
                        f"🧠 Нейросеть всё ещё работает… прошло {mins:.1f} мин.\n"
                        "Она рисует движения персонажа кадр за кадром.",
                        reply_markup=generating_kb())
                except Exception:
                    pass

        progress_task = asyncio.create_task(_progress())
    try:
        await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO)
        settings = DB.get_settings(user.id)
        if ai_enabled():
            prompt = build_prompt(style, scenario, custom_text)
            try:
                mp4 = job / "ai.mp4"
                await generate_ai_video(photo, prompt, mp4)
                # Стикер = вырезанная фигурка на прозрачности, а не прямоугольник:
                # вырезаем фон из сгенерированного видео покадрово.
                if progress_task:
                    progress_task.cancel()
                    progress_task = None
                try:
                    await status.edit_text("✂️ Видео готово — вырезаю фон у фигурки…")
                except TelegramBadRequest:
                    pass
                matted = await asyncio.to_thread(matte_encode, mp4, webm)
                if not matted:
                    log.warning("Вырезание фона не удалось — делаю прямоугольный стикер")
                    await asyncio.to_thread(convert_video, mp4, webm)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("AI-режим упал — откатываюсь на локальную анимацию")
                if progress_task:
                    progress_task.cancel()
                    progress_task = None
                await status.edit_text("⚠️ Нейросеть сейчас недоступна (очередь/лимит) — "
                                       "делаю обычную анимацию…")
                await asyncio.to_thread(_render_local, photo, style_id, scenario.effect,
                                        webm, CFG.remove_bg and settings["remove_bg"])
        else:
            await asyncio.to_thread(_render_local, photo, style_id, scenario.effect,
                                    webm, CFG.remove_bg and settings["remove_bg"])
        await status.delete()
        await _deliver(message, webm, emoji, "photo", custom_text or scenario.title, style_id)
    except asyncio.CancelledError:
        try:
            await status.edit_text("⏹ Генерация отменена. Пришли фото, если хочешь ещё.")
        except TelegramBadRequest:
            pass
        raise
    except Exception as e:
        log.exception("Генерация упала")
        try:
            await status.edit_text(f"😖 Не получилось: {e}\nПопробуй другое фото или сценарий.")
        except TelegramBadRequest:
            await message.answer(f"😖 Не получилось: {e}")
    finally:
        if progress_task:
            progress_task.cancel()
        shutil.rmtree(job, ignore_errors=True)
        _tasks.pop(user.id, None)


def _start_generation(message: Message, src_photo: Path, style_id: str,
                      scenario_id: str | None, custom_text: str | None,
                      emoji_choice: str) -> None:
    user = message.from_user
    assert user
    if user.id in _tasks and not _tasks[user.id].done():
        return  # вызывающий хендлер уже сказал «занято»
    task = asyncio.create_task(
        _generate(message, src_photo, style_id, scenario_id, custom_text, emoji_choice))
    _tasks[user.id] = task


def _busy(user_id: int) -> bool:
    return user_id in _tasks and not _tasks[user_id].done()


async def _start_flow(message: Message, state: FSMContext) -> None:
    await state.set_state(Flow.waiting_photo)
    await message.answer(
        "📸 Пришли *фото* — лучше, где хорошо видно лицо/фигуру.\n"
        "Можно: обычное фото, фото файлом, картинку из альбома или статичный стикер.\n"
        "А ещё я превращаю 🎞 видео/GIF в видеостикеры — просто пришли видео.",
        parse_mode="Markdown", reply_markup=main_menu())


# ------------------------------------------------------------------ команды
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    mode = ("🧠 нейро-режим включён" if ai_enabled()
            else "🆓 бесплатный локальный режим (нейросеть вырезания фона + анимация)")
    await message.answer(
        "👋 Я делаю *персональные видеостикеры* из фото.\n\n"
        "Как пользоваться:\n"
        "1️⃣ Пришли фото\n"
        "2️⃣ Выбери стиль (7 вариантов)\n"
        "3️⃣ Выбери сценарий (17 готовых) или опиши свой\n"
        "4️⃣ Укажи эмодзи — и получи стикер в своём паке 📦\n\n"
        f"Режим: {mode}\nБез оплаты и платных лимитов.",
        parse_mode="Markdown", reply_markup=main_menu())
    await _start_flow(message, state)


@dp.message(Command("new"))
@dp.message(F.text == MENU_NEW)
async def cmd_new(message: Message, state: FSMContext) -> None:
    await _start_flow(message, state)


@dp.message(Command("help"))
@dp.message(F.text == MENU_HELP)
async def cmd_help(message: Message) -> None:
    await message.answer(
        "*Что я умею*\n\n"
        "🎬 /new — видеостикер из фото: стиль → сценарий → эмодзи\n"
        "✍️ Свой сценарий — кнопка после выбора стиля\n"
        "🎞 Пришли видео/GIF (до 2 мин) — обрежу до 3 c и сделаю видеостикер\n"
        "🖼 Пришли статичный стикер — оживлю его\n"
        "📦 /pack — твой пак: открыть, переименовать, удалить последний\n"
        "🕐 /history — последние стикеры, можно переслать заново\n"
        "⚙️ /settings — вырезание фона и автодобавление в пак\n"
        "⏹ Отмена генерации — кнопка под прогрессом или /cancel\n\n"
        "Оплаты нет: пользуйся без ограничений (одна генерация за раз).",
        parse_mode="Markdown")


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    user = message.from_user
    assert user
    if _busy(user.id):
        _tasks[user.id].cancel()
    await state.clear()
    await state.set_state(Flow.waiting_photo)
    await message.answer("Ок, всё сбросил. Пришли фото 📸", reply_markup=main_menu())


@dp.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    user = message.from_user
    if not user or user.id not in CFG.admin_ids:
        return
    s = DB.stats()
    top = "\n".join(f"  • {name}: {n}" for name, n in s["top"]) or "  — пока пусто"
    await message.answer(
        f"📊 *Статистика*\nПользователей: {s['users']}\n"
        f"Генераций всего: {s['generations']} (за 24 ч: {s['today']})\n"
        f"Активных генераций: {sum(1 for t in _tasks.values() if not t.done())}\n"
        f"Топ сценариев:\n{top}", parse_mode="Markdown")


# ------------------------------------------------------------------ пак / история / настройки
async def _show_pack(message: Message) -> None:
    user = message.from_user
    assert user
    pack = await packs.get_pack(message.bot, user.id)
    if not pack:
        await message.answer("📦 У тебя пока нет пака. Сделай первый стикер — пак создастся сам!",
                             reply_markup=main_menu())
        return
    name = packs.pack_name(user.id, (await message.bot.get_me()).username or "bot")
    url = f"https://t.me/addstickers/{name}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Открыть пак", url=url),
         InlineKeyboardButton(text="🖼 Последние стикеры", callback_data="pack:show")],
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data="pack:rename"),
         InlineKeyboardButton(text="🗑 Удалить последний", callback_data="pack:del")],
    ])
    await message.answer(
        f"📦 *{pack.title}*\nСтикеров в паке: {len(pack.stickers)}\n{url}",
        parse_mode="Markdown", reply_markup=kb)


@dp.message(Command("pack"))
@dp.message(F.text == MENU_PACK)
async def cmd_pack(message: Message) -> None:
    await _show_pack(message)


@dp.message(Command("history"))
@dp.message(F.text == MENU_HISTORY)
async def cmd_history(message: Message) -> None:
    user = message.from_user
    assert user
    rows = DB.history(user.id)
    if not rows:
        await message.answer("🕐 История пуста. Сделай первый стикер!", reply_markup=main_menu())
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{r['emoji']} {r['scenario']} · {time.strftime('%d.%m %H:%M', time.localtime(r['ts']))}",
            callback_data=f"hist:{r['id']}")] for r in rows])
    await message.answer("🕐 Твои последние стикеры — нажми, чтобы прислать заново:",
                         reply_markup=kb)


@dp.message(Command("settings"))
@dp.message(F.text == MENU_SETTINGS)
async def cmd_settings(message: Message) -> None:
    user = message.from_user
    assert user
    mode = "нейро (AI)" if ai_enabled() else "локальный бесплатный"
    await message.answer(f"⚙️ *Настройки*\nРежим генерации: {mode}",
                         parse_mode="Markdown", reply_markup=settings_kb(user.id))


@dp.callback_query(F.data.startswith("set:"))
async def cb_setting(cb: CallbackQuery) -> None:
    user = cb.from_user
    key = cb.data.split(":", 1)[1]
    DB.toggle_setting(user.id, key)
    await cb.message.edit_reply_markup(reply_markup=settings_kb(user.id))
    await cb.answer("Сохранено")


@dp.callback_query(F.data == "pack:show")
async def cb_pack_show(cb: CallbackQuery) -> None:
    pack = await packs.get_pack(cb.bot, cb.from_user.id)
    if not pack or not pack.stickers:
        await cb.answer("Пак пуст", show_alert=True)
        return
    for st in pack.stickers[-5:]:
        await cb.bot.send_sticker(cb.message.chat.id, st.file_id)
    await cb.answer()


@dp.callback_query(F.data == "pack:rename")
async def cb_pack_rename(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Flow.waiting_pack_title)
    await cb.message.answer("✏️ Пришли новое название пака (до 64 символов):")
    await cb.answer()


@dp.message(Flow.waiting_pack_title, F.text)
async def on_pack_title(message: Message, state: FSMContext) -> None:
    await state.set_state(Flow.waiting_photo)
    ok = await packs.rename_pack(message.bot, message.from_user.id, message.text or "")  # type: ignore[union-attr]
    await message.answer("✅ Пак переименован." if ok else "😖 Не вышло — возможно, пака ещё нет.")


@dp.callback_query(F.data == "pack:del")
async def cb_pack_del(cb: CallbackQuery) -> None:
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗑 Да, удалить последний", callback_data="pack:del_yes"),
        InlineKeyboardButton(text="Отмена", callback_data="pack:del_no")]])
    await cb.message.answer("Удалить последний стикер из пака?", reply_markup=kb)
    await cb.answer()


@dp.callback_query(F.data == "pack:del_no")
async def cb_pack_del_no(cb: CallbackQuery) -> None:
    await cb.message.delete()
    await cb.answer()


@dp.callback_query(F.data == "pack:del_yes")
async def cb_pack_del_yes(cb: CallbackQuery) -> None:
    ok = await packs.delete_last_sticker(cb.bot, cb.from_user.id)
    await cb.message.edit_text("🗑 Последний стикер удалён." if ok else "Пак уже пуст.")
    await cb.answer()


@dp.callback_query(F.data.startswith("hist:"))
async def cb_history(cb: CallbackQuery) -> None:
    row = DB.get_generation(int(cb.data.split(":", 1)[1]), cb.from_user.id)
    if row and row["file_id"]:
        await cb.bot.send_sticker(cb.message.chat.id, row["file_id"])
        await cb.answer()
    else:
        await cb.answer("Этот стикер уже недоступен", show_alert=True)


@dp.callback_query(F.data == "nav:history")
async def cb_nav_history(cb: CallbackQuery) -> None:
    kb = _history_kb(cb.from_user.id)
    if kb is None:
        await cb.answer("История пуста", show_alert=True)
        return
    await cb.message.answer("🕐 Твои последние стикеры — нажми, чтобы прислать заново:",
                            reply_markup=kb)
    await cb.answer()


# ------------------------------------------------------------------ флоу стикера
@dp.callback_query(F.data == "cancel")
async def cb_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Flow.waiting_photo)
    await cb.message.edit_text("Ок, сбросил. Пришли фото 📸")
    await cb.answer()


@dp.message(Flow.waiting_photo, F.photo)
@dp.message(F.photo)
async def on_photo(message: Message, state: FSMContext) -> None:
    if message.media_group_id:  # альбом: обрабатываем только первое фото
        now = time.time()
        _seen_albums.update({k: v for k, v in _seen_albums.items() if now - v < 60})
        if message.media_group_id in _seen_albums:
            return
        _seen_albums[message.media_group_id] = now
        await message.answer("📸 Альбом получил — беру первое фото.")
    await _accept_photo(message, state, message.photo[-1])


@dp.message(F.sticker)
async def on_sticker_in(message: Message, state: FSMContext) -> None:
    st = message.sticker
    assert st
    user = message.from_user
    assert user
    if st.is_animated:
        await message.answer("Этот стикер анимированный (TGS) — его оживить не могу, "
                             "но могу сделать видеостикер из фото или видео.")
        return
    if st.is_video:  # готовый видеостикер -> просто в твой пак
        job = _job_dir(user.id)
        src = job / "in.webm"
        await message.bot.download(st, destination=src)
        try:
            await _deliver(message, src, st.emoji or "🎬", "sticker", "видеостикер", "original")
        finally:
            shutil.rmtree(job, ignore_errors=True)
        return
    await message.answer("🖼 Оживляю твой стикер…")
    await _accept_photo(message, state, st, suffix=".webp")


@dp.callback_query(Flow.waiting_style, F.data.startswith("style:"))
async def on_style(cb: CallbackQuery, state: FSMContext) -> None:
    style_id = cb.data.split(":", 1)[1]
    if style_id not in STYLES_BY_ID:
        await cb.answer("Такого стиля нет", show_alert=True)
        return
    await state.update_data(style=style_id)
    await state.set_state(Flow.waiting_scenario)
    await cb.message.edit_text(
        f"Стиль: {STYLES_BY_ID[style_id].emoji} {STYLES_BY_ID[style_id].title}\n"
        "Теперь выбери *сценарий* или опиши свой:", parse_mode="Markdown",
        reply_markup=scenarios_kb())
    await cb.answer()


@dp.callback_query(F.data == "back:scenarios")
async def cb_back_scenarios(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Flow.waiting_scenario)
    await cb.message.edit_text("Выбери *сценарий* или опиши свой:", parse_mode="Markdown",
                               reply_markup=scenarios_kb())
    await cb.answer()


@dp.callback_query(Flow.waiting_scenario, F.data == "scen:custom")
async def on_custom(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Flow.waiting_custom_text)
    await cb.message.edit_text(
        "✍️ Опиши сценарий одним предложением, например:\n"
        "«лечу на ракете», «открываю холодильник-портал», «дирижирую оркестром котов»\n\n"
        + ("🧠 Нейросеть выполнит его буквально." if ai_enabled() else
           "Подберу ближайший эффект по ключевым словам."))
    await cb.answer()


async def _ask_emoji(cb_or_msg, state: FSMContext) -> None:  # noqa: ANN001
    data = await state.get_data()
    scenario = (SCENARIOS_BY_ID.get(data.get("scenario_id") or "")
                or match_scenario(data.get("custom_text") or ""))
    await state.set_state(Flow.waiting_emoji)
    text = "😀 Какой эмодзи привязать к стикеру? (по нему стикер ищется в Telegram)"
    if isinstance(cb_or_msg, CallbackQuery):
        await cb_or_msg.message.edit_text(text, reply_markup=emoji_kb(scenario.emoji))
        await cb_or_msg.answer()
    else:
        await cb_or_msg.answer(text, reply_markup=emoji_kb(scenario.emoji))


@dp.callback_query(Flow.waiting_scenario, F.data.startswith("scen:"))
async def on_scenario(cb: CallbackQuery, state: FSMContext) -> None:
    sid = cb.data.split(":", 1)[1]
    if sid not in SCENARIOS_BY_ID:
        await cb.answer("Такого сценария нет", show_alert=True)
        return
    await state.update_data(scenario_id=sid, custom_text=None)
    await _ask_emoji(cb, state)


@dp.message(Flow.waiting_custom_text, F.text)
async def on_custom_text(message: Message, state: FSMContext) -> None:
    await state.update_data(scenario_id=None, custom_text=(message.text or "")[:300])
    await _ask_emoji(message, state)


@dp.callback_query(Flow.waiting_emoji, F.data.startswith("emoji:"))
async def on_emoji(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    user = cb.from_user
    await state.clear()
    await state.set_state(Flow.waiting_photo)
    if _busy(user.id):
        await cb.answer("⏳ Уже генерирую предыдущий стикер…", show_alert=True)
        return
    await cb.answer("Генерирую…")
    _start_generation(cb.message, Path(data["photo"]), data.get("style", "original"),
                      data.get("scenario_id"), data.get("custom_text"),
                      cb.data.split(":", 1)[1])


# ------------------------------------------------------------------ повтор
@dp.callback_query(F.data.startswith("again:"))
async def cb_again(cb: CallbackQuery, state: FSMContext) -> None:
    user = cb.from_user
    last = DB.get_last_job(user.id)
    if not last or not Path(last["photo"]).exists():
        await cb.answer("Фото не сохранилось — пришли новое", show_alert=True)
        return
    action = cb.data.split(":", 1)[1]
    if action == "repeat":
        if _busy(user.id):
            await cb.answer("⏳ Уже генерирую…", show_alert=True)
            return
        await cb.answer("Повторяю…")
        _start_generation(cb.message, Path(last["photo"]), last["style"] or "original",
                          last["scenario_id"], last["custom_text"], last["emoji"] or "auto")
    elif action == "scenario":
        await state.update_data(photo=last["photo"], style=last["style"] or "original")
        await state.set_state(Flow.waiting_scenario)
        await cb.message.answer("🎲 Выбери другой сценарий для этого же фото:",
                                reply_markup=scenarios_kb())
        await cb.answer()
    elif action == "style":
        await state.update_data(photo=last["photo"])
        await state.set_state(Flow.waiting_style)
        await cb.message.answer("🎨 Выбери стиль:", reply_markup=styles_kb())
        await cb.answer()


@dp.callback_query(F.data == "gen:cancel")
async def cb_gen_cancel(cb: CallbackQuery) -> None:
    task = _tasks.get(cb.from_user.id)
    if task and not task.done():
        task.cancel()
        await cb.answer("Отменяю…")
    else:
        await cb.answer("Сейчас ничего не генерируется")


# ------------------------------------------------------------------ видео -> стикер
@dp.message(F.video | F.animation | F.document)
async def on_video(message: Message, state: FSMContext) -> None:
    media = message.video or message.animation or message.document
    user = message.from_user
    if not media or not user:
        return
    mime = getattr(media, "mime_type", "") or ""
    if message.document and mime.startswith("image/"):  # фото файлом без сжатия
        await _accept_photo(message, state, media,
                            suffix=".png" if mime == "image/png" else ".jpg")
        return
    if message.document and not mime.startswith(("video/", "image/gif")):
        await message.answer("Это не видео. Пришли 📸 фото или 🎞 видео/GIF.")
        return
    if _busy(user.id):
        await message.answer("⏳ Дождись текущей генерации (или /cancel).")
        return
    duration = getattr(media, "duration", None)
    job = _job_dir(user.id)
    src, webm = job / "input.mp4", job / "sticker.webm"
    status = await message.answer(
        "🎞 Конвертирую в видеостикер…" + (f"\nОбрежу первые 3 секунды из {duration} c."
                                          if duration and duration > 3 else ""),
        reply_markup=generating_kb())

    async def _convert() -> None:
        try:
            await message.bot.download(media, destination=src)
            await asyncio.to_thread(convert_video, src, webm)
            await status.delete()
            await _deliver(message, webm, "🎬", "video", "из видео", "original")
        except asyncio.CancelledError:
            try:
                await status.edit_text("⏹ Конверсия отменена.")
            except TelegramBadRequest:
                pass
            raise
        except Exception as e:
            log.exception("Конверсия видео упала")
            try:
                await status.edit_text(f"😖 Не получилось: {e}")
            except TelegramBadRequest:
                pass
        finally:
            shutil.rmtree(job, ignore_errors=True)
            _tasks.pop(user.id, None)

    _tasks[user.id] = asyncio.create_task(_convert())


@dp.message()
async def fallback(message: Message) -> None:
    await message.answer("Пришли 📸 фото — сделаю видеостикер, или 🎞 видео/GIF.\n"
                         "Команды: /new /pack /history /settings /help",
                         reply_markup=main_menu())


# ------------------------------------------------------------------ запуск
async def _on_startup(bot: Bot) -> None:
    try:
        await _setup_commands(bot)
    except Exception:  # сеть моргнула на старте — поллинг сам переподключится
        log.exception("Не удалось настроить команды при старте (не критично)")


async def _setup_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="new", description="🎬 Сделать видеостикер из фото"),
        BotCommand(command="pack", description="📦 Мой стикерпак"),
        BotCommand(command="history", description="🕐 История стикеров"),
        BotCommand(command="settings", description="⚙️ Настройки"),
        BotCommand(command="help", description="ℹ️ Помощь"),
        BotCommand(command="cancel", description="⏹ Сбросить / отменить"),
    ])
    me = await bot.get_me()
    log.info("Бот @%s запущен. AI=%s, юзеров в БД: %s",
             me.username, ai_enabled(), DB.stats()["users"])


async def _polling_supervisor() -> None:
    """Поллинг с автопереподключением: сеть моргнула — бот не умирает, а ждёт и снова.

    (Голый start_polling падает на самом первом getMe, если Telegram в этот
    момент недоступен, — для контейнера 24/7 это недопустимо.)
    """
    while True:
        bot = Bot(CFG.token)
        try:
            await dp.start_polling(bot)
            return  # штатная остановка поллинга
        except asyncio.CancelledError:
            raise
        except TelegramUnauthorizedError:
            # Токен невалиден/отозван — ретраить бессмысленно, падаем громко и сразу
            log.critical("Telegram отклонил токен (Unauthorized). Проверь BOT_TOKEN.")
            raise SystemExit(2) from None
        except Exception:
            log.exception("Поллинг упал — перезапуск через 10 секунд")
            await asyncio.sleep(10)
        finally:
            try:
                await bot.session.close()
            except Exception:
                pass


async def _amain() -> None:
    """PORT задан (Cloudflare Containers/PaaS) — рядом с поллингом живёт healthcheck.

    Контейнеру нужен слушающий порт, иначе платформа его не поднимет/усыпит.
    Health отвечает, даже пока Telegram временно недоступен.
    """
    dp.startup.register(_on_startup)
    if not os.getenv("PORT"):
        await _polling_supervisor()
        return
    from aiohttp import web

    async def health(_request):  # noqa: ANN001, ANN202
        return web.json_response({"ok": True, "service": "deepstick-bot"})

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ["PORT"])).start()
    log.info("Healthcheck слушает порт %s", os.environ["PORT"])
    poll_task = asyncio.create_task(_polling_supervisor())
    try:
        await asyncio.Event().wait()  # держим процесс (и health) живым всегда
    finally:
        poll_task.cancel()
        await runner.cleanup()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
