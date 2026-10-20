"""Вырезание фона через rembg (опциональная зависимость).

Если rembg не установлен — возвращаем None, и бот работает с фото целиком
(прямоугольный стикер со скруглёнными углами и белой обводкой).
"""
from __future__ import annotations

import io
import logging

from PIL import Image

log = logging.getLogger(__name__)


_SESSION = None


def _session():
    global _SESSION
    if _SESSION is None:
        from rembg import new_session  # type: ignore

        _SESSION = new_session("u2net")  # модель качается 1 раз в ~/.u2net
    return _SESSION


def remove_background(img: Image.Image) -> Image.Image | None:
    try:
        from rembg import remove  # type: ignore
    except Exception:
        log.info("rembg не установлен — фон не вырезаем")
        return None
    try:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        out = remove(buf.getvalue(), session=_session())
        result = Image.open(io.BytesIO(out)).convert("RGBA")
        return result
    except Exception:
        log.exception("rembg упал — работаем без вырезания")
        return None
