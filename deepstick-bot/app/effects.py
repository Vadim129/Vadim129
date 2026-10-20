"""Локальная анимация фото без нейросетей (бесплатный режим).

Пайплайн как у «готовых реакций» оригинала:
  фото -> (стилизация) -> (вырезать фон) -> белая обводка ->
  покадровая Pillow-анимация на прозрачном холсте 512x512 -> VP9 WebM.

Каждая анимация зациклена бесшовно: положение в момент t=1 совпадает с t=0.
"""
from __future__ import annotations

import math
import random
from collections.abc import Iterator

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from .rembg_wrap import remove_background

CANVAS = 512


# ---------------------------------------------------------------- стилизация
def stylize(img: Image.Image, style: str) -> Image.Image:
    rgb = img.convert("RGB")
    if style == "cartoon":
        rgb = ImageOps.posterize(rgb, bits=4)
        rgb = ImageEnhance.Color(rgb).enhance(1.6)
        rgb = ImageEnhance.Contrast(rgb).enhance(1.12)
        rgb = rgb.filter(ImageFilter.SMOOTH_MORE)
    elif style == "pixel":
        small = rgb.resize((64, 64), Image.Resampling.BILINEAR)
        rgb = small.resize(rgb.size, Image.Resampling.NEAREST)
        rgb = ImageEnhance.Color(rgb).enhance(1.3)
    elif style == "neon":
        edges = rgb.filter(ImageFilter.FIND_EDGES)
        edges = ImageOps.autocontrast(edges)
        edges = ImageEnhance.Color(edges).enhance(2.0)
        rgb = Image.blend(rgb, Image.blend(rgb, edges, 0.65), 0.75)
        rgb = ImageEnhance.Color(rgb).enhance(1.5)
    elif style == "anime":
        rgb = ImageOps.posterize(rgb, bits=3)
        rgb = rgb.filter(ImageFilter.SMOOTH_MORE).filter(ImageFilter.EDGE_ENHANCE_MORE)
        rgb = ImageEnhance.Color(rgb).enhance(1.7)
        rgb = ImageEnhance.Sharpness(rgb).enhance(1.6)
    elif style == "vintage":
        gray = ImageOps.grayscale(rgb)
        rgb = ImageOps.colorize(gray, black=(35, 25, 10), white=(255, 235, 200))
        rgb = ImageEnhance.Contrast(rgb).enhance(1.05)
    elif style == "bw":
        rgb = ImageOps.autocontrast(ImageOps.grayscale(rgb)).convert("RGB")
    return rgb


def _add_white_stroke(rgba: Image.Image, width: int = 9) -> Image.Image:
    """Белая обводка по альфе — классический «стикeр»-вид."""
    alpha = rgba.split()[3]
    dilated = alpha.filter(ImageFilter.MaxFilter(width * 2 + 1))
    out = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    out.paste(white, (0, 0), dilated)
    out.alpha_composite(rgba)
    return out


def _rounded_photo(rgba: Image.Image, radius: int = 48) -> Image.Image:
    mask = Image.new("L", rgba.size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, rgba.size[0] - 1, rgba.size[1] - 1], radius, fill=255)
    out = rgba.copy()
    out.putalpha(Image.composite(rgba.split()[3], Image.new("L", rgba.size, 0), mask))
    border = Image.new("RGBA", (rgba.size[0] + 16, rgba.size[1] + 16), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle([0, 0, border.size[0] - 1, border.size[1] - 1], radius + 8,
                         outline=(255, 255, 255, 255), width=10)
    border.alpha_composite(out, (8, 8))
    return border


def prepare_subject(photo: Image.Image, style: str = "original",
                     remove_bg: bool = True, max_side: int = 400) -> Image.Image:
    """Фото -> объект-стикер, вписанный в max_side x max_side."""
    styled = stylize(photo, style)
    subject: Image.Image | None = None
    if remove_bg:
        subject = remove_background(styled)
        if subject is not None:
            bbox = subject.split()[3].getbbox()
            if bbox:
                subject = subject.crop(bbox)
            subject = _add_white_stroke(subject)
    if subject is None:
        subject = _rounded_photo(styled.convert("RGBA"))
    subject.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return subject


# ------------------------------------------------------------------- декор
def _heart(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color) -> None:
    d.ellipse([cx - s, cy - s * 0.9, cx, cy + s * 0.1], fill=color)
    d.ellipse([cx, cy - s * 0.9, cx + s, cy + s * 0.1], fill=color)
    d.polygon([(cx - s * 0.95, cy), (cx + s * 0.95, cy), (cx, cy + s * 1.2)], fill=color)


def _star(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color) -> None:
    pts = []
    for i in range(10):
        r = s if i % 2 == 0 else s * 0.45
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=color)


def _draw_decor(canvas: Image.Image, effect: str, t: float, frame: int) -> None:
    """Фон/передний план эффектов. t in [0,1) — фаза цикла."""
    d = ImageDraw.Draw(canvas, "RGBA")
    rng = random.Random(42)
    if effect == "rocket":
        for i in range(26):  # звёзды летят вниз — эффект движения вверх
            x = rng.uniform(0, CANVAS)
            y = (rng.uniform(0, CANVAS) + t * CANVAS * 2 + i * 37) % CANVAS
            _star(d, x, y, rng.uniform(4, 9), (255, 255, 200, 200))
    elif effect == "love":
        for i in range(9):
            x = 40 + (i * 53) % 430
            y = CANVAS - ((t * 260 + i * 71) % 520)
            s = 10 + (i % 3) * 5
            _heart(d, x, y, s, (255, 70, 110, 210))
    elif effect == "dance":
        for i in range(42):  # конфетти
            x = rng.uniform(0, CANVAS)
            y = (rng.uniform(0, CANVAS) + t * CANVAS + i * 29) % CANVAS
            c = [(255, 80, 80), (80, 200, 255), (255, 210, 60), (120, 255, 140)][i % 4]
            d.rectangle([x, y, x + 9, y + 5], fill=c + (220,))
    elif effect == "fire":
        for i in range(18):  # искры вверх
            x = 60 + rng.uniform(0, 390)
            y = CANVAS - ((t * 330 + i * 47) % 480)
            d.ellipse([x, y, x + 7, y + 7], fill=(255, 140, 30, 200))
    elif effect == "portal":
        cx = cy = CANVAS / 2
        for k in range(3):
            r = 190 - k * 38
            a0 = t * 360 * (1 if k % 2 == 0 else -1) + k * 40
            d.arc([cx - r, cy - r, cx + r, cy + r], a0, a0 + 240,
                  fill=(150, 90, 255, 200), width=9)
    elif effect == "money":
        for i in range(16):  # купюры падают сверху
            x = (i * 67 + (i % 3) * 20) % 480
            y = (rng.uniform(0, CANVAS) + t * CANVAS + i * 43) % CANVAS
            d.rectangle([x, y, x + 44, y + 22], fill=(70, 190, 90, 225),
                        outline=(30, 120, 50, 255), width=2)
            d.ellipse([x + 17, y + 6, x + 27, y + 16], outline=(230, 255, 230, 255), width=2)
    elif effect == "sleep":
        try:
            font = ImageFont.load_default(size=44)
            font_s = ImageFont.load_default(size=30)
        except Exception:
            font = font_s = ImageFont.load_default()
        for i, (fnt, off) in enumerate(((font_s, 0), (font, 46), (font, 96))):
            y = 120 - ((t * 90 + off) % 140) + i * 8
            d.text((398 + i * 26, y), "Z", font=fnt, fill=(150, 200, 255, 230))
    elif effect == "angry":
        for i in range(14):
            x = 50 + rng.uniform(0, 410)
            y = (rng.uniform(0, CANVAS) - t * CANVAS * 1.4 + i * 31) % CANVAS
            d.ellipse([x, y, x + 6, y + 6], fill=(255, 60, 40, 210))
    elif effect == "winner":
        for i in range(18):
            x = rng.uniform(10, CANVAS - 10)
            y = rng.uniform(10, CANVAS - 10)
            s = 6 + (i % 4) * 3 + 3 * math.sin(t * 6.28 + i)
            _star(d, x, y, max(3, s), (255, 215, 60, 230))
    elif effect == "cry":
        for i in range(16):  # капли вниз
            x = 40 + (i * 61) % 430
            y = (rng.uniform(0, CANVAS) + t * CANVAS * 1.6 + i * 37) % CANVAS
            d.ellipse([x, y, x + 7, y + 11], fill=(90, 170, 255, 210))


def _draw_flame(canvas: Image.Image, subj_box, t: float, frame: int) -> None:
    if subj_box is None:
        return
    x0, y0, x1, y1 = subj_box
    cx, flick = (x0 + x1) / 2, 1 + 0.25 * math.sin(frame * 1.7)
    d = ImageDraw.Draw(canvas, "RGBA")
    h = 62 * flick
    d.polygon([(cx - 26, y1 - 6), (cx + 26, y1 - 6), (cx, y1 + h)], fill=(255, 120, 20, 235))
    d.polygon([(cx - 14, y1 - 4), (cx + 14, y1 - 4), (cx, y1 + h * 0.6)], fill=(255, 210, 60, 255))


# ------------------------------------------------------------------ движение
def _motion(effect: str, t: float) -> tuple[float, float, float, float]:
    """-> (dx, dy, angle_deg, scale) в фазе t."""
    w = 2 * math.pi
    if effect == "bounce":
        return 0, -abs(math.sin(w * 2 * t)) * 46, math.sin(w * t) * 4, 1.0
    if effect == "dance":
        return math.sin(w * 2 * t) * 16, -abs(math.sin(w * 2 * t)) * 30, math.sin(w * 2 * t) * 11, 1.0
    if effect == "spin":
        return 0, math.sin(w * t) * 8, 360 * t, 1.0
    if effect == "shake":  # смех: мелкая тряска
        return math.sin(w * 9 * t) * 9, math.sin(w * 7 * t) * 6, math.sin(w * 9 * t) * 5, 1.03
    if effect == "nod":
        return 0, abs(math.sin(w * 2 * t)) * 20, math.sin(w * 2 * t) * 3, 1.0
    if effect == "no":
        return math.sin(w * 2 * t) * 34, 0, math.sin(w * 2 * t) * 6, 1.0
    if effect == "zoom":  # удивление: наезд туда-обратно
        s = 1 + 0.30 * (0.5 - 0.5 * math.cos(w * t))
        return 0, 0, 0, s
    if effect == "wave":
        return 0, math.sin(w * t) * 10, math.sin(w * 2 * t) * 13, 1.0
    if effect == "rocket":
        return math.sin(w * 3 * t) * 12, math.sin(w * t) * -22 - 10, math.sin(w * 3 * t) * 7, 1.0
    if effect == "love":  # сердцебиение
        pulse = max(0.0, math.sin(w * 2 * t)) ** 3
        return 0, math.sin(w * t) * 8, math.sin(w * t) * 3, 1 + 0.09 * pulse
    if effect == "fire":
        return math.sin(w * 8 * t) * 4, math.sin(w * t) * 6, math.sin(w * 4 * t) * 3, 1.02
    if effect == "portal":
        return 0, math.sin(w * t) * 18, math.sin(w * t) * 5, 1 + 0.03 * math.sin(w * t)
    if effect == "money":
        return math.sin(w * t) * 8, -abs(math.sin(w * 2 * t)) * 26, math.sin(w * t) * 5, 1.0
    if effect == "sleep":
        return math.sin(w * t) * 6, math.sin(w * t) * 12, math.sin(w * t) * 6, 0.97
    if effect == "angry":
        return math.sin(w * 11 * t) * 11, math.sin(w * 9 * t) * 5, math.sin(w * 11 * t) * 6, 1.04
    if effect == "winner":
        return 0, -abs(math.sin(w * 2 * t)) * 54, math.sin(w * t) * 3, 1.02
    if effect == "cry":
        return math.sin(w * 7 * t) * 5, abs(math.sin(w * 2 * t)) * 10, math.sin(w * 7 * t) * 4, 1.0
    return 0, math.sin(w * t) * 10, math.sin(w * t) * 4, 1.0  # float по умолчанию


def render_frames(subject: Image.Image, effect: str, fps: int = 30,
                  duration: float = 2.8) -> Iterator[Image.Image]:
    """Генератор RGBA-кадров 512x512 (ленивый — кадры не копим в памяти)."""
    n = max(2, int(fps * duration))
    cx = cy = CANVAS / 2
    for i in range(n):
        t = i / n
        frame = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        _draw_decor(frame, effect, t, i)
        dx, dy, angle, scale = _motion(effect, t)
        w = max(1, int(subject.size[0] * scale))
        h = max(1, int(subject.size[1] * scale))
        obj = subject.resize((w, h), Image.Resampling.LANCZOS)
        if angle:
            obj = obj.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        x = int(cx + dx - obj.size[0] / 2)
        y = int(cy + dy - obj.size[1] / 2)
        frame.alpha_composite(obj, (x, y))
        if effect == "rocket":
            _draw_flame(frame, (x, y, x + obj.size[0], y + obj.size[1]), t, i)
        elif effect in ("love", "dance", "fire", "money", "cry", "winner", "angry"):
            _draw_decor(frame, effect, t, i)  # часть декора поверх объекта
        yield frame
