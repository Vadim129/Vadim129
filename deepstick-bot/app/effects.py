"""Локальная анимация без нейросетей (бесплатный режим).

Пайплайн: фото -> стилизация -> вырезание фона (если нужно) -> покадровая
Pillow-анимация на прозрачном холсте 512x512 -> VP9 WebM.

Движок анимаций (переписан в 2026-10):
* траектории — функции фазы t in [0,1): сдвиг/поворот/сквош персонажа,
  только периодические, поэтому каждый ролик зациклен бесшовно;
* классические принципы: squash & stretch, антиципация, изинги,
  динамическая тень под персонажем, свечение, вспышки;
* декор — частичные системы (сердечки, звёзды, конфетти, дождь, пузыри…)
  режимами rise/fall/orbit/burst/drift/twinkle/fountain + якорный декор
  (пламя под ногами, корона, нимб, всплеск).
Каталог — EFFECTS (~100 эффектов), сценарии лежат в app/scenarios.py.
"""
from __future__ import annotations

import math
import random
import zlib
from collections.abc import Iterator

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from .rembg_wrap import remove_background

CANVAS = 512
TAU = 2 * math.pi


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


def has_transparency(img: Image.Image, threshold: float = 0.01) -> bool:
    """У картинки уже есть настоящий прозрачный фон (а не сплошной прямоугольник)."""
    if img.mode == "P":
        img = img.convert("RGBA")
    if img.mode not in ("RGBA", "LA"):
        return False
    alpha = img.getchannel("A")
    hist = alpha.histogram()
    clear = sum(hist[:250])
    return clear > threshold * img.width * img.height


def _smooth_alpha(rgba: Image.Image, radius: float = 1.1) -> Image.Image:
    """Мягкий край маски: лёгкое размытие альфы убирает «лесенку» и ореол."""
    alpha = rgba.split()[3].filter(ImageFilter.GaussianBlur(radius))
    out = rgba.copy()
    out.putalpha(alpha)
    return out


def prepare_subject(photo: Image.Image, style: str = "original",
                    remove_bg: bool = True, max_side: int = 400) -> Image.Image:
    """Фото/стикер -> объект для анимации, вписанный в max_side x max_side.

    Правила фона:
    * картинка уже вырезана (есть прозрачность) — фон не трогаем НИКОГДА,
      ни в каком режиме: берём родную альфу, дальше только движение;
    * сплошной прямоугольник/квадрат + вырезание включено — режем rembg;
    * вырезание выключено или недоступно — картинка как есть, целиком.
    Никаких рамок, скруглений и обводок не добавляется ни в одном режиме.
    """
    styled = stylize(photo, style)
    if has_transparency(photo):
        alpha = photo.convert("RGBA").split()[3]
        if alpha.size != styled.size:
            alpha = alpha.resize(styled.size, Image.Resampling.LANCZOS)
        subject = styled.convert("RGBA")
        subject.putalpha(alpha)
        bbox = subject.split()[3].getbbox()
        if bbox:
            subject = subject.crop(bbox)
        subject = _smooth_alpha(subject)
        subject.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        return subject
    if remove_bg:
        cut = remove_background(styled)
        if cut is not None:
            bbox = cut.split()[3].getbbox()
            if bbox:
                cut = cut.crop(bbox)
            cut = _smooth_alpha(cut)
            cut.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            return cut
    subject = styled.convert("RGBA")
    subject.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return subject


# ================================================================== ДВИЖОК
def _hop(t: float, n: int = 2, h: float = 48) -> float:
    """n прыжков за цикл, высота h (вверх — отрицательный y)."""
    return -abs(math.sin(math.pi * n * t)) * h


def _land(t: float, n: int = 2) -> float:
    """1.0 в момент касания земли (для сквоша при приземлении)."""
    return abs(math.cos(math.pi * n * t))


def _sin(freq: float = 1, amp: float = 1.0, phase: float = 0.0):
    return lambda t: amp * math.sin(TAU * freq * t + phase)


def _pulse(t: float, n: int = 2, power: float = 3) -> float:
    return max(0.0, math.sin(TAU * n * t)) ** power


def _steps(v: float, steps: int = 8):
    """Квантование значения — «роботная»/стоп-моушн подача."""
    return lambda t: v(math.floor(t * steps) / steps)


def _spec(x=0, y=0, rot=0, sx=1, sy=1, alpha=1, shadow=False, glow=None,
          tint=None, decor=()) -> dict:
    return {"x": x, "y": y, "rot": rot, "sx": sx, "sy": sy, "alpha": alpha,
            "shadow": shadow, "glow": glow, "tint": tint, "decor": list(decor)}


def _P(kind, n=10, mode="rise", colors=((255, 255, 255),), size=(6, 12),
       speed=1.0, layer="back", area=None, alpha=210) -> dict:
    """Слой частиц."""
    return {"kind": kind, "n": n, "mode": mode, "colors": colors,
            "size": size, "speed": speed, "layer": layer, "area": area,
            "alpha": alpha}


def _A(kind, layer="front", **kw) -> dict:
    """Якорный декор (привязан к рамке персонажа)."""
    d = {"kind": kind, "anchor": True, "layer": layer}
    d.update(kw)
    return d


GOLD = ((255, 205, 60), (255, 225, 130), (255, 170, 30))
PINK = ((255, 90, 140), (255, 140, 180), (255, 60, 110))
RAINBOW = ((255, 90, 90), (255, 180, 60), (255, 230, 90),
           (110, 220, 120), (90, 170, 255), (180, 120, 255))
BLUE = ((120, 190, 255), (170, 220, 255), (90, 150, 255))
WHITE = ((255, 255, 255), (235, 240, 255))

# ------------------------------------------------------------------ каталог
EFFECTS: dict[str, dict] = {
    # --- базовые движения -------------------------------------------------
    "bounce": _spec(y=lambda t: _hop(t, 2, 52),
                    sy=lambda t: 1 - 0.15 * _land(t, 2) ** 1.5,
                    sx=lambda t: 1 + 0.11 * _land(t, 2) ** 1.5,
                    rot=_sin(1, 3), shadow=True),
    "jump_big": _spec(y=lambda t: _hop(t, 1, 120),
                      sy=lambda t: 1 - 0.22 * _land(t, 1) ** 2 + 0.10 * (1 - _land(t, 1)),
                      sx=lambda t: 1 + 0.16 * _land(t, 1) ** 2,
                      shadow=True),
    "hop_small": _spec(y=lambda t: _hop(t, 4, 26),
                       sy=lambda t: 1 - 0.10 * _land(t, 4), shadow=True),
    "float": _spec(y=_sin(1, 16), rot=_sin(1, 3), x=_sin(0.5, 8)),
    "sway": _spec(rot=_sin(1, 7), x=_sin(1, 10), y=_sin(2, 5)),
    "pendulum": _spec(rot=_sin(1, 16), x=_sin(1, 26)),
    "spin": _spec(rot=lambda t: 360 * t, y=_sin(1, 8)),
    "spin_slow": _spec(rot=lambda t: 180 * math.sin(TAU * t), y=_sin(1, 10)),
    "peek": _spec(x=lambda t: 60 * math.sin(TAU * t) ** 3, rot=_sin(1, 4),
                  decor=[_P("quest", 3, "twinkle", WHITE, (16, 24), 1.0, "front")]),
    "dash_side": _spec(x=_sin(1, 95), rot=_sin(1, 5),
                       decor=[_P("line", 8, "drift", WHITE, (24, 44), 1.6, "back")]),
    "run_place": _spec(y=lambda t: -abs(math.sin(TAU * 4 * t)) * 20,
                       rot=_sin(4, 4), shadow=True,
                       decor=[_P("line", 10, "drift", WHITE, (26, 50), 2.2, "back"),
                              _P("puff", 7, "fountain", ((220, 220, 220),), (10, 18), 1.4, "back")]),
    "walk_place": _spec(y=lambda t: -abs(math.sin(TAU * 2 * t)) * 10,
                        rot=_sin(2, 5), x=_sin(2, 6), shadow=True),
    "swim": _spec(x=_sin(1, 42), y=_sin(2, 16), rot=_sin(1, 7),
                  decor=[_P("bubble", 12, "rise", BLUE, (5, 13), 0.9, "front"),
                         _P("ring", 3, "burst", BLUE, (8, 14), 0.7, "back")]),
    "glide": _spec(x=_sin(1, 55), y=_sin(2, 20), rot=_sin(1, 6),
                   decor=[_P("line", 7, "drift", WHITE, (30, 55), 1.4, "back")]),
    "carve": _spec(x=_sin(1, 70), rot=_sin(1, 13),
                   sy=lambda t: 1 - 0.05 * abs(math.sin(TAU * t)), shadow=True,
                   decor=[_P("puff", 8, "fountain", WHITE, (8, 16), 1.3, "back")]),
    "robot_dance": _spec(x=_steps(_sin(1, 26), 8), rot=_steps(_sin(2, 14), 8),
                         y=_steps(lambda t: -abs(math.sin(TAU * 2 * t)) * 14, 8)),
    "zombie": _spec(rot=_sin(0.5, 11), x=_sin(0.5, 20),
                    y=lambda t: abs(math.sin(TAU * t)) * 8,
                    sx=lambda t: 1 + 0.03 * math.sin(TAU * 0.5 * t)),
    "levitate": _spec(y=lambda t: -26 + 10 * math.sin(TAU * t), rot=_sin(1, 2.5),
                      decor=[_P("ring", 4, "burst", ((170, 130, 255),), (8, 13), 0.8, "back"),
                             _A("glowpad", "back")]),
    "ghost_float": _spec(y=_sin(1, 22), x=_sin(0.5, 14),
                         alpha=lambda t: 0.72 + 0.28 * math.sin(TAU * t),
                         decor=[_P("bubble", 8, "rise", ((200, 210, 255),), (6, 13), 0.7, "back")]),
    "teleport": _spec(alpha=lambda t: 0.15 + 0.85 * abs(math.sin(TAU * 2 * t)),
                      sx=lambda t: 0.85 + 0.15 * abs(math.sin(TAU * 2 * t)),
                      sy=lambda t: 0.85 + 0.15 * abs(math.sin(TAU * 2 * t)),
                      decor=[_P("star4", 10, "burst", ((170, 220, 255),), (8, 15), 1.6, "front")]),
    # --- эмоции ------------------------------------------------------------
    "laugh": _spec(x=_sin(9, 9), y=_sin(7, 6), rot=_sin(9, 5), sx=1.03,
                   decor=[_P("drop", 8, "burst", BLUE, (8, 15), 1.3, "front")]),
    "cry": _spec(y=lambda t: abs(math.sin(TAU * 2 * t)) * 10, x=_sin(7, 5),
                 sy=lambda t: 1 - 0.07 * _pulse(t, 2),
                 decor=[_P("drop", 14, "fall", BLUE, (7, 12), 1.5, "front")]),
    "love_beat": _spec(sx=lambda t: 1 + 0.11 * _pulse(t, 2),
                       sy=lambda t: 1 + 0.11 * _pulse(t, 2), rot=_sin(1, 3),
                       decor=[_P("heart", 11, "rise", PINK, (10, 22), 0.9, "front"),
                              _P("heart", 6, "orbit", PINK, (9, 15), 0.8, "back")]),
    "wow": _spec(sx=lambda t: 1 + 0.34 * (0.5 - 0.5 * math.cos(TAU * t)),
                 sy=lambda t: 1 + 0.34 * (0.5 - 0.5 * math.cos(TAU * t)),
                 decor=[_P("line", 9, "burst", GOLD, (20, 36), 1.2, "back")]),
    "mind_blown": _spec(sx=lambda t: 1 + 0.22 * _pulse(t, 1, 6),
                        sy=lambda t: 1 + 0.22 * _pulse(t, 1, 6),
                        decor=[_P("star4", 12, "burst", RAINBOW, (8, 16), 1.4, "front"),
                               _P("bang", 3, "twinkle", ((255, 90, 90),), (20, 30), 1.4, "front")]),
    "angry": _spec(x=_sin(11, 11), y=_sin(9, 5), rot=_sin(11, 6), sx=1.04,
                   decor=[_A("vein", "front"),
                          _P("star4", 8, "burst", ((255, 90, 60),), (7, 13), 1.5, "front")]),
    "sleep": _spec(rot=_sin(1, 6), y=_sin(1, 11), x=_sin(1, 6), sx=0.98, sy=0.98,
                   decor=[_P("zzz", 4, "rise", ((150, 190, 255),), (15, 26), 0.55, "front")]),
    "dizzy": _spec(rot=_sin(2, 15), x=_sin(2, 18), y=_sin(4, 6),
                   decor=[_P("star4", 7, "orbit", GOLD, (9, 15), 1.5, "front")]),
    "scared": _spec(x=_sin(16, 6), y=lambda t: _hop(t, 1, 60) + math.sin(TAU * 16 * t) * 2,
                    shadow=True,
                    decor=[_P("sweat", 6, "burst", BLUE, (8, 14), 1.4, "front")]),
    "shy": _spec(rot=_sin(1, 4), x=_sin(1, 8), sx=0.97, sy=0.97,
                 decor=[_A("blush", "front"),
                        _P("heart", 4, "twinkle", PINK, (8, 13), 0.8, "front")]),
    "sick": _spec(rot=_sin(1, 5), y=_sin(1, 8),
                  tint=((120, 220, 130), lambda t: 0.20 + 0.12 * math.sin(TAU * t)),
                  decor=[_P("bubble", 7, "rise", ((140, 230, 150),), (6, 12), 0.7, "back")]),
    "proud": _spec(sx=lambda t: 1 + 0.06 * _pulse(t, 1, 2),
                   sy=lambda t: 1 + 0.08 * _pulse(t, 1, 2), y=_sin(1, 5),
                   decor=[_P("star4", 8, "twinkle", GOLD, (8, 14), 1.0, "back")]),
    "bored": _spec(y=lambda t: 12 * (0.5 - 0.5 * math.cos(TAU * t)),
                   rot=_sin(1, 3), sy=lambda t: 1 - 0.04 * (0.5 - 0.5 * math.cos(TAU * t)),
                   decor=[_P("bubble", 4, "rise", WHITE, (8, 15), 0.5, "front")]),
    "kiss": _spec(x=lambda t: 16 * math.sin(TAU * t) ** 3,
                  sx=lambda t: 1 + 0.08 * max(0.0, math.sin(TAU * t)) ** 2,
                  sy=lambda t: 1 + 0.08 * max(0.0, math.sin(TAU * t)) ** 2,
                  decor=[_A("lips", "front"),
                         _P("heart", 6, "burst", PINK, (9, 16), 0.9, "front")]),
    "wink": _spec(rot=_sin(2, 8), y=_sin(2, 6),
                  decor=[_P("star4", 5, "twinkle", GOLD, (10, 17), 1.6, "front")]),
    "dead_fun": _spec(rot=lambda t: 72 * max(0.0, math.sin(TAU * t)) ** 2,
                      y=lambda t: 26 * max(0.0, math.sin(TAU * t)) ** 2,
                      decor=[_A("ghost", "front")]),
    "drool": _spec(rot=_sin(1, 4), y=_sin(1, 7),
                   decor=[_P("drop", 5, "burst", BLUE, (8, 14), 0.8, "front"),
                          _P("star4", 5, "twinkle", GOLD, (8, 13), 0.9, "back")]),
    "rage_red": _spec(x=_sin(13, 10), sx=1.05, sy=1.05,
                      tint=((255, 90, 80), lambda t: 0.16 + 0.10 * math.sin(TAU * 3 * t)),
                      decor=[_P("flame", 8, "burst", ((255, 130, 50), (255, 180, 80)), (12, 22), 1.5, "back")]),
    # --- жесты --------------------------------------------------------------
    "hello_wave": _spec(rot=_sin(2, 12), y=_sin(1, 9),
                        decor=[_P("star4", 5, "twinkle", WHITE, (8, 14), 1.2, "front")]),
    "nod_yes": _spec(y=lambda t: abs(math.sin(TAU * 2 * t)) * 22,
                     rot=_sin(2, 3), shadow=True),
    "big_no": _spec(x=_sin(2, 36), rot=_sin(2, 7),
                    decor=[_A("cross", "front")]),
    "ok_ring": _spec(y=lambda t: _hop(t, 2, 22), shadow=True,
                     decor=[_A("ringfloat", "front")]),
    "thanks_bow": _spec(rot=lambda t: 18 * max(0.0, math.sin(TAU * t)),
                        y=lambda t: 20 * max(0.0, math.sin(TAU * t)),
                        decor=[_P("star4", 6, "twinkle", GOLD, (8, 13), 0.9, "front")]),
    "applause": _spec(y=lambda t: _hop(t, 4, 18), shadow=True,
                      decor=[_P("star4", 10, "burst", GOLD, (8, 15), 1.8, "front")]),
    "facepalm": _spec(y=lambda t: 18 * (0.5 - 0.5 * math.cos(TAU * t)),
                      rot=lambda t: 6 * (0.5 - 0.5 * math.cos(TAU * t)),
                      decor=[_P("sweat", 4, "burst", BLUE, (8, 13), 0.9, "front")]),
    "shrug": _spec(y=lambda t: _hop(t, 2, 14),
                   sy=lambda t: 1 - 0.08 * _land(t, 2), shadow=True,
                   decor=[_P("quest", 4, "twinkle", WHITE, (15, 23), 1.1, "front")]),
    "think": _spec(rot=lambda t: 8 * math.sin(TAU * t) ** 1, x=_sin(1, 8),
                   decor=[_P("quest", 3, "rise", WHITE, (14, 22), 0.6, "front"),
                          _P("bubble", 5, "rise", WHITE, (6, 12), 0.6, "front")]),
    "salute": _spec(sy=lambda t: 1 + 0.07 * _pulse(t, 2, 4),
                    y=lambda t: _hop(t, 2, 16), shadow=True),
    "fist_pump": _spec(y=lambda t: _hop(t, 3, 34), rot=_sin(3, 4), shadow=True,
                       decor=[_P("star4", 6, "burst", GOLD, (7, 12), 1.4, "front")]),
    "please": _spec(rot=_sin(1, 5), y=_sin(2, 7),
                    decor=[_P("heart", 5, "twinkle", PINK, (8, 14), 0.9, "front"),
                           _P("star4", 5, "twinkle", WHITE, (7, 12), 0.9, "back")]),
    "stop_push": _spec(sx=lambda t: 1 + 0.16 * _pulse(t, 2, 2),
                       sy=lambda t: 1 + 0.16 * _pulse(t, 2, 2),
                       decor=[_P("ring", 4, "burst", ((255, 120, 120),), (8, 13), 1.2, "front")]),
    "point_cam": _spec(sx=lambda t: 1 + 0.13 * _pulse(t, 1, 3),
                       sy=lambda t: 1 + 0.13 * _pulse(t, 1, 3), rot=_sin(1, 2),
                       decor=[_P("star4", 6, "burst", GOLD, (8, 14), 1.2, "front")]),
    # --- танцы и драйв --------------------------------------------------------
    "dance_groove": _spec(x=_sin(2, 17), y=lambda t: -abs(math.sin(TAU * 2 * t)) * 30,
                          rot=_sin(2, 11), shadow=True,
                          decor=[_P("note", 7, "rise", RAINBOW, (11, 18), 1.0, "back"),
                                 _P("confetti", 12, "fall", RAINBOW, (7, 12), 1.1, "front")]),
    "dance_spin": _spec(rot=lambda t: 360 * t, y=lambda t: _hop(t, 2, 24),
                        decor=[_P("note", 6, "orbit", RAINBOW, (11, 17), 1.2, "back")]),
    "disco": _spec(x=_sin(2, 15), y=lambda t: -abs(math.sin(TAU * 2 * t)) * 26,
                   rot=_sin(2, 9), shadow=True,
                   tint=((255, 120, 220), lambda t: 0.10 + 0.08 * math.sin(TAU * 2 * t)),
                   decor=[_P("circle", 16, "twinkle", RAINBOW, (6, 13), 1.8, "back"),
                          _P("note", 5, "rise", RAINBOW, (11, 17), 1.0, "front")]),
    "breakdance": _spec(rot=lambda t: 360 * t, y=lambda t: _hop(t, 1, 40),
                        sy=lambda t: 1 - 0.12 * _land(t, 1), shadow=True,
                        decor=[_P("star4", 9, "burst", RAINBOW, (8, 14), 1.6, "back")]),
    "moonwalk": _spec(x=_sin(1, 62), y=_sin(4, 4), rot=_sin(1, 3),
                      decor=[_P("star4", 9, "drift", GOLD, (7, 12), 0.8, "back")]),
    "workout": _spec(sy=lambda t: 1 - 0.16 * _pulse(t, 2, 1.5),
                     sx=lambda t: 1 + 0.10 * _pulse(t, 2, 1.5),
                     y=lambda t: 12 * _pulse(t, 2, 1.5), shadow=True,
                     decor=[_P("sweat", 7, "burst", BLUE, (7, 12), 1.6, "front")]),
    "stretch": _spec(sx=lambda t: 1 + 0.14 * math.sin(TAU * t),
                     sy=lambda t: 1 - 0.08 * math.sin(TAU * t), rot=_sin(1, 5)),
    "yoga": _spec(y=lambda t: -18 + 8 * math.sin(TAU * t), rot=_sin(1, 2),
                  decor=[_P("ring", 3, "orbit", ((170, 230, 190),), (7, 11), 0.5, "back"),
                         _A("glowpad", "back")]),
    "jump_rope": _spec(y=lambda t: _hop(t, 3, 44),
                       sy=lambda t: 1 - 0.12 * _land(t, 3), shadow=True,
                       decor=[_A("rope", "front")]),
    "surf": _spec(rot=_sin(1, 12), x=_sin(1, 30), y=_sin(2, 12),
                  decor=[_A("splash", "front"), _P("drop", 8, "burst", BLUE, (7, 12), 1.2, "front")]),
    "skate": _spec(x=_sin(1, 74), rot=_sin(1, 8), y=lambda t: _hop(t, 1, 30),
                   decor=[_P("line", 7, "drift", WHITE, (26, 46), 1.5, "back")]),
    "boxer": _spec(x=_sin(2, 24), y=lambda t: -abs(math.sin(TAU * 2 * t)) * 14,
                   rot=_sin(2, 5), shadow=True,
                   sx=lambda t: 1 + 0.10 * _pulse(t, 2, 5),
                   decor=[_P("star4", 6, "burst", GOLD, (7, 12), 1.7, "front")]),
    "karate": _spec(rot=_steps(lambda t: 16 * math.sin(TAU * 2 * t), 6),
                    x=_steps(_sin(2, 20), 6),
                    sx=lambda t: 1 + 0.08 * _pulse(t, 2, 6)),
    "ninja": _spec(x=_steps(_sin(1, 110), 4), alpha=lambda t: 0.75 + 0.25 * math.sin(TAU * 4 * t),
                   decor=[_P("line", 9, "drift", ((190, 200, 255),), (24, 44), 2.0, "back")]),
    "hero_pose": _spec(y=lambda t: -14 + 6 * math.sin(TAU * t),
                       sx=lambda t: 1 + 0.05 * _pulse(t, 1, 2),
                       sy=lambda t: 1 + 0.07 * _pulse(t, 1, 2),
                       decor=[_P("star4", 9, "twinkle", GOLD, (8, 15), 1.1, "back"),
                              _A("rays", "back")]),
    "race": _spec(x=_sin(28, 3), y=_sin(23, 2),
                  decor=[_P("line", 14, "drift", WHITE, (30, 60), 2.6, "back")]),
    "weightlift": _spec(x=_sin(17, 5), sy=lambda t: 1 - 0.13 * _pulse(t, 1, 2),
                        sx=lambda t: 1 + 0.09 * _pulse(t, 1, 2),
                        y=lambda t: 8 * _pulse(t, 1, 2), shadow=True,
                        decor=[_P("sweat", 8, "burst", BLUE, (7, 12), 1.5, "front")]),
    "football": _spec(y=lambda t: _hop(t, 2, 36), shadow=True,
                      decor=[_A("ball", "front")]),
    "basketball": _spec(sy=lambda t: 1 - 0.13 * _land(t, 2),
                        y=lambda t: _hop(t, 2, 18), shadow=True,
                        decor=[_A("ball2", "front")]),
    # --- праздник -------------------------------------------------------------
    "winner": _spec(y=lambda t: _hop(t, 2, 56), rot=_sin(1, 3), shadow=True,
                    decor=[_P("confetti", 16, "fall", RAINBOW, (7, 12), 1.2, "front"),
                           _P("star4", 9, "twinkle", GOLD, (9, 16), 1.2, "back")]),
    "money": _spec(x=_sin(1, 8), y=lambda t: -abs(math.sin(TAU * 2 * t)) * 26,
                   rot=_sin(1, 5), shadow=True,
                   decor=[_P("coin", 12, "fall", GOLD, (10, 17), 1.1, "back"),
                          _P("confetti", 8, "fall", ((110, 220, 130),), (8, 13), 1.0, "front")]),
    "party": _spec(y=lambda t: _hop(t, 2, 40), rot=_sin(2, 7), shadow=True,
                   decor=[_P("confetti", 18, "burst", RAINBOW, (7, 12), 1.3, "front")]),
    "fireworks": _spec(y=_sin(1, 8),
                       decor=[_P("star4", 16, "burst", RAINBOW, (8, 16), 1.1, "back"),
                              _P("circle", 12, "burst", RAINBOW, (5, 10), 1.5, "back")]),
    "gift_shake": _spec(x=_sin(10, 5), rot=_sin(10, 3),
                        sx=lambda t: 1 + 0.16 * _pulse(t, 1, 8),
                        sy=lambda t: 1 + 0.16 * _pulse(t, 1, 8),
                        decor=[_P("star4", 8, "twinkle", GOLD, (8, 14), 1.5, "front")]),
    "champagne": _spec(x=_sin(12, 6),
                       sx=lambda t: 1 + 0.10 * _pulse(t, 1, 6),
                       decor=[_P("bubble", 16, "burst", ((255, 240, 190),), (5, 11), 1.6, "front")]),
    "crown": _spec(rot=_sin(1, 4), y=_sin(1, 7),
                   sx=lambda t: 1 + 0.04 * _pulse(t, 1, 2),
                   decor=[_A("crown", "front"),
                          _P("star4", 7, "twinkle", GOLD, (8, 14), 1.0, "back")]),
    "medal": _spec(y=lambda t: _hop(t, 2, 34), shadow=True,
                   decor=[_P("star4", 8, "orbit", GOLD, (8, 14), 1.3, "back")]),
    "cheers": _spec(y=lambda t: -20 * _pulse(t, 2, 2) + _sin(1, 5)(t),
                    rot=_sin(2, 4),
                    decor=[_P("bubble", 8, "rise", ((255, 240, 190),), (5, 10), 1.0, "front")]),
    "cake": _spec(rot=_sin(1, 5), y=_sin(1, 6),
                  decor=[_A("candles", "front"),
                         _P("star4", 7, "twinkle", GOLD, (8, 13), 1.0, "back")]),
    "balloons": _spec(y=_sin(1, 18), x=_sin(0.5, 12), rot=_sin(1, 4),
                      decor=[_A("balloon", "back")]),
    # --- природа и погода -----------------------------------------------------
    "rain": _spec(rot=_sin(1, 4), y=_sin(1, 6),
                  decor=[_P("drop", 18, "fall", BLUE, (6, 11), 1.9, "front")]),
    "snow": _spec(rot=_sin(1, 4), y=_sin(1, 7), x=_sin(1, 8),
                  decor=[_P("circle", 16, "fall", WHITE, (4, 9), 0.7, "front")]),
    "sunny": _spec(y=_sin(1, 8), sx=lambda t: 1 + 0.04 * _pulse(t, 1),
                   decor=[_A("rays", "back"),
                          _P("star4", 6, "twinkle", GOLD, (8, 13), 1.0, "front")]),
    "rainbow_arc": _spec(y=_sin(1, 14), x=_sin(1, 10),
                         decor=[_A("rainbow", "back"),
                                _P("star4", 6, "twinkle", WHITE, (7, 12), 0.9, "front")]),
    "autumn": _spec(rot=_sin(1, 6), x=_sin(1, 14),
                    decor=[_P("leaf", 11, "fall", ((240, 150, 60), (230, 110, 50), (250, 190, 80)), (9, 16), 0.8, "front")]),
    "spring": _spec(y=_sin(1, 10), rot=_sin(1, 4),
                    decor=[_P("petal", 11, "drift", PINK, (8, 14), 0.7, "front")]),
    "ocean": _spec(y=_sin(2, 14), rot=_sin(1, 7), x=_sin(1, 10),
                   decor=[_A("splash", "front"),
                          _P("bubble", 7, "rise", BLUE, (5, 11), 0.8, "back")]),
    "wind": _spec(rot=lambda t: 10 + 5 * math.sin(TAU * 2 * t), x=_sin(2, 12),
                  decor=[_P("line", 9, "drift", WHITE, (26, 48), 1.8, "back"),
                         _P("leaf", 6, "drift", ((140, 210, 120),), (8, 14), 1.6, "front")]),
    "night": _spec(y=_sin(1, 12), rot=_sin(1, 3),
                   decor=[_A("moon", "back"),
                          _P("star4", 12, "twinkle", ((200, 215, 255),), (6, 12), 0.9, "back")]),
    "storm": _spec(x=_sin(14, 7),
                   decor=[_P("drop", 14, "fall", BLUE, (6, 11), 2.0, "back"),
                          _A("bolt", "front"), _A("flash", "front")]),
    "campfire": _spec(y=_sin(1, 7),
                      decor=[_A("flame", "front"),
                             _P("star4", 7, "rise", ((255, 170, 80),), (6, 11), 1.0, "front")]),
    "freeze": _spec(x=_sin(22, 3), rot=_sin(22, 1.5),
                    tint=((150, 200, 255), lambda t: 0.15),
                    decor=[_P("circle", 10, "fall", WHITE, (4, 8), 0.6, "front")]),
    # --- магия и космос ---------------------------------------------------------
    "rocket": _spec(x=_sin(3, 12), y=lambda t: -22 - 10 * math.sin(TAU * t) + 6 * math.sin(TAU * 3 * t),
                    rot=_sin(3, 7),
                    decor=[_A("flame", "front"),
                           _P("star4", 13, "fall", WHITE, (6, 12), 1.6, "back")]),
    "portal": _spec(y=_sin(1, 17), rot=_sin(1, 5),
                    sx=lambda t: 1 + 0.03 * math.sin(TAU * t),
                    decor=[_P("ring", 5, "orbit", ((170, 110, 255), (110, 190, 255)), (8, 14), 1.1, "back"),
                           _P("star4", 8, "twinkle", ((200, 160, 255),), (7, 12), 1.0, "front")]),
    "magic": _spec(y=_sin(1, 13), rot=_sin(1, 4),
                   decor=[_P("star4", 14, "burst", ((255, 230, 150), (190, 160, 255)), (7, 14), 1.2, "front")]),
    "ufo": _spec(y=lambda t: -30 + 8 * math.sin(TAU * t), x=_sin(1, 16),
                 rot=_sin(1, 5),
                 decor=[_A("beam", "back"),
                        _P("star4", 8, "twinkle", WHITE, (6, 11), 0.8, "back")]),
    "comet": _spec(x=_sin(1, 66), y=lambda t: -30 * math.sin(TAU * t), rot=_sin(1, 9),
                   decor=[_P("star4", 10, "drift", ((170, 220, 255),), (6, 12), 1.2, "back")]),
    "orbit": _spec(x=_sin(1, 30), y=_sin(2, 15), rot=_sin(1, 10),
                   decor=[_P("circle", 4, "orbit", GOLD, (7, 12), 1.0, "back")]),
    "astronaut": _spec(y=_sin(0.5, 20), x=_sin(0.5, 15),
                       rot=lambda t: 14 * math.sin(TAU * 0.5 * t),
                       decor=[_P("star4", 9, "twinkle", WHITE, (6, 11), 0.7, "back")]),
    "witch": _spec(x=_sin(1, 48), y=lambda t: -18 * math.sin(TAU * t) - 8, rot=_sin(1, 7),
                   decor=[_P("star4", 9, "drift", ((200, 170, 255),), (6, 12), 1.1, "back")]),
    "crystal": _spec(sx=lambda t: 1 + 0.07 * _pulse(t, 1), y=_sin(1, 6),
                     decor=[_P("ring", 4, "burst", ((170, 130, 255),), (8, 13), 0.9, "back"),
                            _P("star4", 7, "twinkle", ((220, 190, 255),), (7, 12), 1.0, "front")]),
    "potion": _spec(rot=_sin(2, 5), y=_sin(2, 5),
                    tint=((140, 255, 170), lambda t: 0.10 + 0.06 * math.sin(TAU * 2 * t)),
                    decor=[_P("bubble", 13, "rise", ((150, 255, 180),), (5, 12), 1.0, "front")]),
    "dream": _spec(y=_sin(1, 15), rot=_sin(1, 4), x=_sin(0.5, 10),
                   decor=[_P("bubble", 6, "rise", WHITE, (10, 20), 0.5, "front"),
                          _P("star4", 6, "twinkle", ((190, 200, 255),), (7, 12), 0.8, "back")]),
    "time_warp": _spec(rot=lambda t: 10 * math.sin(TAU * 0.5 * t),
                       x=lambda t: 16 * math.sin(TAU * 0.5 * t),
                       decor=[_P("ring", 3, "orbit", WHITE, (7, 11), 0.4, "back")]),
    "sparkle_clean": _spec(sx=lambda t: 1 + 0.05 * _pulse(t, 2), y=_sin(1, 6),
                           decor=[_P("star4", 12, "twinkle", ((255, 255, 220),), (9, 17), 1.7, "front")]),
    # --- экшн ---------------------------------------------------------------------
    "cool": _spec(rot=_sin(1, 4), y=lambda t: _hop(t, 2, 14),
                  sx=lambda t: 1 + 0.05 * _pulse(t, 2, 2), shadow=True,
                  decor=[_P("star4", 6, "twinkle", GOLD, (8, 14), 1.1, "back")]),
    "superhero": _spec(y=lambda t: -20 + 7 * math.sin(TAU * t),
                       sx=lambda t: 1 + 0.06 * _pulse(t, 1, 2),
                       decor=[_P("line", 8, "drift", ((170, 200, 255),), (26, 48), 1.7, "back"),
                              _P("star4", 7, "twinkle", GOLD, (8, 13), 1.0, "front")]),
    "sneak": _spec(sy=lambda t: 1 - 0.14 * (0.5 - 0.5 * math.cos(TAU * 2 * t)),
                   y=lambda t: 10 * (0.5 - 0.5 * math.cos(TAU * 2 * t)),
                   x=_sin(2, 10),
                   decor=[_P("quest", 2, "twinkle", WHITE, (13, 19), 0.8, "front")]),
    "fishing": _spec(rot=_sin(1, 5), y=_sin(2, 9),
                     decor=[_P("ring", 3, "burst", BLUE, (7, 12), 0.8, "front"),
                            _P("drop", 5, "burst", BLUE, (6, 11), 1.0, "front")]),
    "idea": _spec(y=lambda t: _hop(t, 1, 26), shadow=True,
                  decor=[_A("bulb", "front"),
                         _P("star4", 6, "burst", GOLD, (7, 12), 1.2, "front")]),
    "alarm": _spec(x=_sin(18, 6), rot=_sin(18, 3),
                   decor=[_A("bells", "front"),
                          _P("bang", 3, "twinkle", ((255, 100, 100),), (18, 27), 1.6, "front")]),
    "photo_flash": _spec(decor=[_A("flash", "front"),
                                 _P("star4", 7, "burst", WHITE, (8, 14), 1.4, "front")],
                         sx=lambda t: 1 + 0.08 * _pulse(t, 1, 7)),
    "heartbeat_panic": _spec(x=_sin(12, 7),
                             sx=lambda t: 1 + 0.13 * _pulse(t, 3, 4),
                             sy=lambda t: 1 + 0.13 * _pulse(t, 3, 4),
                             decor=[_P("sweat", 6, "burst", BLUE, (7, 12), 1.6, "front")]),
}

DEFAULT_EFFECT = "bounce"


def _val(v, t: float) -> float:
    return float(v(t)) if callable(v) else float(v)


def _sample_params(spec: dict, t: float) -> dict:
    return {"x": _val(spec.get("x", 0), t), "y": _val(spec.get("y", 0), t),
            "rot": _val(spec.get("rot", 0), t), "sx": _val(spec.get("sx", 1), t),
            "sy": _val(spec.get("sy", 1), t), "alpha": _val(spec.get("alpha", 1), t)}


# ------------------------------------------------------------------ частицы
def _star(d, cx, cy, s, color, points=4, rot=0.0) -> None:
    pts = []
    for i in range(points * 2):
        r = s if i % 2 == 0 else s * 0.42
        a = rot + i * math.pi / points - math.pi / 2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=color)


def _heart(d, cx, cy, s, color) -> None:
    d.ellipse([cx - s, cy - s * 0.9, cx, cy + s * 0.1], fill=color)
    d.ellipse([cx, cy - s * 0.9, cx + s, cy + s * 0.1], fill=color)
    d.polygon([(cx - s * 0.95, cy), (cx + s * 0.95, cy), (cx, cy + s * 1.2)], fill=color)


def _drop(d, cx, cy, s, color, outline=False) -> None:
    pts = [(cx, cy - s * 1.2), (cx + s * 0.75, cy + s * 0.3),
           (cx + s * 0.45, cy + s), (cx - s * 0.45, cy + s),
           (cx - s * 0.75, cy + s * 0.3)]
    if outline:
        d.polygon(pts, outline=color, width=2)
    else:
        d.polygon(pts, fill=color)


def _note(d, cx, cy, s, color) -> None:
    d.ellipse([cx - s * 0.7, cy + s * 0.3, cx + s * 0.2, cy + s], fill=color)
    d.line([cx + s * 0.15, cy + s * 0.6, cx + s * 0.15, cy - s * 0.9], fill=color, width=3)
    d.polygon([(cx + s * 0.15, cy - s * 0.9), (cx + s * 0.85, cy - s * 0.55),
               (cx + s * 0.15, cy - s * 0.25)], fill=color)


def _coin(d, cx, cy, s, color) -> None:
    d.ellipse([cx - s, cy - s, cx + s, cy + s], fill=color)
    inner = tuple(max(0, c - 60) for c in color[:3]) + (color[3],)
    d.ellipse([cx - s * 0.55, cy - s * 0.55, cx + s * 0.55, cy + s * 0.55], outline=inner, width=2)


def _confetti(d, cx, cy, s, color, ang) -> None:
    w, h = s * 1.5, s * 0.8
    pts = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        pts.append((cx + dx * math.cos(ang) - dy * math.sin(ang),
                    cy + dx * math.sin(ang) + dy * math.cos(ang)))
    d.polygon(pts, fill=color)


def _petal(d, cx, cy, s, color, ang, leaf=False) -> None:
    pts = []
    for k in range(13):
        a = k / 12 * TAU
        r = s * (0.45 + 0.55 * abs(math.cos(a)))
        x, y = cx + r * math.cos(a) * 0.62, cy + r * math.sin(a)
        pts.append((cx + (x - cx) * math.cos(ang) - (y - cy) * math.sin(ang),
                    cy + (x - cx) * math.sin(ang) + (y - cy) * math.cos(ang)))
    d.polygon(pts, fill=color)


def _shape(d, kind, x, y, s, color, ang=0.0, frame=0) -> None:
    if kind == "star4":
        _star(d, x, y, s, color, 4, ang)
    elif kind == "star5":
        _star(d, x, y, s, color, 5, ang)
    elif kind == "heart":
        _heart(d, x, y, s * 0.8, color)
    elif kind == "circle":
        d.ellipse([x - s * 0.6, y - s * 0.6, x + s * 0.6, y + s * 0.6], fill=color)
    elif kind == "ring":
        d.ellipse([x - s, y - s, x + s, y + s], outline=color, width=max(2, int(s * 0.22)))
    elif kind in ("drop", "sweat"):
        _drop(d, x, y, s * 0.8, color, outline=(kind == "sweat"))
    elif kind == "note":
        _note(d, x, y, s, color)
    elif kind == "coin":
        _coin(d, x, y, s * 0.8, color)
    elif kind == "confetti":
        _confetti(d, x, y, s, color, ang)
    elif kind in ("petal", "leaf"):
        _petal(d, x, y, s, color, ang, leaf=(kind == "leaf"))
    elif kind == "bubble":
        d.ellipse([x - s * 0.7, y - s * 0.7, x + s * 0.7, y + s * 0.7], outline=color, width=2)
        d.ellipse([x - s * 0.35, y - s * 0.4, x - s * 0.05, y - s * 0.1], fill=color)
    elif kind == "line":
        d.line([x - s, y, x + s, y], fill=color, width=max(2, int(s * 0.16)))
    elif kind == "puff":
        d.ellipse([x - s, y - s * 0.6, x + s, y + s * 0.6], fill=color)
    elif kind == "flame":
        d.polygon([(x - s * 0.7, y + s * 0.6), (x + s * 0.7, y + s * 0.6),
                   (x, y - s * 1.1)], fill=color)
    elif kind in ("zzz", "bang", "quest"):
        ch = {"zzz": "Z", "bang": "!", "quest": "?"}[kind]
        try:
            font = ImageFont.load_default(size=int(s * 2.1))
        except Exception:
            font = ImageFont.load_default()
        d.text((x, y), ch, font=font, fill=color, anchor="mm")
    else:
        _star(d, x, y, s, color, 4, ang)


def _layer_particles(layer: dict, seed: int) -> list[dict]:
    rng = random.Random(seed)
    area = layer.get("area") or (30, CANVAS - 30, 30, CANVAS - 30)
    parts = []
    for _ in range(layer["n"]):
        smin, smax = layer["size"]
        parts.append({
            "x": rng.uniform(area[0], area[1]), "y": rng.uniform(area[2], area[3]),
            "size": rng.uniform(smin, smax), "phase": rng.random(),
            "speed": rng.uniform(0.75, 1.3), "drift": rng.uniform(4, 20),
            "r": rng.uniform(90, 215), "ang": rng.uniform(0, TAU),
            "color": rng.choice(layer["colors"]),
            "spin": rng.uniform(-2.5, 2.5),
        })
    return parts


def _draw_particles(d, layer: dict, parts: list[dict], t: float, frame: int) -> None:
    cx = cy = CANVAS / 2
    for p in parts:
        mode = layer["mode"]
        base_alpha = layer.get("alpha", 210)
        if mode == "rise":
            y = (p["y"] - t * layer["speed"] * p["speed"] * CANVAS) % CANVAS
            x = p["x"] + math.sin(TAU * t * 1.3 + p["phase"] * TAU) * p["drift"]
            a = base_alpha
        elif mode == "fall":
            y = (p["y"] + t * layer["speed"] * p["speed"] * CANVAS) % CANVAS
            x = p["x"] + math.sin(TAU * t * 1.3 + p["phase"] * TAU) * p["drift"]
            a = base_alpha
        elif mode == "drift":
            x = (p["x"] + t * layer["speed"] * p["speed"] * CANVAS * 0.6) % CANVAS
            y = p["y"] + math.sin(TAU * t + p["phase"] * TAU) * p["drift"]
            a = base_alpha
        elif mode == "orbit":
            ang = p["phase"] * TAU + TAU * t * layer["speed"] * p["speed"]
            x = cx + math.cos(ang) * p["r"]
            y = cy - 16 + math.sin(ang) * p["r"] * 0.8
            a = base_alpha
        elif mode == "burst":
            cyc = (t * layer["speed"] * p["speed"] + p["phase"]) % 1.0
            r = cyc * p["r"]
            x = cx + math.cos(p["ang"]) * r
            y = cy - 10 + math.sin(p["ang"]) * r
            a = int(base_alpha * math.sin(math.pi * cyc))
        elif mode == "fountain":
            cyc = (t * layer["speed"] * p["speed"] + p["phase"]) % 1.0
            x = p["x"] + (p["phase"] - 0.5) * 90 * cyc
            y = CANVAS - 60 - math.sin(math.pi * cyc) * 130 * p["speed"]
            a = int(base_alpha * math.sin(math.pi * cyc))
        else:  # twinkle
            x, y = p["x"], p["y"]
            a = int(base_alpha * (0.3 + 0.7 * abs(math.sin(TAU * t * layer["speed"] * p["speed"] + p["phase"] * TAU))))
        if a <= 4:
            continue
        color = p["color"][:3] + (int(a),)
        size = p["size"] * (1 + 0.15 * math.sin(TAU * t + p["phase"] * TAU))
        _shape(d, layer["kind"], x, y, size, color, ang=p["spin"] * t * TAU, frame=frame)


# ------------------------------------------------------------------ якоря
def _draw_anchor(canvas: Image.Image, layer: dict, box, t: float) -> None:
    x0, y0, x1, y1 = box
    cx, w, h = (x0 + x1) / 2, x1 - x0, y1 - y0
    d = ImageDraw.Draw(canvas, "RGBA")
    kind = layer["kind"]
    flick = 1 + 0.22 * math.sin(t * TAU * 7)
    if kind == "flame":  # пламя под персонажем (ракета/костёр)
        fh = h * 0.34 * flick
        d.polygon([(cx - w * 0.16, y1 - 4), (cx + w * 0.16, y1 - 4),
                   (cx, y1 + fh)], fill=(255, 120, 20, 225))
        d.polygon([(cx - w * 0.08, y1 - 2), (cx + w * 0.08, y1 - 2),
                   (cx, y1 + fh * 0.6)], fill=(255, 210, 60, 245))
    elif kind == "crown":
        cw, ch = w * 0.52, h * 0.20
        top = y0 - ch - 10 - 4 * math.sin(TAU * t)
        pts = [(cx - cw / 2, top + ch), (cx - cw / 2, top + ch * 0.3),
               (cx - cw / 4, top + ch * 0.65), (cx, top), (cx + cw / 4, top + ch * 0.65),
               (cx + cw / 2, top + ch * 0.3), (cx + cw / 2, top + ch)]
        d.polygon(pts, fill=(255, 200, 50, 245))
        d.ellipse([cx - 5, top + ch * 0.55, cx + 5, top + ch * 0.55 + 10], fill=(255, 90, 120, 255))
    elif kind == "halo":
        ry = y0 - 16 - 4 * math.sin(TAU * t)
        d.ellipse([cx - w * 0.24, ry - 10, cx + w * 0.24, ry + 10],
                  outline=(255, 220, 90, 230), width=6)
    elif kind == "splash":
        for k in range(5):
            a = math.pi * (0.15 + 0.175 * k)
            r = w * (0.30 + 0.10 * math.sin(TAU * t + k))
            x, y = cx + math.cos(a) * r * 1.4, y1 - abs(math.sin(a)) * h * 0.24
            _drop(d, x, y, 9 + 3 * math.sin(TAU * t + k * 1.3), (120, 190, 255, 210))
        d.arc([cx - w * 0.42, y1 - 18, cx + w * 0.42, y1 + 16], 180, 360,
              fill=(150, 205, 255, 200), width=5)
    elif kind == "glowpad":
        d.ellipse([cx - w * 0.42, y1 + 2, cx + w * 0.42, y1 + 26],
                  fill=(170, 130, 255, int(70 + 30 * math.sin(TAU * t))))
    elif kind == "rays":  # вращающиеся лучи за спиной
        for k in range(12):
            a = k * TAU / 12 + t * TAU * 0.5
            x, y = cx + math.cos(a) * w * 0.85, (y0 + y1) / 2 + math.sin(a) * h * 0.85
            d.line([cx, (y0 + y1) / 2, x, y], fill=(255, 220, 90, 60), width=13)
    elif kind == "rainbow":
        cols = [(255, 90, 90), (255, 170, 60), (255, 230, 90),
                (110, 220, 120), (90, 170, 255)]
        for k, col in enumerate(cols):
            r = w * (0.62 + 0.09 * k)
            d.arc([cx - r, y1 - r * 1.35, cx + r, y1 + r * 0.35], 180, 360,
                  fill=col + (190,), width=11)
    elif kind == "moon":
        mx, my, r = x1 - 66, 78, 30
        d.ellipse([mx - r, my - r, mx + r, my + r], fill=(240, 240, 210, 255))
        d.ellipse([mx - r * 0.35, my - r * 1.05, mx + r * 1.05, my + r * 0.35],
                  fill=(0, 0, 0, 0))
    elif kind == "beam":  # луч НЛО сверху
        top_w, bot_w = w * 0.24, w * 0.95
        grad = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        gd.polygon([(cx - top_w, 0), (cx + top_w, 0),
                    (cx + bot_w, y1), (cx - bot_w, y1)], fill=(190, 255, 190, 66))
        canvas.alpha_composite(grad.filter(ImageFilter.GaussianBlur(8)))
    elif kind == "bolt":
        bx, by = x1 - 60, y0 - 26
        d.polygon([(bx + 14, by), (bx - 8, by + 34), (bx + 6, by + 34),
                   (bx - 12, by + 62), (bx + 22, by + 26), (bx + 8, by + 26)],
                  fill=(255, 225, 90, 245))
    elif kind == "flash":
        pulse = max(0.0, 1 - abs(((t * 2) % 1.0) - 0.5) * 14)
        if pulse > 0.02:
            overlay = Image.new("RGBA", (CANVAS, CANVAS), (255, 255, 255, int(120 * pulse)))
            canvas.alpha_composite(overlay)
    elif kind == "vein":  # вздутая венка злости
        vx, vy = x1 - 34, y0 + 8
        for a in (0.4, 1.2, 2.0, 2.8):
            d.line([vx, vy, vx + 17 * math.cos(a), vy + 17 * math.sin(a)],
                   fill=(255, 70, 60, 240), width=5)
        d.ellipse([vx - 6, vy - 6, vx + 6, vy + 6], fill=(255, 70, 60, 240))
    elif kind == "blush":
        for sgn in (-1, 1):
            bx = cx + sgn * w * 0.27
            by = y0 + h * 0.44
            d.ellipse([bx - 17, by - 10, bx + 17, by + 10], fill=(255, 130, 150, 110))
    elif kind == "lips":
        lx, ly = x1 - 26, y0 + h * 0.45
        d.ellipse([lx - 15, ly - 8, lx + 2, ly + 5], fill=(255, 80, 130, 235))
        d.ellipse([lx - 2, ly - 8, lx + 15, ly + 5], fill=(255, 80, 130, 235))
    elif kind == "ghost":
        gx, gy = x1 - 58, y0 - 64 - 7 * math.sin(TAU * t)
        d.rounded_rectangle([gx - 17, gy - 18, gx + 17, gy + 12], 15, fill=(235, 240, 255, 200))
        for k in range(3):
            d.ellipse([gx - 17 + k * 12, gy + 4, gx - 5 + k * 12, gy + 18], fill=(235, 240, 255, 200))
        d.ellipse([gx - 9, gy - 8, gx - 3, gy - 1], fill=(90, 90, 120, 255))
        d.ellipse([gx + 3, gy - 8, gx + 9, gy - 1], fill=(90, 90, 120, 255))
    elif kind == "cross":  # большой красный X
        bx, by = x1 - 58, y0 - 20
        d.line([bx - 16, by - 16, bx + 16, by + 16], fill=(255, 70, 70, 240), width=9)
        d.line([bx - 16, by + 16, bx + 16, by - 16], fill=(255, 70, 70, 240), width=9)
    elif kind == "ringfloat":
        ry = y0 - 27 - 5 * math.sin(TAU * t)
        d.ellipse([cx - 26, ry - 11, cx + 26, ry + 11], outline=(90, 200, 120, 235), width=6)
    elif kind == "rope":  # скакалка дугой
        sw = math.sin(TAU * 3 * t)
        bbox = [cx - w * 0.62, y0 - h * 0.2 + 60 * sw, cx + w * 0.62, y1 + 8 + 60 * sw]
        d.arc(bbox, 0, 180, fill=(255, 255, 255, 160), width=4)
    elif kind == "ball":
        by = y1 - 16 - abs(math.sin(TAU * 2 * t)) * 66
        d.ellipse([cx + w * 0.28, by - 17, cx + w * 0.28 + 34, by + 17],
                  fill=(245, 245, 245, 255), outline=(60, 60, 60, 255), width=3)
        d.ellipse([cx + w * 0.28 + 11, by - 6, cx + w * 0.28 + 23, by + 6], fill=(60, 60, 60, 255))
    elif kind == "ball2":
        by = y1 - 14 - abs(math.sin(TAU * 2 * t)) * 46
        bx = cx + w * 0.30
        d.ellipse([bx, by - 16, bx + 32, by + 16], fill=(255, 140, 60, 255),
                  outline=(160, 80, 20, 255), width=2)
        d.arc([bx + 4, by - 16, bx + 28, by + 16], 90, 270, fill=(160, 80, 20, 255), width=2)
    elif kind == "candles":
        for k, dx in enumerate((-0.16, 0.0, 0.16)):
            fx, fy = cx + w * dx, y0 - 30 - 5 * math.sin(TAU * 3 * t + k * 2.1)
            d.polygon([(fx - 6, fy + 12), (fx + 6, fy + 12), (fx, fy - 10 * flick)],
                      fill=(255, 170, 60, 245))
            d.ellipse([fx - 3, fy - 2, fx + 3, fy + 9], fill=(255, 225, 130, 255))
    elif kind == "balloon":
        bx, by = x1 - 40, y0 - 84 - 8 * math.sin(TAU * t)
        d.line([cx + w * 0.2, y0 + 8, bx, by + 30], fill=(255, 255, 255, 150), width=2)
        d.ellipse([bx - 24, by - 30, bx + 24, by + 30], fill=(255, 110, 150, 235))
    elif kind == "bulb":
        bx, by = cx + w * 0.30, y0 - 48 - 5 * math.sin(TAU * 2 * t)
        d.ellipse([bx - 17, by - 17, bx + 17, by + 17], fill=(255, 230, 120, 245))
        d.rectangle([bx - 6, by + 15, bx + 6, by + 24], fill=(170, 170, 170, 255))
    elif kind == "bells":
        for sgn in (-1, 1):
            bx, by = cx + sgn * w * 0.33, y0 - 20 + 4 * math.sin(TAU * 9 * t + sgn)
            d.ellipse([bx - 13, by - 11, bx + 13, by + 9], fill=(255, 200, 70, 245))
            d.ellipse([bx - 4, by + 7, bx + 4, by + 14], fill=(220, 160, 50, 255))


def _shadow(canvas: Image.Image, cx: float, ground_y: float, w: float,
            height_frac: float) -> None:
    sh = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sw = w * (1 - 0.38 * height_frac)
    a = int(105 * (1 - 0.55 * height_frac))
    sd.ellipse([cx - sw / 2, ground_y - 13, cx + sw / 2, ground_y + 13],
               fill=(20, 16, 40, max(0, a)))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(7)))


def render_frames(subject: Image.Image, effect: str, fps: int = 30,
                  duration: float = 2.8) -> Iterator[Image.Image]:
    """Генератор RGBA-кадров 512x512 (ленивый — кадры не копим в памяти)."""
    spec = EFFECTS.get(effect) or EFFECTS[DEFAULT_EFFECT]
    seed = zlib.crc32(effect.encode())
    layers = []
    for li, layer in enumerate(spec["decor"]):
        if layer.get("anchor"):
            layers.append((layer, None))
        else:
            layers.append((layer, _layer_particles(layer, seed + li * 977)))
    glow = spec.get("glow")
    tint = spec.get("tint")
    n = max(2, int(fps * duration))
    cx = cy = CANVAS / 2
    base_half_h = subject.size[1] / 2
    ground_y = min(CANVAS - 26, cy + base_half_h + 34)
    for i in range(n):
        t = i / n
        prm = _sample_params(spec, t)
        frame = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        draw = ImageDraw.Draw(frame, "RGBA")
        # трансформация персонажа
        w = max(1, int(subject.size[0] * prm["sx"]))
        h = max(1, int(subject.size[1] * prm["sy"]))
        obj = subject.resize((w, h), Image.Resampling.LANCZOS)
        if prm["rot"]:
            obj = obj.rotate(prm["rot"], resample=Image.Resampling.BICUBIC, expand=True)
        if tint:
            color, fn = tint
            strength = max(0.0, min(0.45, float(fn(t))))
            solid = Image.new("RGBA", obj.size, color[:3] + (255,))
            solid.putalpha(obj.split()[3])
            obj = Image.blend(obj, solid, strength)
        if prm["alpha"] < 0.999:
            a = obj.split()[3].point(lambda v: int(v * max(0.0, prm["alpha"])))
            obj.putalpha(a)
        ox = int(cx + prm["x"] - obj.size[0] / 2)
        oy = int(cy + prm["y"] - obj.size[1] / 2)
        box = (ox, oy, ox + obj.size[0], oy + obj.size[1])
        # задний декор
        for layer, parts in layers:
            if layer["layer"] != "back":
                continue
            if parts is None:
                _draw_anchor(frame, layer, box, t)
            else:
                _draw_particles(draw, layer, parts, t, i)
        if glow:
            g = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
            sil = Image.new("RGBA", obj.size, glow[:3] + (255,))
            sil.putalpha(obj.split()[3].filter(ImageFilter.GaussianBlur(6)))
            g.alpha_composite(sil, (ox, oy))
            frame.alpha_composite(g.filter(ImageFilter.GaussianBlur(4)))
            draw = ImageDraw.Draw(frame, "RGBA")
        if spec["shadow"]:
            _shadow(frame, cx + prm["x"], ground_y, subject.size[0] * 0.92,
                    max(0.0, min(1.0, -prm["y"] / 130)))
        frame.alpha_composite(obj, (ox, oy))
        # передний декор
        for layer, parts in layers:
            if layer["layer"] != "front":
                continue
            if parts is None:
                _draw_anchor(frame, layer, box, t)
            else:
                _draw_particles(draw, layer, parts, t, i)
        yield frame
