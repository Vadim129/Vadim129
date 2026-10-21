#!/usr/bin/env python3
"""Клон @DeepStickBot (все функции, кроме оплаты): фото -> стиль -> сценарий ->
эмодзи -> видеостикер в личном паке пользователя.

Возможности:
  * фото (обычное, файлом, альбомом), стикер и видео/GIF как исходник;
  * 17 сценариев, 7 стилей, свой сценарий текстом, выбор эмодзи стикера;
  * стикерпаки: основной личный + именные — создать пак, добавить стикер
    в любой пак, удалить отдельный стикер из пака, переименовать, удалить пак;
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
from aiogram.exceptions import (  # noqa: E402
    TelegramBadRequest,
    TelegramRetryAfter,
    TelegramUnauthorizedError,
)
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
    User,
)

from app import packs  # noqa: E402
from app.ai_video import ai_enabled, generate_ai_video  # noqa: E402
from app.comfy import build_notebook, comfy_generate, extract_tunnel  # noqa: E402
import httpx  # noqa: E402
from app.db import Database  # noqa: E402
from app.effects import prepare_subject, render_frames  # noqa: E402
from app.encode import convert_video, encode_frames  # noqa: E402
from app.matting import matte_encode  # noqa: E402
from app.scenarios import (  # noqa: E402
    CATEGORIES,
    SCENARIOS,
    scenario_for_emoji,
    scenarios_in,
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


def _is_admin(user_id: int) -> bool:
    """Владелец бота: из ADMIN_IDS или первый пользователь (личный бот)."""
    return user_id in CFG.admin_ids or DB.first_user_id() == user_id


_AI_SCOPES = ("all", "owner", "off")


def _ai_scope() -> str:
    """Охват нейросети: all — всем, owner — только владельцу, off — никому."""
    scope = DB.get_global("ai_scope", "")
    if scope in _AI_SCOPES:
        return scope
    return "off" if DB.get_global("ai_enabled", "1") == "0" else "all"  # legacy


def _scope_allows(user_id: int | None) -> bool:
    """Разрешает ли нейросеть этому юзеру: охват + индивидуальный список.

    all — всем; owner — владельцу и пользователям из индивидуального
    списка (кнопка «👥 Доступ к нейросети» в настройках); off — никому.
    """
    scope = _ai_scope()
    if scope == "off":
        return False
    if scope == "all":
        return True
    if user_id is None:
        return False
    return _is_admin(user_id) or DB.is_ai_allowed(user_id)


def _ai_on(user_id: int | None = None) -> bool:
    """Нейросеть доступна этому пользователю прямо сейчас."""
    return ai_enabled() and _scope_allows(user_id)


# ------------------------------------------------- Kaggle-ComfyUI (Wan 2.2)
COMFY_TTL = 11.5 * 3600  # сессия Kaggle живёт максимум 12 часов
_comfy_health = {"ok": False, "checked": 0.0}


def _comfy_url() -> str | None:
    """Адрес живого (по возрасту) ComfyUI-туннеля или None."""
    url = DB.get_global("comfy_url", "")
    try:
        ts = float(DB.get_global("comfy_ts", "0") or 0)
    except ValueError:
        ts = 0.0
    return url if url and time.time() - ts < COMFY_TTL else None


async def _comfy_alive() -> bool:
    """Жив ли ComfyUI прямо сейчас (проверка с кэшем на минуту)."""
    url = _comfy_url()
    if not url:
        return False
    now = time.monotonic()
    if now - _comfy_health["checked"] < 60:
        return _comfy_health["ok"]
    ok = False
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0)) as client:
            ok = (await client.get(f"{url}/system_stats")).status_code == 200
    except Exception:
        ok = False
    _comfy_health.update(ok=ok, checked=now)
    if not ok:
        DB.set_global("comfy_url", "")
    return ok


def _comfy_status_text() -> str:
    if not (CFG.kaggle_username and CFG.kaggle_key):
        return "нужны секреты Kaggle"
    return "🟢 онлайн" if _comfy_url() else "⚪ выключена"


def _neuro_advertised(user_id: int | None) -> bool:
    """Показывать ли юзеру нейро-режим: HF задан или Kaggle онлайн."""
    return _scope_allows(user_id) and (ai_enabled() or bool(_comfy_url()))
DB = Database(CFG.data_dir / "bot.db")
dp = Dispatcher()
BASE = Path(tempfile.gettempdir()) / "deepstick_jobs"
BASE.mkdir(parents=True, exist_ok=True)
USERS_DIR = CFG.data_dir / "users"

_tasks: dict[int, asyncio.Task] = {}       # одна активная генерация на юзера
_seen_albums: dict[str, float] = {}        # media_group_id -> когда видели

MENU_START = "▶️ Старт"
MENU_NEW = "🎬 Сделать стикер"
MENU_PACK = "📦 Стикерпаки"
MENU_HISTORY = "🕐 История"
MENU_SETTINGS = "⚙️ Настройки"
MENU_HELP = "ℹ️ Помощь"
MENU_REVIVE = "🎬 Оживить набор"

EMOJIS = ["😂", "😍", "😮", "🔥", "😎", "🤬", "🥺", "👍",
          "💃", "🚀", "😴", "🏆", "💸", "😭", "🤪"]


class Flow(StatesGroup):
    waiting_photo = State()
    waiting_style = State()
    waiting_scenario = State()
    waiting_custom_text = State()
    waiting_emoji = State()
    waiting_pack_title = State()
    waiting_new_pack_title = State()
    waiting_revive_pack = State()
    waiting_revive_custom = State()
    waiting_ai_user = State()


# ------------------------------------------------------------------ клавиатуры
def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_START)],
            [KeyboardButton(text=MENU_NEW)],
            [KeyboardButton(text=MENU_PACK), KeyboardButton(text=MENU_HISTORY)],
            [KeyboardButton(text=MENU_REVIVE)],
            [KeyboardButton(text=MENU_SETTINGS), KeyboardButton(text=MENU_HELP)],
        ], resize_keyboard=True)


def styles_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{s.emoji} {s.title}", callback_data=f"style:{s.id}")]
            for s in STYLES]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _cat_kb(prefix: str, cat_prefix: str, item_prefix: str) -> InlineKeyboardMarkup:
    """Корень выбора сценария: кнопки категорий с числом сценариев."""
    rows, row = [], []
    for cid, title in CATEGORIES:
        row.append(InlineKeyboardButton(
            text=f"{title} · {len(scenarios_in(cid))}", callback_data=f"{cat_prefix}{cid}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✍️ Свой сценарий (текстом)",
                                      callback_data=f"{item_prefix}custom")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _scen_kb(items, item_prefix: str, cat_prefix: str) -> InlineKeyboardMarkup:
    rows, row = [], []
    for sc in items:
        row.append(InlineKeyboardButton(text=f"{sc.emoji} {sc.title}",
                                        callback_data=f"{item_prefix}{sc.id}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Категории", callback_data=f"{cat_prefix}root")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def scenarios_kb(category: str | None = None) -> InlineKeyboardMarkup:
    if category is None:
        return _cat_kb("scen", "scencat:", "scen:")
    return _scen_kb(scenarios_in(category), "scen:", "scencat:")


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


def after_kb(pack_url: str | None, gen_id: int | None = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔁 Повторить", callback_data="again:repeat"),
         InlineKeyboardButton(text="🎲 Другой сценарий", callback_data="again:scenario")],
        [InlineKeyboardButton(text="🎨 Сменить стиль", callback_data="again:style"),
         InlineKeyboardButton(text="🕐 История", callback_data="nav:history")],
    ]
    if gen_id:
        rows.append([InlineKeyboardButton(text="➕ Добавить этот стикер в пак",
                                          callback_data=f"addto:{gen_id}")])
    if pack_url:
        rows.append([InlineKeyboardButton(text="📦 Открыть мой пак", url=pack_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _active_title(user_id: int) -> str:
    target = DB.get_settings(user_id)["active_pack"]
    if target == "main":
        return "Основной"
    rec = DB.get_pack_rec(user_id, int(target)) if target.isdigit() else None
    return rec["title"] if rec else "Основной"


def settings_kb(user_id: int) -> InlineKeyboardMarkup:
    s = DB.get_settings(user_id)
    mark = {True: "✅ вкл", False: "❌ выкл"}
    rows = []
    if _is_admin(user_id):  # охват нейросети настраивает только владелец
        scope_label = {"all": "✅ для всех", "owner": "👤 только я + список",
                       "off": "❌ выключена"}[_ai_scope()]
        rows.append([InlineKeyboardButton(
            text=f"🧠 Нейросеть: {scope_label}", callback_data="adm:aiscope")])
        rows.append([InlineKeyboardButton(
            text=f"☁️ Kaggle-нейросеть: {_comfy_status_text()}",
            callback_data="kg:open")])
        rows.append([InlineKeyboardButton(
            text=f"👥 Доступ к нейросети: разрешено {len(DB.ai_allowed_ids())}",
            callback_data="aiu:list:0")])
        rows.append([InlineKeyboardButton(
            text="📊 Пользователи и статистика", callback_data="stats:open")])
    rows += [
        [InlineKeyboardButton(text=f"🎯 Пак для новых стикеров: {_active_title(user_id)}",
                              callback_data="pk:list")],
        [InlineKeyboardButton(text=f"✂️ Вырезать фон: {mark[s['remove_bg']]}",
                              callback_data="set:remove_bg")],
        [InlineKeyboardButton(text=f"📦 Добавлять в пак: {mark[s['auto_pack']]}",
                              callback_data="set:auto_pack")],
        [InlineKeyboardButton(text="✏️ Переименовать пак", callback_data="pack:rename")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


async def _deliver(message: Message, user: User, webm: Path, emoji: str, kind: str,
                   scenario_title: str, style_id: str) -> None:
    """Отправить готовый стикер (+в пак по настройке) и записать в историю.

    user передаётся явно: message может быть сообщением самого бота (когда
    генерацию запустили кнопкой), и message.from_user тогда — бот (USER_IS_BOT).
    """
    settings = DB.get_settings(user.id)
    pack_url, file_id, pack_err = None, None, None
    if settings["auto_pack"]:
        target = settings["active_pack"]
        rec = (DB.get_pack_rec(user.id, int(target))
               if target != "main" and target.isdigit() else None)
        if target != "main" and rec is not None:
            # именной текущий пак: добавляем в него; если пак удалили в
            # Telegram — add_to_named_pack честно вернёт ошибку
            pack_url, file_id, pack_err = await packs.add_to_named_pack(
                message.bot, user.id, rec["name"], webm, emoji)
        else:
            if target != "main":  # запись пака пропала — откатываемся на основной
                DB.set_active_pack(user.id, "main")
            pack_url, file_id, pack_err = await packs.add_to_pack(
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
    gen_id = DB.log_generation(user.id, kind, scenario_title, style_id, emoji, file_id)
    text = "✅ Готово!"
    if pack_url:
        text += f"\nТвой пак: {pack_url}"
    elif pack_err:
        text += ("\n⚠️ Стикер сделал, но в пак не добавился. "
                 f"Причина Telegram: {pack_err}\n"
                 "Попробуй 📦 Стикерпаки → стикер можно добавить вручную кнопкой ниже.")
    await message.answer(text, reply_markup=after_kb(pack_url, gen_id if file_id else None))


# ------------------------------------------------------------------ генерация
async def _generate(message: Message, user: User, src_photo: Path, style_id: str,
                    scenario_id: str | None, custom_text: str | None, emoji_choice: str) -> None:
    style = STYLES_BY_ID[style_id]
    scenario = SCENARIOS_BY_ID[scenario_id] if scenario_id else match_scenario(custom_text or "")
    emoji = scenario.emoji if emoji_choice == "auto" else emoji_choice
    DB.set_last_job(user.id, str(src_photo), style_id, scenario_id, custom_text, emoji_choice)
    job = _job_dir(user.id)
    photo = job / "photo.jpg"
    shutil.copy(src_photo, photo)
    webm = job / "sticker.webm"
    neuro = _ai_on(user.id) or (await _comfy_alive() and _scope_allows(user.id))
    status = await message.answer(
        f"🎬 Генерирую: {scenario.emoji} «{custom_text or scenario.title}»…\n"
        + ("🧠 Нейросеть создаёт движения персонажа по твоему сценарию.\n"
           "Бесплатная очередь: обычно 1–10 минут, не пугайся."
           if neuro else "Обычно 5–15 секунд."),
        reply_markup=generating_kb())

    progress_task: asyncio.Task | None = None
    if neuro:
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
        if neuro:
            prompt = build_prompt(style, scenario, custom_text)
            try:
                mp4 = job / "ai.mp4"
                await _neuro_video_q(photo, prompt, mp4, user.id)
                # Стикер = вырезанная фигурка на прозрачности, а не прямоугольник:
                # вырезаем фон из сгенерированного видео покадрово.
                if progress_task:
                    progress_task.cancel()
                    progress_task = None
                try:
                    await status.edit_text("✂️ Видео готово — вырезаю фон у фигурки…")
                except TelegramBadRequest:
                    pass
                matted = await _matte_q(mp4, webm)
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
                await _render_local_q(photo, style_id, scenario.effect,
                                      webm, CFG.remove_bg and settings["remove_bg"])
        else:
            await _render_local_q(photo, style_id, scenario.effect,
                                  webm, CFG.remove_bg and settings["remove_bg"])
        await status.delete()
        await _deliver(message, user, webm, emoji, "photo", custom_text or scenario.title, style_id)
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


def _start_generation(message: Message, user: User, src_photo: Path, style_id: str,
                      scenario_id: str | None, custom_text: str | None,
                      emoji_choice: str) -> None:
    if user.id in _tasks and not _tasks[user.id].done():
        return  # вызывающий хендлер уже сказал «занято»
    task = asyncio.create_task(
        _generate(message, user, src_photo, style_id, scenario_id, custom_text, emoji_choice))
    _tasks[user.id] = task


# Локальный рендер (rembg + VP9) тяжёлый по CPU/RAM — не более 3 параллельно,
# остальные задачи честно ждут в очереди, а не убивают процесс по OOM.
# Нейро-генерация — это ожидание внешней очереди, ей отдельный лимит.
_RENDER_SEM = asyncio.Semaphore(3)
_AI_SEM = asyncio.Semaphore(4)


async def _render_local_q(*args) -> None:
    async with _RENDER_SEM:
        await asyncio.to_thread(_render_local, *args)


async def _matte_q(mp4: Path, webm: Path) -> bool:
    async with _RENDER_SEM:
        return await asyncio.to_thread(matte_encode, mp4, webm)


async def _neuro_video_q(photo: Path, prompt: str, out: Path, user_id: int) -> None:
    """Нейрогенерация видео: живой Kaggle-ComfyUI первым, дальше HF-цепочка."""
    async with _AI_SEM:
        url = _comfy_url()
        if url and _scope_allows(user_id):
            try:
                await comfy_generate(url, photo, prompt, out)
                return
            except Exception:
                log.warning("ComfyUI не справился — пробую HF-цепочку",
                            exc_info=True)
                DB.set_global("comfy_url", "")
        await generate_ai_video(photo, prompt, out)


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
@dp.message(F.text == MENU_START)
async def menu_start(message: Message, state: FSMContext) -> None:
    await cmd_start(message, state)


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else 0
    if not ai_enabled():
        mode = "🆓 бесплатный локальный режим (нейросеть вырезания фона + анимация)"
    elif _ai_on(uid):
        mode = "🧠 нейро-режим включён"
    elif _scope_allows(uid) and _comfy_url():
        mode = "🧠 нейро-режим включён (Kaggle ComfyUI)"
    elif _ai_scope() == "owner":
        mode = "🆓 локальный режим (нейросеть — у владельца и разрешённых им)"
    else:
        mode = "🆓 локальный режим (нейросеть временно отключена владельцем)"
    await message.answer(
        "👋 Я делаю *персональные видеостикеры* из фото.\n\n"
        "Как пользоваться:\n"
        "1️⃣ Пришли фото\n"
        "2️⃣ Выбери стиль (7 вариантов)\n"
        "3️⃣ Выбери сценарий (" + str(len(SCENARIOS)) + " готовых) или опиши свой\n"
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
        "📦 /pack — стикерпаки: создать свой пак, добавлять в него стикеры, "
        "удалять отдельные стикеры и пак целиком\n"
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


async def _quota_line() -> str:
    """Остаток бесплатной ZeroGPU-квоты HF (для админа): секунды и время сброса."""
    if not os.getenv("HF_TOKEN"):
        extra = [t.strip() for t in os.getenv("HF_TOKENS", "").split(",") if t.strip()]
        if not extra:
            return ""
        os.environ["HF_TOKEN"] = extra[0]  # get_zero_gpu_quota читает токен из окружения
    try:
        from huggingface_hub import get_zero_gpu_quota  # type: ignore

        q = await asyncio.to_thread(get_zero_gpu_quota)  # HF_TOKEN из окружения
        reset = q.resets_at.strftime("%d.%m %H:%M UTC") if getattr(q, "resets_at", None) else "?"
        return (f"\n🧠 ZeroGPU: осталось {getattr(q, 'remaining', '?')} c "
                f"из {getattr(q, 'base', '?')}, сброс: {reset}")
    except Exception:
        return ""


@dp.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    user = message.from_user
    if not user or not _is_admin(user.id):
        return
    await message.answer(_stats_text() + await _quota_line(),
                         reply_markup=_stats_kb())


# ------------------------------------------------------------------ пак / история / настройки
def _packs_list_kb(user_id: int) -> InlineKeyboardMarkup:
    active = DB.get_settings(user_id)["active_pack"]

    def mark(t: str) -> str:
        return "🎯" if active == t else "📦"

    rows = [[InlineKeyboardButton(text=f"{mark('main')} Основной пак", callback_data="pk:main")]]
    for rec in DB.list_packs(user_id):
        rows.append([InlineKeyboardButton(text=f"{mark(str(rec['id']))} {rec['title']}"[:60],
                                           callback_data=f"pk:{rec['id']}")])
    rows.append([InlineKeyboardButton(text="➕ Создать пак", callback_data="pk:new")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _resolve_pack(bot: Bot, user_id: int, target: str):  # noqa: ANN202
    """target: 'main' или id записи -> (имя пака в Telegram, запись БД|None)."""
    if target == "main":
        me = await bot.get_me()
        return packs.pack_name(user_id, me.username or "bot"), None
    rec = DB.get_pack_rec(user_id, int(target))
    return (rec["name"], rec) if rec else (None, None)


def _pack_card_kb(target: str, url: str, custom: bool, is_active: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🔗 Открыть пак", url=url)]]
    if not is_active:
        rows.append([InlineKeyboardButton(text="🎯 Сюда новые стикеры",
                                          callback_data=f"pkact:{target}")])
    rows.append([InlineKeyboardButton(text="🎬 Сделать стикер в этот пак",
                                      callback_data=f"pkmk:{target}")])
    rows.append([InlineKeyboardButton(text="🖼 Стикеры пака (и удаление)",
                                      callback_data=f"pkv:{target}:0"),
                 InlineKeyboardButton(text="➕ Добавить из истории",
                                      callback_data=f"pkadd:{target}")])
    rows.append([InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"pkr:{target}")])
    if custom:
        rows.append([InlineKeyboardButton(text="🗑 Удалить пак целиком",
                                          callback_data=f"pkd:{target}")])
    rows.append([InlineKeyboardButton(text="⬅️ Все паки", callback_data="pk:list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_pack(message: Message) -> None:
    user = message.from_user
    assert user
    await message.answer(
        "📦 *Твои стикерпаки*\n🎯 — пак, в который падают *новые* стикеры.\n"
        "Нажми на пак: внутри — сделать стикер прямо в него, добавить из истории, "
        "удалить лишние, переименовать или удалить пак.",
        parse_mode="Markdown", reply_markup=_packs_list_kb(user.id))


@dp.message(Command("pack"))
@dp.message(F.text == MENU_PACK)
async def cmd_pack(message: Message) -> None:
    await _show_pack(message)


def _sample_webm(path: Path, color: tuple[int, int, int]) -> Path:
    """Крошечный тестовый видеостикер для самопроверки паков."""
    from PIL import Image, ImageDraw

    def frames():
        for i in range(10):
            img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse([90 + i * 22, 150, 290 + i * 22, 350], fill=color + (255,))
            yield img

    encode_frames(frames, path, fps=10, duration=1.0)
    return path


@dp.message(Command("packtest"))
async def cmd_packtest(message: Message) -> None:
    """Самопроверка паков на живом Telegram: создать/добавить/удалить/удалить пак.

    Всё делается на тестовом паке и откатывается; личный пак проверяется
    добавлением тестового стикера с последующим удалением именно его.
    """
    user = message.from_user
    assert user
    bot = message.bot
    lines = ["🧪 *Проверка стикерпаков*"]
    job = _job_dir(user.id)
    try:
        w1 = await asyncio.to_thread(_sample_webm, job / "t1.webm", (220, 60, 60))
        w2 = await asyncio.to_thread(_sample_webm, job / "t2.webm", (60, 160, 60))
        me = await bot.get_me()
        name = f"dstest{uuid.uuid4().hex[:8]}_by_{(me.username or 'bot').lower()}"

        async def step(label: str, coro) -> bool:  # noqa: ANN001, ANN202
            ok, err = await coro
            lines.append(("✅ " if ok else "❌ ") + label
                         + ("" if ok else f"\n   Telegram: {err}"))
            return ok

        if await step("Создание пака",
                      packs.create_pack_webm(bot, user.id, name,
                                             "🧪 DeepStick test", w1, "🧪")):
            pack = await packs.get_pack_by_name(bot, name)
            lines.append(f"ℹ️ Стикеров после создания: {len(pack.stickers) if pack else '—'}")
            await step("Добавление стикера файлом",
                       packs.add_webm_to_pack(bot, user.id, name, w2, "🔥"))
            pack = await packs.get_pack_by_name(bot, name)
            if pack and pack.stickers:
                await step("Удаление отдельного стикера",
                           packs.delete_sticker(bot, pack.stickers[0].file_id))
            await step("Переименование пака",
                       packs.rename_pack_by_name(bot, name, "🧪 DeepStick renamed"))
            await step("Удаление пака целиком", packs.delete_pack(bot, name))

        main_name = packs.pack_name(user.id, me.username or "bot")
        before = await packs.get_pack_by_name(bot, main_name)
        before_n = len(before.stickers) if before else 0
        url, _fid, err = await packs.add_to_pack(bot, user.id, user.first_name, w1, "🧪")
        after = await packs.get_pack_by_name(bot, main_name)
        after_n = len(after.stickers) if after else 0
        ok_main = bool(url) and after_n == before_n + 1
        lines.append(("✅ " if ok_main else "❌ ")
                     + f"Личный пак (добавление): стикеров {before_n} → {after_n}"
                     + ("" if ok_main else f"\n   Telegram: {err}"))
        if after and after_n > before_n:  # откатываем только свой тестовый стикер
            if before is None:
                await packs.delete_pack(bot, main_name)
            else:
                await packs.delete_sticker(bot, after.stickers[-1].file_id)
            lines.append("ℹ️ Тестовый стикер из личного пака убрал за собой")
    except Exception as e:
        log.exception("packtest упал")
        lines.append(f"❌ Проверка упала: {e}")
    finally:
        shutil.rmtree(job, ignore_errors=True)
    await message.answer("\n".join(lines))


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
    if not ai_enabled():
        mode = "локальный бесплатный"
    elif _ai_on(user.id):
        mode = "нейро (AI)"
    elif _scope_allows(user.id) and _comfy_url():
        mode = "нейро (Kaggle ComfyUI)"
    elif _ai_scope() == "owner":
        mode = "локальный (нейросеть у владельца и разрешённых им)"
    else:
        mode = "локальный (нейросеть отключена владельцем)"
    await message.answer(f"⚙️ *Настройки*\nРежим генерации: {mode}",
                         parse_mode="Markdown", reply_markup=settings_kb(user.id))


_AI_SCOPE_TEXT = {
    "all": "🧠 Нейросеть включена для всех пользователей",
    "owner": "👤 Нейросеть: только ты и пользователи из списка «👥 Доступ к нейросети», у остальных — локальная анимация",
    "off": "🔕 Нейросеть выключена для всех: локальная анимация",
}


@dp.callback_query(F.data == "adm:aiscope")
async def cb_admin_aiscope(cb: CallbackQuery) -> None:
    if not _is_admin(cb.from_user.id):
        await cb.answer("Это настройка владельца бота", show_alert=True)
        return
    nxt = _AI_SCOPES[(_AI_SCOPES.index(_ai_scope()) + 1) % len(_AI_SCOPES)]
    DB.set_global("ai_scope", nxt)
    DB.set_global("ai_enabled", "0" if nxt == "off" else "1")  # legacy-ключ
    await cb.message.edit_reply_markup(reply_markup=settings_kb(cb.from_user.id))
    await cb.answer(_AI_SCOPE_TEXT[nxt], show_alert=True)




# ------------------------------------- пользователи, нейродоступ и статистика
AI_USERS_PER_PAGE = 8


def _user_identity(u: dict) -> str:
    username = (u.get("username") or "").strip().lstrip("@")
    first = (u.get("first_name") or "").strip()
    if username:
        base = f"@{username}"
    elif first:
        base = first
    elif not u.get("known", True):
        base = "ещё не запускал бота"
    else:
        base = "без имени"
    return f"{base} · ID {int(u['user_id'])}"


def _known_user(user_id: int) -> dict | None:
    for row in DB.list_users():
        if int(row["user_id"]) == user_id:
            return dict(row)
    return None


def _ai_user_entries() -> list[dict]:
    """Пользователи бота + заранее разрешённые ID, которых в базе ещё нет."""
    allowed = DB.ai_allowed_ids()
    entries: list[dict] = []
    known: set[int] = set()
    for row in DB.list_users():
        u = dict(row)
        uid = int(u["user_id"])
        known.add(uid)
        u.update(known=True, allowed=uid in allowed)
        entries.append(u)
    for uid in sorted(allowed - known):
        entries.append({"user_id": uid, "first_name": "", "username": "",
                        "created_at": 0, "last_seen": 0,
                        "known": False, "allowed": True})
    return entries


def _ai_users_view(page: int) -> tuple[str, InlineKeyboardMarkup]:
    entries = _ai_user_entries()
    s = DB.stats()
    total_pages = max(1, (len(entries) + AI_USERS_PER_PAGE - 1) // AI_USERS_PER_PAGE)
    page = min(max(page, 0), total_pages - 1)
    part = entries[page * AI_USERS_PER_PAGE:(page + 1) * AI_USERS_PER_PAGE]
    scope_human = {"all": "для всех", "owner": "только владелец + этот список",
                   "off": "выключена для всех"}[_ai_scope()]
    lines = [
        "👥 Доступ к нейросети",
        f"Пользователей бота: {s['users']}",
        f"Режим нейросети: {scope_human}",
        f"Индивидуально разрешено: {len(DB.ai_allowed_ids())}",
        "",
        "Нажимай на человека, чтобы открыть или закрыть ему нейросеть.",
        "👑 — владелец (доступ всегда), ✅ — доступ открыт, ⬜ — закрыт.",
        "Список работает в режиме «👤 только я + список». В режиме "
        "«для всех» нейросеть и так у всех, в «выключена» — ни у кого.",
    ]
    if part:
        lines.append("")
        for e in part:
            status = ("владелец" if _is_admin(int(e["user_id"])) else
                      "доступ открыт" if e["allowed"] else "доступа нет")
            lines.append(f"• {_user_identity(e)} — {status}")
    else:
        lines.append("\nПока никто не запускал бота.")
    if total_pages > 1:
        lines.append(f"\nСтраница {page + 1} из {total_pages}")
    rows: list[list[InlineKeyboardButton]] = []
    for e in part:
        uid = int(e["user_id"])
        prefix = "👑" if _is_admin(uid) else ("✅" if e["allowed"] else "⬜")
        rows.append([InlineKeyboardButton(
            text=f"{prefix} {_user_identity(e)}"[:64],
            callback_data=f"aiu:tgl:{uid}:{page}")])
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️ Назад",
                                            callback_data=f"aiu:list:{page - 1}"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="Вперёд ➡️",
                                            callback_data=f"aiu:list:{page + 1}"))
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="➕ Добавить по ID или @username",
                                      callback_data="aiu:add")])
    rows.append([InlineKeyboardButton(text="📊 Общая статистика",
                                      callback_data="stats:open")])
    rows.append([InlineKeyboardButton(text="⚙️ К настройкам",
                                      callback_data="aiu:settings")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _stats_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи и доступ к нейросети",
                              callback_data="aiu:list:0")],
        [InlineKeyboardButton(text="⚙️ К настройкам", callback_data="aiu:settings")],
    ])


def _stats_text() -> str:
    s = DB.stats()
    users = [dict(r) for r in DB.list_users()]
    scope_human = {"all": "для всех", "owner": "только владелец + индивидуальный список",
                   "off": "выключена"}[_ai_scope()]
    top = "\n".join(f"  • {name}: {n}" for name, n in s["top"]) or "  — пока пусто"
    lines = [
        "📊 Статистика бота",
        f"Пользователей: {s['users']} (с @username: {s['with_username']}, "
        f"без: {s['users'] - s['with_username']})",
        f"Генераций всего: {s['generations']} (за 24 ч: {s['today']})",
        f"Стикерпаков в реестре: {s['packs']}",
        f"Нейросеть: {scope_human}; индивидуально разрешено: {s['ai_allowed']}",
        f"Kaggle-ComfyUI: {_comfy_status_text()}",
        f"Активных генераций сейчас: {sum(1 for t in _tasks.values() if not t.done())}",
        "",
        "Топ сценариев:",
        top,
        "",
        "Пользователи (сначала недавно активные):",
    ]
    # Бюджет символов: сообщение Telegram ограничено, длинные списки
    # постранично доступны в «👥 Пользователи и доступ к нейросети».
    shown: list[str] = []
    budget = 2600
    for i, u in enumerate(users[:80], 1):
        line = f"{i}. {_user_identity(u)}"
        if shown and budget - len(line) < 0:
            break
        shown.append(line)
        budget -= len(line) + 1
    lines += shown
    if len(users) > len(shown):
        lines.append(f"…и ещё {len(users) - len(shown)} — все есть постранично "
                     "в «👥 Пользователи и доступ к нейросети».")
    if not users:
        lines.append("— пока никого")
    return "\n".join(lines)


@dp.callback_query(F.data.startswith("aiu:list:"))
async def cb_ai_users(cb: CallbackQuery) -> None:
    if not _is_admin(cb.from_user.id):
        await cb.answer("Это настройка владельца бота", show_alert=True)
        return
    try:
        page = int((cb.data or "").rsplit(":", 1)[1])
    except ValueError:
        page = 0
    text, kb = _ai_users_view(page)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@dp.callback_query(F.data.startswith("aiu:tgl:"))
async def cb_ai_user_toggle(cb: CallbackQuery) -> None:
    if not _is_admin(cb.from_user.id):
        await cb.answer("Это настройка владельца бота", show_alert=True)
        return
    parts = (cb.data or "").split(":")
    try:
        uid, page = int(parts[2]), int(parts[3])
    except (IndexError, ValueError):
        await cb.answer("Не понял пользователя")
        return
    if _is_admin(uid):
        await cb.answer("👑 У владельца доступ есть всегда", show_alert=True)
        return
    allowed = DB.set_ai_allowed(uid, not DB.is_ai_allowed(uid))
    text, kb = _ai_users_view(page)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        pass
    await cb.answer("✅ Доступ к нейросети открыт" if allowed
                    else "⬜ Доступ к нейросети закрыт")


@dp.callback_query(F.data == "aiu:add")
async def cb_ai_user_add(cb: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(cb.from_user.id):
        await cb.answer("Это настройка владельца бота", show_alert=True)
        return
    await state.set_state(Flow.waiting_ai_user)
    await cb.message.answer(
        "Пришли одним сообщением:\n"
        "• Telegram ID цифрами — это надёжнее всего, ID не меняется;\n"
        "• или @username — сработает, если человек уже запускал бота.\n\n"
        "Если человека ещё нет в списке: пусть откроет бота и нажмёт /start — "
        "появится в списке, либо пришли его ID (его можно узнать через @userinfobot).")
    await cb.answer()


@dp.message(Flow.waiting_ai_user, F.text)
async def on_ai_user_input(message: Message, state: FSMContext) -> None:
    user = message.from_user
    assert user
    if not _is_admin(user.id):
        return
    text = (message.text or "").strip()
    uid: int | None = None
    if text.isdigit():
        uid = int(text)
    else:
        row = DB.find_user_by_username(text)
        if row is not None:
            uid = int(row["user_id"])
    if not uid or uid <= 0:
        await message.answer(
            "Не нашёл такого пользователя. По @username ищу только тех, кто "
            "уже запускал бота. Пришли Telegram ID цифрами — по нему выдам "
            "доступ точно. Или /cancel, чтобы выйти.")
        return
    await state.clear()
    if _is_admin(uid):
        await message.answer("👑 Это владелец — у него доступ к нейросети есть всегда.")
        return
    DB.set_ai_allowed(uid, True)
    known = _known_user(uid)
    label = _user_identity(known or {"user_id": uid, "known": False,
                                     "username": "", "first_name": ""})
    view_text, kb = _ai_users_view(0)
    await message.answer(
        f"✅ Доступ к нейросети открыт: {label}\n"
        + ("Доступ уже действует." if known else
           "Человек ещё не запускал бота — доступ применится, когда придёт.")
        + "\n\n" + view_text, reply_markup=kb)


@dp.callback_query(F.data == "aiu:settings")
async def cb_ai_settings(cb: CallbackQuery) -> None:
    if not _is_admin(cb.from_user.id):
        await cb.answer("Это настройка владельца бота", show_alert=True)
        return
    await cb.message.answer("⚙️ Настройки", reply_markup=settings_kb(cb.from_user.id))
    await cb.answer()


@dp.callback_query(F.data == "stats:open")
async def cb_stats_open(cb: CallbackQuery) -> None:
    if not _is_admin(cb.from_user.id):
        await cb.answer("Это статистика владельца бота", show_alert=True)
        return
    await cb.message.answer(_stats_text() + await _quota_line(),
                            reply_markup=_stats_kb())
    await cb.answer()


# ------------------------------------------------------------- Kaggle ComfyUI
KAGGLE_KERNEL_FILE = Path(__file__).resolve().parent / "kaggle" / "comfy_kernel.py"
_kaggle_tasks: dict[int, asyncio.Task] = {}


def _kaggle_ready() -> bool:
    return bool(CFG.kaggle_username and CFG.kaggle_key)


def _kaggle_slug() -> str:
    return f"{CFG.kaggle_username}/deepstick-comfy"


async def _kaggle_api(method: str, path: str, **kw):  # noqa: ANN202
    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
        return await client.request(
            method, f"https://www.kaggle.com/api/v1{path}",
            auth=(CFG.kaggle_username, CFG.kaggle_key), **kw)


def _kaggle_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Запустить сессию (≈12 ч)",
                              callback_data="kg:start")],
        [InlineKeyboardButton(text="⏹ Отключить (забыть адрес)",
                              callback_data="kg:stop")],
    ])


@dp.callback_query(F.data == "kg:open")
async def cb_kaggle_open(cb: CallbackQuery) -> None:
    if not _is_admin(cb.from_user.id):
        await cb.answer("Это настройка владельца бота", show_alert=True)
        return
    if not _kaggle_ready():
        await cb.answer(
            "Нужны секреты Kaggle. Как получить: kaggle.com → аватар → "
            "Settings → API → Create New Token (скачается kaggle.json: "
            "оттуда username и key). Добавь в GitHub: Settings → Secrets "
            "and variables → Actions → KAGGLE_USERNAME и KAGGLE_KEY. "
            "И подтверди телефон в Kaggle — без этого GPU не дают.",
            show_alert=True)
        return
    url = _comfy_url()
    text = ("☁️ *Kaggle-нейросеть (ComfyUI, Wan 2.2)*\nСтатус: "
            + ("🟢 онлайн. Генерации идут через Kaggle, пока жива сессия "
               "(до ~12 ч с запуска)." if url else
               "⚪ выключена. Запуск сессии занимает 5–10 минут (скачать "
               "модели), живёт до 12 часов; квота Kaggle — ~30 GPU-часов "
               "в неделю."))
    await cb.message.answer(text, parse_mode="Markdown", reply_markup=_kaggle_kb())
    await cb.answer()


@dp.callback_query(F.data == "kg:start")
async def cb_kaggle_start(cb: CallbackQuery) -> None:
    if not _is_admin(cb.from_user.id):
        await cb.answer("Это настройка владельца бота", show_alert=True)
        return
    if _comfy_url():
        await cb.answer("Уже онлайн 🟢", show_alert=True)
        return
    task = _kaggle_tasks.get(cb.from_user.id)
    if task and not task.done():
        await cb.answer("Уже запускаю, подожди…")
        return
    _kaggle_tasks[cb.from_user.id] = asyncio.create_task(
        _kaggle_launch(cb.message, cb.from_user))
    await cb.answer("Запускаю…")


@dp.callback_query(F.data == "kg:stop")
async def cb_kaggle_stop(cb: CallbackQuery) -> None:
    if not _is_admin(cb.from_user.id):
        await cb.answer("Это настройка владельца бота", show_alert=True)
        return
    DB.set_global("comfy_url", "")
    _comfy_health.update(ok=False, checked=0.0)
    await cb.answer("Отключил. Сама сессия в Kaggle доработает до конца "
                    "лимита — мгновенно остановить её можно в интерфейсе "
                    "Kaggle (My Code → deepstick-comfy → Stop).",
                    show_alert=True)


async def _comfy_quick(url: str) -> bool:
    """Быстрая проверка: ComfyUI по этому адресу реально отвечает."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(6.0)) as client:
            return (await client.get(f"{url}/system_stats")).status_code == 200
    except Exception:
        return False


async def _kaggle_state() -> str:
    """Статус существующего кернела ('' — нет или API не ответил)."""
    try:
        rs = await _kaggle_api("GET", f"/kernels/status/{_kaggle_slug()}")
        if rs.status_code == 200:
            return str(rs.json().get("status") or "")
    except Exception:
        pass
    return ""


async def _kaggle_launch(message: Message, user: User) -> None:
    status = await message.answer(
        "☁️ Запускаю Kaggle-сессию с ComfyUI (Wan 2.2)…\n"
        "Первый старт — 5–10 минут: скачать модели и поднять сервер.")
    try:
        state = await _kaggle_state()
        running = state.lower() in ("running", "queued")
        if not running:
            body = {
                "slug": _kaggle_slug(),
                "newTitle": "DeepStick ComfyUI (Wan 2.2)",
                "text": build_notebook(KAGGLE_KERNEL_FILE.read_text()),
                "language": "python", "kernelType": "notebook",
                "isPrivate": True, "enableGpu": True, "enableInternet": True,
                "datasetDataSources": [], "competitionDataSources": [],
                "kernelDataSources": [], "modelDataSources": [],
                "categoryIds": [],
            }
            r = await _kaggle_api("POST", "/kernels/push", json=body)
            if r.status_code >= 400 and "already in use" in r.text:
                # Кернел уже создан прошлой попыткой: обновляем код без
                # смены названия (Kaggle ругается на дубль заголовка).
                body.pop("newTitle", None)
                r = await _kaggle_api("POST", "/kernels/push", json=body)
            if r.status_code >= 400:
                await status.edit_text(
                    f"😖 Kaggle отклонил запуск: HTTP {r.status_code}\n"
                    f"{r.text[:280]}")
                return
        deadline = time.monotonic() + 25 * 60
        seen = ""
        dead: set[str] = set()
        while time.monotonic() < deadline:
            await asyncio.sleep(45)
            st = await _kaggle_state()
            low = st.lower().replace("_", "")
            if st and st != seen:
                seen = st
                try:
                    await status.edit_text(
                        f"☁️ Kaggle-сессия: статус {st}… жду готовности ComfyUI.")
                except TelegramBadRequest:
                    pass
            ro = await _kaggle_api("GET", f"/kernels/output/{_kaggle_slug()}")
            url = extract_tunnel(ro.json(), exclude=dead) \
                if ro.status_code == 200 else None
            if url:
                if await _comfy_quick(url):
                    DB.set_global("comfy_url", url)
                    DB.set_global("comfy_ts", str(time.time()))
                    _comfy_health.update(ok=True, checked=time.monotonic())
                    await status.edit_text(
                        "✅ *Нейросеть Kaggle онлайн!* ComfyUI (Wan 2.2) "
                        "живёт до ~12 часов или пока не кончится недельная "
                        "квота Kaggle.\nГенерации теперь идут через неё "
                        "(охват — настройкой «🧠 Нейросеть» выше), откат на "
                        "HF/локальную анимацию автоматический.",
                        parse_mode="Markdown")
                    return
                dead.add(url)  # адрес от прошлой, уже мёртвой сессии
            if low in ("error", "cancelacknowledged", "canceled", "failed"):
                await status.edit_text(
                    f"😖 Сессия Kaggle упала (статус {st}). Зайди в Kaggle → "
                    "My Code → deepstick-comfy и глянь лог последней версии.")
                return
            if low == "complete":
                await status.edit_text(
                    "😖 Сессия Kaggle завершилась, так и не опубликовав "
                    "адрес ComfyUI. Глянь лог: Kaggle → My Code → "
                    "deepstick-comfy — и пришли мне последние строки.")
                return
        await status.edit_text(
            "😖 Не дождался готовности за 25 минут. Проверь в Kaggle "
            "(My Code → deepstick-comfy), что сессия запустилась, и попробуй "
            "ещё раз.")
    except Exception as e:
        log.exception("Запуск Kaggle упал")
        try:
            await status.edit_text(f"😖 Не удалось запустить Kaggle: {e}")
        except TelegramBadRequest:
            pass
    finally:
        _kaggle_tasks.pop(user.id, None)



@dp.callback_query(F.data.startswith("set:"))
async def cb_setting(cb: CallbackQuery) -> None:
    user = cb.from_user
    key = cb.data.split(":", 1)[1]
    DB.toggle_setting(user.id, key)
    await cb.message.edit_reply_markup(reply_markup=settings_kb(user.id))
    await cb.answer("Сохранено")


@dp.callback_query(F.data == "pack:rename")
async def cb_pack_rename(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(rename_target="main")
    await state.set_state(Flow.waiting_pack_title)
    await cb.message.answer("✏️ Пришли новое название пака (до 64 символов):")
    await cb.answer()


@dp.message(Flow.waiting_pack_title, F.text)
async def on_pack_title(message: Message, state: FSMContext) -> None:
    user = message.from_user
    assert user
    data = await state.get_data()
    target = data.get("rename_target", "main")
    await state.set_state(Flow.waiting_photo)
    name, rec = await _resolve_pack(message.bot, user.id, str(target))
    title = message.text or ""
    ok, _err = (await packs.rename_pack_by_name(message.bot, name, title)
                if name else (False, "пак не найден"))
    if ok and rec is not None:
        DB.rename_pack_rec(user.id, rec["id"], title[:64])
    await message.answer("✅ Пак переименован." if ok else "😖 Не вышло — возможно, пака ещё нет.")


# ------------------------------------------------------ управление паками (v2)
@dp.callback_query(F.data == "pk:list")
async def cb_packs_list(cb: CallbackQuery) -> None:
    await cb.message.answer("📦 *Твои стикерпаки*:", parse_mode="Markdown",
                            reply_markup=_packs_list_kb(cb.from_user.id))
    await cb.answer()


async def _send_pack_card(cb: CallbackQuery, target: str) -> bool:
    name, rec = await _resolve_pack(cb.bot, cb.from_user.id, target)
    if not name:
        await cb.answer("Пак не найден", show_alert=True)
        return False
    pack = await packs.get_pack_by_name(cb.bot, name)
    if not pack:
        await cb.answer("Этого пака в Telegram пока нет — сделай стикер, и он появится.",
                        show_alert=True)
        return False
    url = f"https://t.me/addstickers/{name}"
    is_active = DB.get_settings(cb.from_user.id)["active_pack"] == target
    await cb.message.answer(
        f"📦 {pack.title}" + (" 🎯 — сюда падают новые стикеры" if is_active else "")
        + f"\nСтикеров в паке: {len(pack.stickers)}\n{url}",
        reply_markup=_pack_card_kb(target, url, custom=rec is not None,
                                   is_active=is_active))
    return True


@dp.callback_query(F.data.func(lambda d: d.startswith("pk:") and d not in ("pk:new", "pk:list")))
async def cb_pack_card(cb: CallbackQuery) -> None:
    await _send_pack_card(cb, cb.data.split(":", 1)[1])
    await cb.answer()


@dp.callback_query(F.data.startswith("pkact:"))
async def cb_pack_set_active(cb: CallbackQuery) -> None:
    target = cb.data.split(":", 1)[1]
    DB.set_active_pack(cb.from_user.id, target)
    await cb.answer("🎯 Теперь новые стикеры будут падать в этот пак")
    await _send_pack_card(cb, target)


@dp.callback_query(F.data.startswith("pkmk:"))
async def cb_pack_make(cb: CallbackQuery, state: FSMContext) -> None:
    target = cb.data.split(":", 1)[1]
    DB.set_active_pack(cb.from_user.id, target)
    await state.set_state(Flow.waiting_photo)
    await cb.message.answer(
        f"🎬 Делаем стикер в пак «{_active_title(cb.from_user.id)}».\n"
        "📸 Пришли фото — и выбери стиль и сценарий, как обычно.",
        reply_markup=main_menu())
    await cb.answer()


@dp.callback_query(F.data.startswith("pkv:"))
async def cb_pack_view(cb: CallbackQuery) -> None:
    parts = cb.data.split(":")
    target = parts[1]
    offset = int(parts[2]) if len(parts) > 2 else 0
    name, _rec = await _resolve_pack(cb.bot, cb.from_user.id, target)
    pack = await packs.get_pack_by_name(cb.bot, name) if name else None
    if not pack or not pack.stickers:
        await cb.answer("Пак пуст", show_alert=True)
        return
    page = pack.stickers[offset:offset + 10]  # по 10, чтобы не спамить чат
    for st in page:
        ref = uuid.uuid4().hex[:10]
        DB.put_ref(cb.from_user.id, name, st.file_id, ref)
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Удалить из пака", callback_data=f"pkdel:{ref}")]])
        await cb.bot.send_sticker(cb.message.chat.id, st.file_id, reply_markup=kb)
    total = len(pack.stickers)
    rows = []
    if offset + 10 < total:
        rows.append([InlineKeyboardButton(
            text=f"➡️ Ещё стикеры ({offset + 10} из {total})",
            callback_data=f"pkv:{target}:{offset + 10}")])
    await cb.message.answer(
        f"🖼 Стикеры {offset + 1}–{offset + len(page)} из {total} — "
        "под каждым кнопка удаления.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None)
    await cb.answer()


@dp.callback_query(F.data.startswith("pkdel:"))
async def cb_pack_del_sticker(cb: CallbackQuery) -> None:
    ref = cb.data.split(":", 1)[1]
    rec = DB.get_ref(ref, cb.from_user.id)
    if not rec:
        await cb.answer("Этот стикер уже удалён", show_alert=True)
        return
    ok, _err = await packs.delete_sticker(cb.bot, rec["file_id"])
    if ok:
        DB.delete_ref(ref)
        try:
            await cb.message.delete()
        except TelegramBadRequest:
            pass
        await cb.answer("🗑 Стикер удалён из пака")
    else:
        await cb.answer("Не удалось удалить — попробуй ещё раз", show_alert=True)


def _history_pick_kb(user_id: int, prefix: str) -> InlineKeyboardMarkup | None:
    rows = DB.history(user_id, limit=10)
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{r['emoji']} {r['scenario']} · {time.strftime('%d.%m %H:%M', time.localtime(r['ts']))}",
            callback_data=f"{prefix}:{r['id']}")] for r in rows])


@dp.callback_query(F.data.startswith("pkadd:"))
async def cb_pack_add_pick(cb: CallbackQuery) -> None:
    target = cb.data.split(":", 1)[1]
    kb = _history_pick_kb(cb.from_user.id, f"pkadd2:{target}")
    if kb is None:
        await cb.answer("История пуста — сначала сделай стикер", show_alert=True)
        return
    await cb.message.answer("Какой стикер добавить в пак?", reply_markup=kb)
    await cb.answer()


async def _do_add_to_pack(cb: CallbackQuery, target: str, gen_id: int) -> None:
    row = DB.get_generation(gen_id, cb.from_user.id)
    name, _rec = await _resolve_pack(cb.bot, cb.from_user.id, target)
    if not row or not row["file_id"] or not name:
        await cb.answer("Стикер недоступен", show_alert=True)
        return
    if target == "main" and await packs.get_pack_by_name(cb.bot, name) is None:
        await cb.answer("Основного пака ещё нет — сделай первый стикер", show_alert=True)
        return
    ok, err = await packs.add_file_to_pack(cb.bot, cb.from_user.id, name,
                                           row["file_id"], row["emoji"] or "🔥")
    await cb.answer("✅ Добавлено в пак" if ok else f"😖 Telegram отказал: {err}",
                    show_alert=True)


@dp.callback_query(F.data.startswith("pkadd2:"))
async def cb_pack_add_do(cb: CallbackQuery) -> None:
    _pk, target, gen = cb.data.split(":", 2)
    await _do_add_to_pack(cb, target, int(gen))


@dp.callback_query(F.data.startswith("addto:"))
async def cb_addto_pick(cb: CallbackQuery) -> None:
    gen_id = cb.data.split(":", 1)[1]
    rows = [[InlineKeyboardButton(text="📦 Основной пак",
                                  callback_data=f"addto2:main:{gen_id}")]]
    for rec in DB.list_packs(cb.from_user.id):
        rows.append([InlineKeyboardButton(text=f"📦 {rec['title']}"[:60],
                                           callback_data=f"addto2:{rec['id']}:{gen_id}")])
    await cb.message.answer("В какой пак добавить этот стикер?",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@dp.callback_query(F.data.startswith("addto2:"))
async def cb_addto_do(cb: CallbackQuery) -> None:
    _pk, target, gen = cb.data.split(":", 2)
    await _do_add_to_pack(cb, target, int(gen))


@dp.callback_query(F.data == "pk:new")
async def cb_pack_new(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Flow.waiting_new_pack_title)
    await cb.message.answer("➕ Как назовём новый пак? Пришли название текстом:")
    await cb.answer()


@dp.message(Flow.waiting_new_pack_title, F.text)
async def on_new_pack_title(message: Message, state: FSMContext) -> None:
    user = message.from_user
    assert user
    title = (message.text or "Мой пак").strip()[:64]
    kb = _history_pick_kb(user.id, "pknew")
    if kb is None:
        await state.set_state(Flow.waiting_photo)
        await message.answer("Пак нельзя создать пустым, а у тебя пока нет стикеров. "
                             "Сначала сделай стикер 🎬")
        return
    await state.update_data(new_pack_title=title)
    await state.set_state(Flow.waiting_photo)
    await message.answer(f"Пак «{title}» — выбери первый стикер для него:", reply_markup=kb)


@dp.callback_query(F.data.startswith("pknew:"))
async def cb_pack_new_first(cb: CallbackQuery, state: FSMContext) -> None:
    user = cb.from_user
    data = await state.get_data()
    title = data.get("new_pack_title") or "Мой пак"
    row = DB.get_generation(int(cb.data.split(":", 1)[1]), user.id)
    if not row or not row["file_id"]:
        await cb.answer("Стикер недоступен", show_alert=True)
        return
    me = await cb.bot.get_me()
    name = packs.custom_pack_name(user.id, me.username or "bot", uuid.uuid4().hex[:6])
    ok, err = await packs.create_pack_with_file(cb.bot, user.id, name, title,
                                                row["file_id"], row["emoji"] or "🔥")
    if not ok:
        await cb.answer(f"😖 Telegram отказал в создании пака: {err}", show_alert=True)
        return
    pack_id = DB.add_pack(user.id, name, title)
    DB.set_active_pack(user.id, str(pack_id))  # новый пак — сразу текущий
    url = f"https://t.me/addstickers/{name}"
    await cb.message.answer(
        f"✅ Пак «{title}» создан и выбран текущим 🎯\n{url}\n"
        "Новые стикеры теперь будут падать сюда. Ещё стикеры — кнопками ниже "
        "или «🎬 Сделать стикер в этот пак».",
        reply_markup=_pack_card_kb(str(pack_id), url, custom=True, is_active=True))
    await cb.answer()


@dp.callback_query(F.data.startswith("pkr:"))
async def cb_pack_rename2(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(rename_target=cb.data.split(":", 1)[1])
    await state.set_state(Flow.waiting_pack_title)
    await cb.message.answer("✏️ Пришли новое название пака (до 64 символов):")
    await cb.answer()


@dp.callback_query(F.data.startswith("pkd:"))
async def cb_pack_delete_ask(cb: CallbackQuery) -> None:
    target = cb.data.split(":", 1)[1]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗑 Да, удалить пак", callback_data=f"pkd_yes:{target}"),
        InlineKeyboardButton(text="Отмена", callback_data="pkd_no")]])
    await cb.message.answer("Удалить этот пак целиком со всеми стикерами?", reply_markup=kb)
    await cb.answer()


@dp.callback_query(F.data == "pkd_no")
async def cb_pack_delete_no(cb: CallbackQuery) -> None:
    await cb.message.delete()
    await cb.answer()


@dp.callback_query(F.data.startswith("pkd_yes:"))
async def cb_pack_delete_do(cb: CallbackQuery) -> None:
    user = cb.from_user
    rec = DB.get_pack_rec(user.id, int(cb.data.split(":", 1)[1]))
    if not rec:
        await cb.answer("Пак не найден", show_alert=True)
        return
    ok, _err = await packs.delete_pack(cb.bot, rec["name"])
    DB.delete_pack_rec(user.id, rec["id"])
    if DB.get_settings(user.id)["active_pack"] == str(rec["id"]):
        DB.set_active_pack(user.id, "main")
    await cb.message.edit_text(
        "🗑 Пак удалён." if ok else "🗑 Убрал пак из списка (в Telegram он мог уже отсутствовать).")
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
            await _deliver(message, user, src, st.emoji or "🎬", "sticker", "видеостикер", "original")
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


@dp.callback_query(Flow.waiting_scenario, F.data.startswith("scencat:"))
async def on_scen_category(cb: CallbackQuery, state: FSMContext) -> None:
    cat = (cb.data or "").split(":", 1)[1]
    if cat == "root":
        await cb.message.edit_text("Выбери *категорию*, а в ней — сценарий, или опиши свой:",
                                   parse_mode="Markdown", reply_markup=scenarios_kb())
    else:
        title = dict(CATEGORIES).get(cat, "Сценарии")
        await cb.message.edit_text(f"*{title}* — выбери сценарий:",
                                   parse_mode="Markdown", reply_markup=scenarios_kb(cat))
    await cb.answer()


@dp.callback_query(Flow.waiting_scenario, F.data == "scen:custom")
async def on_custom(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Flow.waiting_custom_text)
    await cb.message.edit_text(
        "✍️ Опиши сценарий одним предложением, например:\n"
        "«лечу на ракете», «открываю холодильник-портал», «дирижирую оркестром котов»\n\n"
        + ("🧠 Нейросеть выполнит его буквально." if _neuro_advertised(cb.from_user.id) else
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
    _start_generation(cb.message, user, Path(data["photo"]), data.get("style", "original"),
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
        _start_generation(cb.message, user, Path(last["photo"]), last["style"] or "original",
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



# ------------------------------------------------------------------ оживление набора
REVIVE_LIMIT_AI = 10  # первые N стикеров в нейро-режиме; остальные — локально


def revive_scenarios_kb(category: str | None = None) -> InlineKeyboardMarkup:
    if category is None:
        return _cat_kb("rvs", "rvscat:", "rvs:")
    return _scen_kb(scenarios_in(category), "rvs:", "rvscat:")


def revive_mode_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Движения по эмодзи стикеров (у каждого своё)",
                              callback_data="rvm:emoji")],
        [InlineKeyboardButton(text="🎯 Одно движение для всех",
                              callback_data="rvm:single")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ])


def revive_engine_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Нейросеть (живое движение, долго)",
                              callback_data="rveng:ai")],
        [InlineKeyboardButton(text="⚡ Локально (вырезать фон + эффект, быстро)",
                              callback_data="rveng:local")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ])


async def _with_retry(factory, tries: int = 3):  # noqa: ANN001, ANN202
    """Повтор при Telegram-флуде (RetryAfter): подождать и попробовать снова."""
    for attempt in range(tries):
        try:
            return await factory()
        except TelegramRetryAfter as e:
            if attempt == tries - 1:
                raise
            await asyncio.sleep(float(e.retry_after) + 1)


def _file_has_transparency(path: Path) -> bool:
    from PIL import Image

    from app.effects import has_transparency

    with Image.open(path) as img:
        return has_transparency(img)


def _to_png(raw: Path, out: Path) -> None:
    from PIL import Image

    with Image.open(raw) as img:
        img.convert("RGBA").save(out, format="PNG")


@dp.message(F.text == MENU_REVIVE)
async def cmd_revive(message: Message, state: FSMContext) -> None:
    await state.set_state(Flow.waiting_revive_pack)
    await message.answer(
        "🎬 *Оживление набора стикеров*\n\n"
        "Пришли *ссылку на набор* (например, `https://t.me/addstickers/Cats`) "
        "или *любой стикер* из него.\n\n"
        "Я создам новый набор и добавлю движение каждому стикеру. Уже "
        "вырезанные стикеры не трогаю — только движение; фон вырезаю лишь "
        "у сплошных картинок. Видеостикеры скопирую как есть, анимированные "
        "(.tgs) — пропущу.",
        parse_mode="Markdown", reply_markup=main_menu())


@dp.message(Flow.waiting_revive_pack, F.sticker | F.text)
async def on_revive_input(message: Message, state: FSMContext) -> None:
    if message.sticker:
        name = message.sticker.set_name
        if not name:
            await message.answer("У этого стикера нет набора 😕 Пришли ссылку на набор.")
            return
    else:
        name = packs.parse_pack_name(message.text or "")
        if not name:
            await message.answer("Не вижу ссылки. Формат: `https://t.me/addstickers/ИмяНабора`",
                                 parse_mode="Markdown")
            return
    try:
        sset = await message.bot.get_sticker_set(name=name)
    except TelegramBadRequest:
        await message.answer("😕 Такой набор не нашёл. Проверь ссылку.")
        return
    static_n = sum(1 for st in sset.stickers if not st.is_video and not st.is_animated)
    video_n = sum(1 for st in sset.stickers if st.is_video)
    tgs_n = len(sset.stickers) - static_n - video_n
    if not static_n and not video_n:
        await message.answer("В этом наборе только .tgs-стикеры — их оживить не могу 😕")
        return
    await state.update_data(revive_src=name, revive_title=sset.title)
    await message.answer(
        f"📦 Набор «{sset.title}»: {len(sset.stickers)} стикеров "
        f"(статика {static_n}, видео {video_n}"
        + (f", пропущу .tgs: {tgs_n}" if tgs_n else "") + ").\n\n"
        "Как оживлять?",
        reply_markup=revive_mode_kb())


@dp.callback_query(F.data.startswith("rvm:"))
async def cb_revive_mode(cb: CallbackQuery, state: FSMContext) -> None:
    mode = (cb.data or "").split(":", 1)[1]
    if mode == "single":
        await cb.message.edit_text("Выбери одно движение для всех стикеров набора:",
                                   reply_markup=revive_scenarios_kb())
        await cb.answer()
        return
    await state.update_data(revive_mode="emoji", revive_scenario=None,
                            revive_custom=None)
    await _revive_engine_or_start(cb.message, cb.from_user, state, edit=True)
    await cb.answer()


@dp.callback_query(F.data.startswith("rvscat:"))
async def cb_revive_scen_category(cb: CallbackQuery, state: FSMContext) -> None:
    cat = (cb.data or "").split(":", 1)[1]
    if cat == "root":
        await cb.message.edit_text("Выбери категорию, а в ней — одно движение для всех:",
                                   reply_markup=revive_scenarios_kb())
    else:
        await cb.message.edit_text("Выбери одно движение для всех стикеров набора:",
                                   reply_markup=revive_scenarios_kb(cat))
    await cb.answer()


@dp.callback_query(F.data.startswith("rvs:"))
async def cb_revive_scenario(cb: CallbackQuery, state: FSMContext) -> None:
    choice = (cb.data or "").split(":", 1)[1]
    if choice == "custom":
        await state.set_state(Flow.waiting_revive_custom)
        await cb.message.edit_text(
            "✍️ Опиши движение одним предложением — применю его ко всем "
            "стикерам набора:")
        await cb.answer()
        return
    if choice not in SCENARIOS_BY_ID:
        await cb.answer("Такого сценария нет", show_alert=True)
        return
    await state.update_data(revive_mode="single", revive_scenario=choice,
                            revive_custom=None)
    await _revive_engine_or_start(cb.message, cb.from_user, state, edit=True)
    await cb.answer()


@dp.message(Flow.waiting_revive_custom, F.text)
async def on_revive_custom(message: Message, state: FSMContext) -> None:
    user = message.from_user
    assert user
    text = (message.text or "").strip()
    if len(text) < 3:
        await message.answer("Слишком коротко — опиши движение чуть подробнее.")
        return
    await state.update_data(revive_mode="single", revive_scenario=None,
                            revive_custom=text)
    await _revive_engine_or_start(message, user, state, edit=False)


async def _revive_engine_or_start(message: Message, user: User, state: FSMContext,
                                  *, edit: bool) -> None:
    if _ai_on(user.id):
        text = ("Чем оживлять?\n\n"
                "🧠 *Нейросеть* — настоящее движение по сценарию, но медленно "
                "(минуты на стикер) и тратит бесплатную квоту: первые "
                f"{REVIVE_LIMIT_AI} стикеров сделает нейросеть, остальные — "
                "локально, чтобы не ждать часами.\n"
                "⚡ *Локально* — вырезание фона + анимация-эффект, быстро.\n"
                "В обоих режимах оживлю *все* стикеры набора; уже вырезанные "
                "не трогаю — только добавлю движение.")
        if edit:
            await message.edit_text(text, parse_mode="Markdown",
                                    reply_markup=revive_engine_kb())
        else:
            await message.answer(text, parse_mode="Markdown",
                                 reply_markup=revive_engine_kb())
    else:
        await _revive_begin(message, user, state, "local")


@dp.callback_query(F.data.startswith("rveng:"))
async def cb_revive_engine(cb: CallbackQuery, state: FSMContext) -> None:
    engine = (cb.data or "").split(":", 1)[1]
    await _revive_begin(cb.message, cb.from_user, state, engine)
    await cb.answer()


async def _revive_begin(message: Message, user: User, state: FSMContext,
                        engine: str) -> None:
    if _busy(user.id):
        await message.answer("⏳ Сначала дождись текущей генерации "
                             "(или отмени её кнопкой выше).")
        return
    data = await state.get_data()
    await state.clear()
    task = asyncio.create_task(_revive_run(
        message, user, data["revive_src"], data.get("revive_scenario"),
        data.get("revive_custom"), engine, data.get("revive_mode", "emoji")))
    _tasks[user.id] = task


async def _revive_run(message: Message, user: User, src_name: str,
                      scenario_id: str | None, custom_text: str | None,
                      engine: str, mode: str = "emoji") -> None:
    bot = message.bot
    base_scenario = (SCENARIOS_BY_ID[scenario_id] if scenario_id
                     else match_scenario(custom_text or ""))
    style = STYLES_BY_ID["original"]
    settings = DB.get_settings(user.id)
    remove_bg = CFG.remove_bg and settings["remove_bg"]
    status = await message.answer("🎬 Оживляю набор…", reply_markup=generating_kb())
    job = _job_dir(user.id)
    done = fail = skip = 0
    fail_reasons: list[str] = []
    created = False
    url = ""
    try:
        sset = await bot.get_sticker_set(name=src_name)
        title = f"🎬 {sset.title} — оживлённые"[:64]
        me = await bot.me()
        # Каждое оживление — СВЕЖИЙ пак: в существующий не дописываем,
        # иначе повторные запуски забивают его до лимита Telegram (120)
        # и дальше падают вообще все добавления.
        new_name = packs.alive_pack_name(src_name, me.username or "")
        if await packs.get_pack_by_name(bot, new_name) is not None:
            for v in range(2, 20):
                cand = packs.alive_pack_name(f"{src_name}_v{v}", me.username or "")
                if await packs.get_pack_by_name(bot, cand) is None:
                    new_name = cand
                    break
        url = f"https://t.me/addstickers/{new_name}"
        todo, gen_seen = [], 0
        for st in sset.stickers:
            if st.is_animated:
                skip += 1
            elif st.is_video:
                todo.append(("copy", st, None))
            else:
                gen_seen += 1
                eng = ("ai" if engine == "ai" and gen_seen <= REVIVE_LIMIT_AI
                       else "local")
                todo.append(("gen", st, eng))
        total = len(todo)
        done_ai = done_local = done_copy = 0
        for i, (kind, st, eng) in enumerate(todo, 1):
            try:
                out = job / f"s{i}.webm"
                used_ai = False
                if kind == "copy":
                    file = await _with_retry(lambda: bot.get_file(st.file_id))
                    await _with_retry(lambda: bot.download(file, destination=out))
                else:
                    raw, src = job / f"s{i}.raw", job / f"s{i}.png"
                    file = await _with_retry(lambda: bot.get_file(st.file_id))
                    await _with_retry(lambda: bot.download(file, destination=raw))
                    await asyncio.to_thread(_to_png, raw, src)
                    per = (scenario_for_emoji(st.emoji) if mode == "emoji"
                           else base_scenario)
                    if eng == "ai" and await asyncio.to_thread(
                            _file_has_transparency, src):
                        # стикер уже вырезан: нейросеть не трогаем вообще,
                        # только локальное движение по родной прозрачности
                        eng = "local"
                    if eng == "ai":
                        mp4 = job / f"s{i}.mp4"
                        try:
                            await _neuro_video_q(
                                src, build_prompt(style, per,
                                                  custom_text if mode == "single" else None),
                                mp4, user.id)
                            if not await _matte_q(mp4, out):
                                await asyncio.to_thread(convert_video, mp4, out)
                            used_ai = True
                        except Exception:
                            log.warning("Оживление: нейросеть упала на стикере %s — локально", i)
                            await _render_local_q(src, "original",
                                                  per.effect, out, remove_bg)
                    else:
                        await _render_local_q(src, "original",
                                              per.effect, out, remove_bg)
                _link, _fid, err = await _with_retry(lambda: packs.add_to_named_pack(
                    bot, user.id, new_name, out,
                    st.emoji or (per.emoji if kind == "gen" else "🎬"),
                    create_title=None if created else title))
                if err and not created:
                    # Пак, видимо, удаляли: Telegram не отдаёт его имя обратно,
                    # и создание с тем же именем падает. Уходим на запасное имя.
                    log.warning("Оживление: имя %s недоступно (%s) — запасное", new_name, err)
                    new_name = packs.alive_pack_name(f"{src_name}_v2",
                                                     me.username or "")
                    url = f"https://t.me/addstickers/{new_name}"
                    _link, _fid, err = await _with_retry(lambda: packs.add_to_named_pack(
                        bot, user.id, new_name, out,
                        st.emoji or (per.emoji if kind == "gen" else "🎬"),
                        create_title=title))
                if err:
                    fail += 1
                    fail_reasons.append(f"№{i}: {str(err)[:90]}")
                    log.warning("Оживление: добавление стикера %s не удалось: %s", i, err)
                else:
                    created = True
                    done += 1
                    if kind == "copy":
                        done_copy += 1
                    elif used_ai:
                        done_ai += 1
                    else:
                        done_local += 1
            except asyncio.CancelledError:
                raise
            except Exception as e:
                fail += 1
                fail_reasons.append(f"№{i}: {type(e).__name__}: {str(e)[:90]}")
                log.exception("Оживление набора: стикер %s не удался", i)
            await asyncio.sleep(0.35)  # темп добавлений — против флуд-лимита
            try:
                await status.edit_text(
                    f"🎬 Оживляю набор «{sset.title}»: обработано {i}/{total}\n"
                    f"✅ добавлено {done}"
                    + (f", ❌ не удалось {fail}" if fail else "")
                    + (f", ⏭ .tgs пропущено {skip}" if skip else ""),
                    reply_markup=generating_kb())
            except TelegramBadRequest:
                pass
        if created:
            rec = next((r for r in DB.list_packs(user.id) if r["name"] == new_name), None)
            rec_id = int(rec["id"]) if rec else DB.add_pack(user.id, new_name, title)
            DB.set_active_pack(user.id, str(rec_id))
            actual = None
            try:
                actual = len((await bot.get_sticker_set(name=new_name)).stickers)
            except Exception:
                pass
            parts = []
            if done_ai:
                parts.append(f"🧠 нейро {done_ai}")
            if done_local:
                parts.append(f"⚡ локально {done_local}")
            if done_copy:
                parts.append(f"🎞 видео скопировано {done_copy}")
            await status.edit_text(
                f"✅ Готово! Оживил {done} стикеров"
                + (f" ({', '.join(parts)})" if parts else "")
                + (f", не удалось {fail}" if fail else "")
                + (f", пропущено .tgs {skip}" if skip else "")
                + (f"\n📦 По данным Telegram в паке сейчас стикеров: {actual}"
                   if actual is not None else "")
                + (("\n❌ Причины неудач: " + "; ".join(fail_reasons[:3])
                    + ("…" if len(fail_reasons) > 3 else ""))
                   if fail_reasons else "")
                + f"\n\n📦 Новый набор: {url}\n"
                "Сделал его текущим — новые стикеры будут падать сюда.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📦 Открыть набор", url=url)],
                    [InlineKeyboardButton(text="📦 Стикерпаки", callback_data="pk:list")],
                ]))
        else:
            await status.edit_text(
                "😖 Не удалось оживить ни одного стикера из этого набора. "
                "Попробуй другой набор или локальный режим.")
    except asyncio.CancelledError:
        try:
            await status.edit_text(
                f"⏹ Оживление остановлено. Успел добавить {done} стикеров."
                + (f"\n📦 {url}" if created else ""))
        except TelegramBadRequest:
            pass
        raise
    except Exception as e:
        log.exception("Оживление набора упало")
        try:
            await status.edit_text(f"😖 Не получилось оживить набор: {e}")
        except TelegramBadRequest:
            pass
    finally:
        shutil.rmtree(job, ignore_errors=True)
        _tasks.pop(user.id, None)


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
            await _deliver(message, user, webm, "🎬", "video", "из видео", "original")
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
    log.info("Бот @%s запущен. AI-провайдер=%s охват=%s, юзеров в БД: %s",
             me.username, ai_enabled(), _ai_scope(), DB.stats()["users"])


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
