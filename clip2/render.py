"""Energetic beat-synced clip: 1080x1920, 30 fps, 149.36 s.

Sources: 7 AI videos + 2 photos + the supplied track.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
SRC = os.path.join(ASSETS, "src")
PHOTOS = os.path.join(ASSETS, "photos")
MEDIA = os.path.join(HERE, "media")
TMP = os.path.join(HERE, "tmp")

W, H, FPS = 1080, 1920, 30
DUR = 149.36
CARD = 1000          # working size of the framed card
PHOTO = 912

FF = subprocess.run(["python3", "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
                    capture_output=True, text=True).stdout.strip()

FONT_BOLD = os.path.join(ASSETS, "fonts", "RussoOne-Regular.ttf")
FONT_COND = os.path.join(ASSETS, "fonts", "Oswald.ttf")

BEATS = np.array(json.load(open(os.path.join(ASSETS, "beats.json")))["beats"], float)
BEATS = BEATS - 0.055
DOWNS = BEATS[3::4]


# --------------------------------------------------------------------------- utils
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def back_out(x, k=2.1):
    x = clamp(x)
    return 1 + (k + 1) * (x - 1) ** 3 + k * (x - 1) ** 2


def pulse(t, decay=7.0):
    k = np.searchsorted(BEATS, t, side="right")
    if k == 0:
        return 0.0
    return math.exp(-decay * (t - BEATS[k - 1]))


def down_pulse(t, decay=5.0):
    k = np.searchsorted(DOWNS, t, side="right")
    if k == 0:
        return 0.0
    return math.exp(-decay * (t - DOWNS[k - 1]))


def nearest_beat(t):
    return float(BEATS[int(np.argmin(np.abs(BEATS - t)))])


# --------------------------------------------------------------------------- art
GRADES = {
    "cold": dict(mul=(0.92, 1.02, 1.12), sat=0.85, contrast=1.10),
    "hot": dict(mul=(0.98, 0.94, 1.10), sat=1.22, contrast=1.16),
    "red": dict(mul=(0.80, 0.86, 1.25), sat=1.30, contrast=1.22),
    "teal": dict(mul=(1.10, 1.00, 0.94), sat=1.05, contrast=1.10),
    "green": dict(mul=(0.92, 1.06, 0.95), sat=1.18, contrast=1.12),
    "blue": dict(mul=(1.14, 0.96, 0.88), sat=1.05, contrast=1.14),
    "bw": dict(mul=(1.0, 1.0, 1.0), sat=0.0, contrast=1.22),
    "amber": dict(mul=(0.88, 0.98, 1.16), sat=1.15, contrast=1.12),
}


def grade(img, name):
    g = GRADES[name]
    f = img.astype(np.float32)
    m = np.array(g["mul"], np.float32)
    f *= m
    gray = f.mean(2, keepdims=True)
    f = gray + (f - gray) * g["sat"]
    f = (f - 128.0) * g["contrast"] + 128.0
    return np.clip(f, 0, 255).astype(np.uint8)


def cover(img, w, h):
    ih, iw = img.shape[:2]
    s = max(w / iw, h / ih)
    nw, nh = int(round(iw * s)), int(round(ih * s))
    r = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    x = (nw - w) // 2
    y = (nh - h) // 2
    return r[y:y + h, x:x + w]


def rounded_mask(size, radius):
    m = np.zeros((size, size), np.uint8)
    cv2.rectangle(m, (radius, 0), (size - radius, size), 255, -1)
    cv2.rectangle(m, (0, radius), (size, size - radius), 255, -1)
    for cx, cy in ((radius, radius), (size - radius, radius),
                   (radius, size - radius), (size - radius, size - radius)):
        cv2.circle(m, (cx, cy), radius, 255, -1)
    return m


def oval_mask(w, h, feather=3):
    m = np.zeros((h, w), np.uint8)
    cv2.ellipse(m, (w // 2, h // 2), (w // 2 - 2, h // 2 - 2), 0, 0, 360, 255, -1)
    if feather:
        m = cv2.GaussianBlur(m, (0, 0), feather)
    return m


def paste(canvas, sprite, x, y, shadow=True):
    """sprite BGRA, top-left (x, y), soft shadow."""
    h, w = sprite.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(canvas.shape[1], x + w), min(canvas.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    sx0, sy0 = x0 - x, y0 - y
    sub = sprite[sy0:sy0 + (y1 - y0), sx0:sx0 + (x1 - x0)]
    a = sub[..., 3:4].astype(np.float32) / 255.0
    roi = canvas[y0:y1, x0:x1].astype(np.float32)
    if shadow:
        roi *= 1.0 - 0.35 * a
    canvas[y0:y1, x0:x1] = (sub[..., :3].astype(np.float32) * a + roi * (1 - a)).astype(np.uint8)


# --------------------------------------------------------------------------- text
class Kit:
    def __init__(self):
        self.src = {}
        for name in ("office", "wash", "fire", "gas", "storm", "game", "night"):
            self.src[name] = np.load(os.path.join(SRC, name + ".npy"), mmap_mode="r")
        self.photo = {n: cv2.imread(os.path.join(PHOTOS, n + ".png")) for n in ("portrait", "messy")}
        self.texts = {}
        self.card_cache = {}
        self.mask = rounded_mask(PHOTO, 26)
        self.oval = None
        self.vignette = self._vignette()
        self.grain = [np.random.default_rng(i).normal(0, 2.0, (H // 2, W // 2, 1)).astype(np.float32)
                      for i in range(6)]
        self.rays = self._rays()
        self.glows = {}

    @staticmethod
    def _vignette():
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        cx, cy = W / 2, H / 2
        r = np.sqrt(((x - cx) / (W * 0.62)) ** 2 + ((y - cy) / (H * 0.62)) ** 2)
        v = np.clip(1.08 - 0.34 * np.clip(r, 0, 1.6) ** 1.7, 0.55, 1.0)
        return v[..., None].astype(np.float32)

    @staticmethod
    def _rays():
        """Radial speed lines, alpha 0..1, 1080x1920."""
        small = np.zeros((H // 4, W // 4), np.float32)
        cx, cy = small.shape[1] / 2, small.shape[0] / 2
        rng = np.random.default_rng(7)
        for i in range(64):
            a = rng.uniform(0, 2 * math.pi)
            r0 = rng.uniform(0.20, 0.34) * small.shape[1]
            r1 = rng.uniform(0.55, 0.95) * small.shape[1]
            w = rng.uniform(0.6, 2.4)
            x0 = cx + math.cos(a) * r0
            y0 = cy + math.sin(a) * r0
            x1 = cx + math.cos(a) * r1
            y1 = cy + math.sin(a) * r1
            cv2.line(small, (int(x0), int(y0)), (int(x1), int(y1)), 1.0, max(1, int(w)))
        small = cv2.GaussianBlur(small, (0, 0), 1.1)
        return cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]

    # ---------------------------------------------------------------- sprites
    def text(self, s, size, fill=(255, 255, 255), shadow=(255, 212, 0),
             stroke=(12, 12, 14), cond=False, tilt=0.0):
        key = (s, size, fill, shadow, stroke, cond, tilt)
        if key in self.texts:
            return self.texts[key]
        font = ImageFont.truetype(FONT_COND if cond else FONT_BOLD, size)
        stroke_w = max(4, int(size * 0.10))
        pad = stroke_w * 2 + int(size * 0.28)
        if tilt:
            probe = Image.new("L", (10, 10))
            d = ImageDraw.Draw(probe)
            bb = d.textbbox((0, 0), s, font=font, stroke_width=stroke_w)
        else:
            probe = Image.new("L", (10, 10))
            d = ImageDraw.Draw(probe)
            bb = d.textbbox((0, 0), s, font=font, stroke_width=stroke_w)
        tw = bb[2] - bb[0]
        th = bb[3] - bb[1]
        img = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        ox, oy = pad - bb[0], pad - bb[1]
        if shadow is not None:
            off = max(3, int(size * 0.055))
            dr.text((ox + off, oy + off), s, font=font, fill=shadow + (255,),
                    stroke_width=stroke_w, stroke_fill=shadow + (255,))
        dr.text((ox, oy), s, font=font, fill=fill + (255,), stroke_width=stroke_w,
                stroke_fill=stroke + (255,))
        arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGBA2BGRA)
        if tilt:
            hh, ww = arr.shape[:2]
            m = cv2.getRotationMatrix2D((ww / 2, hh / 2), tilt, 1.0)
            cos, sin = abs(m[0, 0]), abs(m[0, 1])
            nw, nh = int(hh * sin + ww * cos), int(hh * cos + ww * sin)
            m[0, 2] += nw / 2 - ww / 2
            m[1, 2] += nh / 2 - hh / 2
            arr = cv2.warpAffine(arr, m, (nw, nh), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        self.texts[key] = arr
        return arr

    # ---------------------------------------------------------------- sources
    def frame(self, name, t):
        if name in self.src:
            arr = self.src[name]
            i = int(round(t * FPS)) % arr.shape[0]
            return np.asarray(arr[i])
        img = self.photo[name]
        return img


# --------------------------------------------------------------------------- shots
def build_shots():
    """Explicit timeline: every block matches the on-screen line."""
    S = []

    def add(a, b, src, mode, grd, off=0.0):
        S.append(dict(a=a, b=b, src=src, mode=mode, grade=grd, off=off))

    # ---------------- 0–16 intro
    add(0.0, 6.9, "office", "card", "cold", 0.0)          # title
    add(6.9, 9.2, "office", "full", "cold", 1.2)          # ОФИСНЫЙ ВОИН
    add(9.2, 11.9, "portrait", "card", "bw", 0.0)         # просто мужик
    teaser = [("gas", "hot"), ("night", "blue"), ("wash", "teal"), ("game", "green"),
              ("storm", "red"), ("fire", "red"), ("gas", "hot"), ("night", "blue")]
    step = (16.0 - 11.9) / len(teaser)
    for i, (n, g) in enumerate(teaser):
        add(11.9 + i * step, 11.9 + (i + 1) * step, n, "full", g, off=(i % 3) * 0.7)

    # ---------------- 16–27.1 chorus 1
    add(16.0, 18.3, "fire", "full", "red", 0.6)           # ЖАРКО!
    add(18.3, 20.6, "fire", "card", "red", 1.4)
    add(20.6, 22.2, "fire", "full", "red", 2.2)           # ЖГИ!
    add(22.2, 23.4, "storm", "full", "red", 1.0)
    add(23.4, 24.5, "gas", "full", "hot", 1.6)
    add(24.5, 25.8, "fire", "quad", "red", 0.4)
    add(25.8, 27.1, "storm", "full", "red", 2.6)

    # ---------------- 27.1–31 break
    add(27.1, 31.0, "wash", "oval", "teal", 0.2)          # СТИРКА ПО-РУССКИ

    # ---------------- 31–43.3 verse
    add(31.0, 33.2, "office", "card", "cold", 0.3)        # РАБОТА КИПИТ
    add(33.2, 35.6, "office", "full", "cold", 1.8)
    add(35.6, 37.5, "gas", "card", "amber", 0.8)          # ЗАПРАВИЛСЯ
    add(37.5, 39.6, "gas", "full", "amber", 1.9)
    add(39.6, 41.3, "gas", "full", "hot", 3.1)            # И ПОЕХАЛ
    add(41.3, 43.3, "office", "card", "cold", 2.4)

    # ---------------- 43.3–45 build
    add(43.3, 45.0, "game", "full", "green", 1.0)         # СИЛА!

    # ---------------- 45–58.1 chorus 2
    add(45.0, 47.3, "fire", "full", "red", 1.0)           # ЖАРКО!
    add(47.3, 49.6, "fire", "quad", "red", 2.0)
    add(49.6, 51.6, "storm", "full", "red", 0.8)          # ЖГИ!
    add(51.6, 53.4, "gas", "full", "hot", 2.2)
    add(53.4, 54.8, "fire", "card", "red", 1.1)
    add(54.8, 56.4, "storm", "full", "red", 2.9)          # ЕЩЁ!
    add(56.4, 58.1, "game", "full", "green", 0.5)

    # ---------------- 58.1–71 groove
    add(58.1, 61.4, "night", "full", "blue", 0.4)         # НОЧНАЯ СМЕНА
    add(61.4, 64.4, "night", "card", "blue", 2.0)
    add(64.4, 67.4, "gas", "full", "amber", 1.2)          # ТИХО ЕДЕМ
    add(67.4, 71.0, "night", "full", "blue", 3.2)         # НО УВЕРЕННО

    # ---------------- 71–74.1 quiet
    add(71.0, 74.1, "portrait", "card", "bw", 0.0)        # ПРОСТО МУЖИК

    # ---------------- 74.1–87 groove 2
    add(74.1, 77.4, "game", "full", "green", 0.6)         # МАГИЯ
    add(77.4, 80.4, "game", "quad", "green", 1.6)
    add(80.4, 83.4, "game", "card", "green", 2.4)         # БЕЗ ПЕРЕРЫВА
    add(83.4, 87.0, "office", "full", "cold", 2.2)        # И СНОВА В БОЙ

    # ---------------- 87–90.1 quiet
    add(87.0, 90.1, "messy", "glitch", "bw", 0.0)         # ВЕТЕР В ХАЕР

    # ---------------- 90.1–102 heavy
    add(90.1, 93.6, "storm", "full", "red", 0.2)          # ГРОЗА
    add(93.6, 96.6, "storm", "card", "red", 1.4)
    add(96.6, 99.6, "fire", "full", "red", 1.8)           # БЬЁТ
    add(99.6, 102.0, "gas", "full", "hot", 2.6)           # ПРЯМО В ЦЕЛЬ

    # ---------------- 102–105.1 quiet
    add(102.0, 105.1, "wash", "oval", "teal", 1.6)        # СТИРКА 2.0

    # ---------------- 105.1–118 heavy 2
    add(105.1, 107.6, "gas", "full", "amber", 0.4)        # ЗАПРАВИЛСЯ
    add(107.6, 109.8, "gas", "card", "amber", 2.2)
    add(109.8, 112.0, "night", "full", "blue", 1.0)       # И ПОЛЕТЕЛ
    add(112.0, 114.0, "game", "full", "green", 1.4)
    add(114.0, 116.2, "night", "card", "blue", 2.6)       # БЕЗ ТОРМОЗОВ
    add(116.2, 118.0, "storm", "full", "red", 3.0)

    # ---------------- 118–134 bridge
    add(118.0, 123.0, "office", "card", "cold", 0.2)      # РАБОТА — ТОЖЕ БОЙ
    add(123.0, 128.0, "office", "full", "cold", 2.0)      # НО МЫ НЕ СДАЁМСЯ
    add(128.0, 131.0, "messy", "glitch", "bw", 0.0)       # ДО КОНЦА
    add(131.0, 134.0, "portrait", "card", "bw", 0.0)

    # ---------------- 134–145.1 final
    fin = [(134.0, 136.2, "storm", "full", "red"), (136.2, 138.4, "fire", "full", "red"),
           (138.4, 140.0, "game", "full", "green"), (140.0, 141.6, "gas", "full", "hot"),
           (141.6, 143.4, "fire", "quad", "red"), (143.4, 145.1, "storm", "full", "red")]
    for i, (a, b, n, m, g) in enumerate(fin):
        lab = "full" if i < 2 else m
        add(a, b, n, lab, g, off=(i % 3) * 0.9)

    # ---------------- outro
    add(145.1, 149.36, "portrait", "card", "bw", 0.0)     # КОНЕЦ
    return S


SHOTS = build_shots()


def shot_at(t):
    for s in SHOTS:
        if s["a"] <= t < s["b"]:
            return s
    return SHOTS[-1]


def section_energy(t):
    """0..1 rough loudness used for effect strength."""
    if 16 <= t < 27 or 45 <= t < 58 or 60 <= t < 71 or 90 <= t < 102 or 105 <= t < 118 \
            or 134 <= t < 145:
        return 1.0
    if 0 <= t < 16 or 27 <= t < 31 or 71 <= t < 74 or 87 <= t < 90 or 102 <= t < 105 \
            or 145 <= t:
        return 0.35
    return 0.7


# --------------------------------------------------------------------------- texts
TEXTS = [
    # big top line(s) + optional caption under the card
    (0.7, 6.8, "Я РУССКИЙ\nМУЖИК", 150, (255, 255, 255), (255, 212, 0), 300),
    (6.9, 11.9, "ОФИСНЫЙ ВОИН", 104, (255, 255, 255), (0, 0, 0), 300),
    (9.0, 11.9, "просто мужик", 62, (255, 255, 255), (0, 0, 0), 1630),
    (12.2, 15.7, "ПОЕХАЛИ!", 132, (255, 216, 0), (0, 0, 0), 1560),
    (16.4, 20.2, "ЖАРКО!", 190, (255, 255, 255), (190, 20, 20), 290),
    (20.6, 26.8, "ЖГИ!", 150, (255, 216, 0), (0, 0, 0), 1600),
    (27.4, 30.9, "СТИРКА\nПО-РУССКИ", 104, (255, 255, 255), (0, 60, 90), 300),
    (31.4, 35.6, "РАБОТА КИПИТ", 96, (255, 255, 255), (0, 0, 0), 300),
    (36.0, 39.4, "ЗАПРАВИЛСЯ", 112, (255, 216, 0), (0, 0, 0), 1600),
    (39.8, 41.2, "И ПОЕХАЛ", 108, (255, 255, 255), (0, 0, 0), 1600),
    (43.5, 44.9, "СИЛА!", 160, (110, 255, 140), (0, 0, 0), 1620),
    (45.4, 49.4, "ЖАРКО!", 190, (255, 255, 255), (190, 20, 20), 290),
    (49.8, 54.0, "ЖГИ!", 150, (255, 216, 0), (0, 0, 0), 560),
    (54.4, 57.8, "ЕЩЁ!", 160, (255, 255, 255), (0, 0, 0), 1560),
    (58.4, 62.4, "НОЧНАЯ СМЕНА", 96, (255, 255, 255), (0, 0, 0), 300),
    (62.8, 66.4, "ТИХО ЕДЕМ", 100, (255, 216, 0), (0, 0, 0), 1600),
    (66.8, 70.8, "НО УВЕРЕННО", 92, (255, 255, 255), (0, 0, 0), 300),
    (71.3, 74.0, "ПРОСТО\nМУЖИК", 130, (255, 255, 255), (255, 212, 0), 300),
    (74.4, 78.2, "МАГИЯ", 160, (140, 255, 160), (0, 0, 0), 300),
    (78.6, 83.0, "БЕЗ ПЕРЕРЫВА", 92, (255, 255, 255), (0, 0, 0), 1600),
    (83.4, 86.8, "И СНОВА В БОЙ", 96, (255, 216, 0), (0, 0, 0), 300),
    (87.3, 90.0, "ВЕТЕР В ХАЕР", 96, (255, 255, 255), (0, 0, 0), 1600),
    (90.4, 94.4, "ГРОЗА", 180, (255, 255, 255), (190, 20, 20), 290),
    (94.8, 98.8, "БЬЁТ", 160, (255, 216, 0), (0, 0, 0), 1600),
    (99.2, 101.8, "ПРЯМО В ЦЕЛЬ", 86, (255, 255, 255), (0, 0, 0), 1640),
    (102.3, 105.0, "СТИРКА 2.0", 104, (255, 255, 255), (0, 60, 90), 300),
    (105.4, 109.4, "ЗАПРАВИЛСЯ", 108, (255, 216, 0), (0, 0, 0), 300),
    (109.8, 111.9, "И ПОЛЕТЕЛ", 104, (255, 255, 255), (0, 0, 0), 1600),
    (112.3, 113.9, "ЗАРЯД!", 130, (140, 255, 160), (0, 0, 0), 1630),
    (114.0, 117.8, "БЕЗ ТОРМОЗОВ", 92, (255, 255, 255), (0, 0, 0), 300),
    (118.4, 123.0, "РАБОТА —\nТОЖЕ БОЙ", 96, (255, 255, 255), (0, 0, 0), 300),
    (123.4, 128.0, "НО МЫ\nНЕ СДАЁМСЯ", 100, (255, 216, 0), (0, 0, 0), 1620),
    (128.4, 133.6, "ДО КОНЦА", 130, (255, 255, 255), (190, 20, 20), 300),
    (134.4, 139.6, "Я РУССКИЙ\nМУЖИК", 140, (255, 255, 255), (255, 212, 0), 300),
    (140.0, 145.0, "ФИНАЛ!", 150, (255, 216, 0), (0, 0, 0), 1600),
    (145.6, 148.4, "КОНЕЦ", 190, (255, 255, 255), (190, 20, 20), 1580),
]


# --------------------------------------------------------------------------- compose
def card_sprite(kit, src_img, grd, zoom, angle, size=PHOTO):
    """Photo tile with a dark poster frame + accent bar."""
    img = grade(src_img, grd)
    h, w = img.shape[:2]
    cw = int(w / zoom)
    x0 = (w - cw) // 2
    y0 = (h - cw) // 2
    crop = img[max(0, y0):max(0, y0) + cw, max(0, x0):max(0, x0) + cw]
    crop = cv2.resize(crop, (size, size), interpolation=cv2.INTER_CUBIC)
    crop = cv2.addWeighted(crop, 1.35, cv2.GaussianBlur(crop, (0, 0), 1.4), -0.35, 3)

    out = np.zeros((CARD, CARD, 4), np.uint8)
    out[:, :, :3] = (16, 16, 18)
    px = (CARD - size) // 2
    out[px:px + size, px:px + size, :3] = crop
    out[px:px + size, px:px + size, 3] = 255
    rgb = np.ascontiguousarray(out[:, :, :3])
    cv2.rectangle(rgb, (px - 3, px - 3), (px + size + 2, px + size + 2), (245, 245, 245), 2)
    accent = {"red": (60, 40, 220), "amber": (40, 190, 255), "cold": (240, 200, 150),
              "teal": (230, 200, 90), "green": (110, 240, 110), "blue": (255, 160, 80),
              "bw": (235, 235, 235)}[grd]
    cv2.rectangle(rgb, (px - 3, px + size + 2), (px + size + 2, px + size + 12), accent, -1)
    out[:, :, :3] = rgb
    mask = rounded_mask(CARD, 26)
    out[..., 3] = mask
    if angle:
        m = cv2.getRotationMatrix2D((CARD / 2, CARD / 2), angle, 1.0)
        out = cv2.warpAffine(out, m, (CARD, CARD), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    return out


def mode_is_card(shot):
    return shot["mode"] in ("card", "oval")


def compose(kit, t):
    shot = shot_at(t)
    local = t - shot["a"]
    span = max(1e-3, shot["b"] - shot["a"])
    u = clamp(local / span)
    e = section_energy(t)
    p = pulse(t)
    dp = down_pulse(t)

    src_img = kit.frame(shot["src"], t + shot["off"])

    # ---- background: blurred, graded, drifting
    bg = grade(src_img, shot["grade"])
    bg = cover(bg, W, H)
    bg = cv2.resize(bg, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    bg = cv2.GaussianBlur(bg, (0, 0), 4.0)
    bg = cv2.resize(bg, (W, H), interpolation=cv2.INTER_LINEAR)
    dim = 0.30 if mode_is_card(shot) else (0.40 + 0.10 * e)
    bg = (bg.astype(np.float32) * dim + 8.0)
    canvas = np.clip(bg, 0, 255).astype(np.uint8)

    # ---- rays on accents
    if e > 0.6:
        rays = kit.rays
        a = (0.10 * p + 0.05 * dp) * e
        if a > 0.004:
            canvas = np.clip(canvas.astype(np.float32) + rays * 255.0 * a, 0, 255).astype(np.uint8)

    # ---- foreground
    mode = shot["mode"]
    if mode == "card":
        # accent glow behind the card (cached per grade)
        cache_key = ("glow", shot["grade"])
        if cache_key not in kit.glows:
            g = np.zeros((H // 4, W // 4, 3), np.uint8)
            accent = {"red": (40, 30, 190), "amber": (30, 150, 235), "cold": (150, 120, 90),
                      "teal": (170, 150, 60), "green": (90, 190, 70), "blue": (200, 120, 50),
                      "bw": (40, 40, 40)}[shot["grade"]]
            cv2.circle(g, (W // 8, 255), 160, accent, -1)
            g = cv2.GaussianBlur(g, (0, 0), 40).astype(np.float32)
            kit.glows[cache_key] = cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)
        glow = kit.glows[cache_key]
        canvas = np.clip(canvas.astype(np.float32) + glow * (0.55 + 0.25 * p), 0, 255).astype(np.uint8)
        zoom = 1.02 + 0.12 * ease_in_out(u) + 0.025 * p
        angle = math.sin(t * 0.7) * 1.1
        sprite = card_sprite(kit, src_img, shot["grade"], zoom, angle)
        sc = (0.96 + 0.02 * p) * (1.0 + 0.02 * math.sin(t * 1.3))
        m = cv2.getRotationMatrix2D((CARD / 2, CARD / 2), 0, sc)
        big = cv2.warpAffine(sprite, m, (CARD, CARD), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        shake = 16 * p + 6 * down_pulse(t)
        x = (W - CARD) // 2 + int(math.sin(t * 11.0) * shake)
        y = 500 + int(math.cos(t * 9.0) * shake)
        # shadow
        shade = (big[..., 3].astype(np.float32) / 255.0) * 0.60
        sx, sy = 10, 26
        roi = canvas[y + sy:y + sy + CARD, x + sx:x + sx + CARD].astype(np.float32)
        a3 = cv2.GaussianBlur(shade, (0, 0), 16)
        roi *= (1 - a3)[..., None]
        canvas[y + sy:y + sy + CARD, x + sx:x + sx + CARD] = np.clip(roi, 0, 255).astype(np.uint8)
        paste(canvas, big, x, y, shadow=False)

    elif mode == "full":
        zoom = 1.05 + 0.10 * ease_in_out(u) + 0.03 * p
        img = grade(src_img, shot["grade"])
        cw = int(640 * 9 / 16 / zoom)          # 9:16 window inside the square source
        x0 = (640 - cw) // 2
        crop = img[:, x0:x0 + cw]
        full = cv2.resize(crop, (W, H), interpolation=cv2.INTER_CUBIC)
        blur = cv2.GaussianBlur(full, (0, 0), 1.6)
        full = cv2.addWeighted(full, 1.45, blur, -0.45, 4)
        # chromatic aberration
        sh = 2 + int(3 * p)
        full[..., 2] = np.roll(full[..., 2], sh, axis=1)
        canvas = full

    elif mode == "oval":
        img = grade(src_img, shot["grade"])
        zoom = 1.03 + 0.10 * ease_in_out(u)
        cw = int(640 / zoom)
        crop = img[(640 - cw) // 2:(640 - cw) // 2 + cw, (640 - cw) // 2:(640 - cw) // 2 + cw]
        crop = cv2.resize(crop, (760, 760), interpolation=cv2.INTER_LINEAR)
        crop = np.clip(crop.astype(np.float32) * 1.75 + 22, 0, 255).astype(np.uint8)
        r = int(452 + 8 * p)
        tile = np.zeros((2 * (r + 26), 2 * (r + 26), 4), np.uint8)
        big = cv2.resize(crop, (2 * r, 2 * r), interpolation=cv2.INTER_LINEAR)
        off = 26
        tile[off:off + 2 * r, off:off + 2 * r, :3] = big
        tile[off:off + 2 * r, off:off + 2 * r, 3] = 255
        om = oval_mask(2 * (r + 26), 2 * (r + 26), 2)
        tile[..., 3] = np.minimum(tile[..., 3], om)
        cv2.circle(canvas, (W // 2, 940), r + 8, (250, 252, 255), 12, cv2.LINE_AA)
        cv2.circle(canvas, (W // 2, 940), r + 18, (24, 24, 28), 5, cv2.LINE_AA)
        paste(canvas, tile, W // 2 - (r + 26), 940 - (r + 26), shadow=False)

    elif mode == "quad":
        img = grade(src_img, shot["grade"])
        cw = int(640 * 9 / 16)
        crop = img[:, (640 - cw) // 2:(640 + cw) // 2]
        half = cv2.resize(crop, (W // 2, H // 2), interpolation=cv2.INTER_LINEAR)
        q = np.zeros((H, W, 3), np.uint8)
        q[:H // 2, :W // 2] = half
        q[:H // 2, W // 2:] = cv2.flip(half, 1)
        q[H // 2:, :W // 2] = cv2.flip(half, 0)
        q[H // 2:, W // 2:] = cv2.flip(half, -1)
        canvas = q
        sh = 3 + int(4 * p)
        canvas[..., 2] = np.roll(canvas[..., 2], sh, axis=1)

    else:  # glitch / photo
        img = grade(src_img, shot["grade"])
        base = cover(img, W, H)
        canvas = base.copy()
        if mode == "glitch":
            rng = np.random.default_rng(int(t * 30))
            for _ in range(7):
                y0 = int(rng.integers(0, H - 40))
                hh = int(rng.integers(8, 46))
                dx = int(rng.integers(-40, 40))
                canvas[y0:y0 + hh] = np.roll(base[y0:y0 + hh], dx, axis=1)
            sh = 4 + int(6 * p)
            canvas[..., 2] = np.roll(canvas[..., 2], sh, axis=1)
            canvas[..., 0] = np.roll(canvas[..., 0], -sh, axis=1)
        else:
            canvas = base

    # ---- impact flash on downbeats
    f = 0.0
    k = np.searchsorted(DOWNS, t, side="right")
    if k > 0:
        dt = t - DOWNS[k - 1]
        if dt < 0.09:
            f = (1 - dt / 0.09) * (0.16 * e + 0.05)
    if f > 0.004:
        canvas = np.clip(canvas.astype(np.float32) * (1 - f) + 255.0 * f, 0, 255).astype(np.uint8)

    # ---- section boundary whip
    for s in SHOTS:
        if 0 <= t - s["a"] < 0.10 and s["a"] > 0.5:
            w = 1 - (t - s["a"]) / 0.10
            if w > 0.05:
                kx = max(1, int(28 * w)) | 1
                canvas = cv2.blur(canvas, (kx, 1))
                shift = int(70 * w)
                canvas = np.roll(canvas, shift, axis=1)
            break

    # ---- grain + vignette
    g = kit.grain[int(t * 30) % len(kit.grain)]
    g = cv2.resize(g, (W, H), interpolation=cv2.INTER_NEAREST)
    canvas = np.clip(canvas.astype(np.float32) + g[..., None], 0, 255).astype(np.uint8)
    canvas = (canvas.astype(np.float32) * kit.vignette).astype(np.uint8)

    # ---- texts
    for (a, b, s, size, fill, sh, y) in TEXTS:
        if not (a <= t < b):
            continue
        tin = t - a
        tout = b - t
        alpha = clamp(tin / 0.10) * clamp(tout / 0.16)
        if alpha <= 0.01:
            continue
        sp = kit.text(s, size, fill, sh)
        grow = back_out(clamp(tin / 0.22))
        beta = 0.82 + 0.18 * grow
        beta *= 1.0 + 0.02 * p
        hh, ww = sp.shape[:2]
        if ww * beta > 1000:
            beta = 1000 / ww
        m = cv2.getRotationMatrix2D((ww / 2, hh / 2), 0.0, beta)
        m[0, 2] += (W / 2) - ww / 2
        m[1, 2] += y - hh / 2
        rot = cv2.warpAffine(sp, m, (W, H), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        if alpha < 0.999:
            rot[..., 3] = (rot[..., 3].astype(np.float32) * alpha).astype(np.uint8)
        paste(canvas, rot, 0, 0, shadow=False)

    # ---- final fade in/out
    if t < 0.5:
        canvas = (canvas.astype(np.float32) * (t / 0.5)).astype(np.uint8)
    if t > DUR - 1.2:
        k = clamp((t - (DUR - 1.2)) / 1.2)
        canvas = (canvas.astype(np.float32) * (1 - k)).astype(np.uint8)
    return canvas


# --------------------------------------------------------------------------- main
def render(out, start=0.0, end=None, crf=19):
    end = DUR if end is None else min(end, DUR)
    n0, n1 = int(round(start * FPS)), int(round(end * FPS))
    cmd = [FF, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-an", "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-maxrate", "9M", "-bufsize", "18M",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    kit = Kit()
    for i in range(n0, n1):
        t = i / FPS
        frame = compose(kit, t)
        p.stdin.write(frame.tobytes())
        if i % 150 == 0:
            print(f"\rframe {i}/{n1} t={t:6.1f}s", end="", flush=True)
    p.stdin.close()
    p.wait()
    print(f"\nwrote {out}")


def preview(times):
    os.makedirs(TMP, exist_ok=True)
    kit = Kit()
    for t in times:
        f = compose(kit, float(t))
        path = os.path.join(TMP, f"prev_{float(t):06.2f}.png")
        cv2.imwrite(path, f)
        print("wrote", path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview")
    ap.add_argument("--out")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--crf", type=int, default=19)
    args = ap.parse_args()
    if args.preview:
        preview([float(x) for x in args.preview.split(",")])
    elif args.out:
        os.makedirs(MEDIA, exist_ok=True)
        render(args.out, args.start, args.end, args.crf)
    else:
        ap.print_help()
