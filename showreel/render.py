#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Шоурил «СМОТРИТЕ, КАК Я УМЕЮ» — 15 секунд, 1080×1920, 30 fps, 450 кадров.

Всё видео рисуется этим файлом покадрово (Pillow + NumPy):
без видеоредактора, без плагинов, без готовых футажей.
Звук тоже синтезируется кодом (NumPy) — бит, басы, подъёмы и удары.

Запуск:
    python3 showreel/render.py            # полный рендер в out9/
    python3 showreel/render.py --preview  # быстрый черновик 360×640

Нужны: Pillow, numpy, imageio-ffmpeg (даёт бинарник ffmpeg).
"""

import argparse
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"

# ---------------------------------------------------------------- константы
W, H, FPS, DUR = 1080, 1920, 30, 15
TOTAL = FPS * DUR                      # 450 кадров
BLACK = (10, 10, 10)
CREAM = (244, 237, 226)
ORANGE = (255, 90, 26)
GREY = (120, 120, 118)
DARKLINE = (26, 26, 26)

SCENES = [  # (начало_кадра, длина_кадров, подпись_техники)
    (0,   54, ""),                                  # 01 хук + строки кода
    (54,  54, "01 — КИНЕТИЧЕСКАЯ ТИПОГРАФИКА"),      # 02 движение
    (108, 54, "02 — 3D БЕЗ 3D-ДВИЖКА"),             # 03 куб
    (162, 54, "03 — 2 600 ЧАСТИЦ"),                 # 04 частицы
    (216, 54, "04 — КАДР ЗА КАДРОМ"),               # 05 счётчик
    (270, 54, ""),                                  # 06 геометрия
    (324, 54, ""),                                  # 07 show reel
    (378, 72, ""),                                  # 08 финал
]
AUTHOR = "VADIM"
rng = np.random.default_rng(129)

# ---------------------------------------------------------------- шрифты
_cache = {}


def font(name, size):
    key = (name, size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(str(FONT_DIR / name), size)
    return _cache[key]


def display(size):
    return font("Montserrat_900Black.ttf", size)


def mono(size, bold=False):
    return font("JetBrainsMono_700Bold.ttf" if bold else "JetBrainsMono_400Regular.ttf", size)


def text_w(draw, txt, fnt):
    box = draw.textbbox((0, 0), txt, font=fnt)
    return box[2] - box[0], box[3] - box[1], box


def fit(draw, txt, max_w, start, name="Montserrat_900Black.ttf", min_size=20):
    size = start
    while size > min_size:
        fnt = font(name, size)
        if draw.textbbox((0, 0), txt, font=fnt)[2] <= max_w:
            return fnt
        size -= 4
    return font(name, min_size)


def center_text(draw, cx, y, txt, fnt, fill, tracking=0):
    """Текст по центру; tracking — межбуквенный интервал в пикселях."""
    if not tracking:
        w, h, box = text_w(draw, txt, fnt)
        draw.text((cx - w / 2 - box[0], y - box[1]), txt, font=fnt, fill=fill)
        return w, h
    widths = [draw.textbbox((0, 0), ch, font=fnt)[2] for ch in txt]
    total = sum(widths) + tracking * (len(txt) - 1)
    x = cx - total / 2
    for ch, cw in zip(txt, widths):
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += cw + tracking
    return total, fnt.size


# ---------------------------------------------------------------- easing
def clamp01(x):
    return min(1.0, max(0.0, x))


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_inout(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def pop(x):
    """Появление с лёгким перелётом (как пружина)."""
    x = clamp01(x)
    return 1 + 2.2 * ((x - 1) ** 3) + 1.2 * ((x - 1) ** 2) if x < 1 else 1.0


def slide(draw, cx, y, txt, fnt, fill, prog, direction=1):
    """Строка въезжает сбоку с обрезкой по мере появления."""
    w, h, box = text_w(draw, txt, fnt)
    off = (1 - ease_out(prog)) * (w + 120) * direction
    draw.text((cx - w / 2 - box[0] + off, y - box[1]), txt, font=fnt, fill=fill)


# ---------------------------------------------------------------- фоновая сетка
_grid = None


def grid_bg():
    global _grid
    if _grid is None:
        img = Image.new("RGB", (W, H), BLACK)
        d = ImageDraw.Draw(img)
        for x in range(0, W + 1, 90):
            d.line([(x, 0), (x, H)], fill=DARKLINE, width=1)
        for y in range(0, H + 1, 90):
            d.line([(0, y), (W, y)], fill=DARKLINE, width=1)
        _grid = img
    return _grid.copy()


CODE_LINES = [
    "const scene = scenes[current];", "frame = render(t * 30)",
    "if (t > cut) next_scene();", "particles.forEach(p => p.update(dt));",
    "cube.rotateY(angle += 0.04);", "ctx.fillStyle = '#FF5A1A';",
    "for (let i = 0; i < 2600; i++) spawn(i);", "text.pop(easeOutCubic(p));",
    "bass.note(freq, time, 0.24);", "while (frame < 450) draw(frame++);",
    "const scale = spring(stiffness = 180);", "mask = text_to_points('15')",
    "ring.expand(radius * easeIn(p));", "bars[i] = 40 + noise(i, t) * 220;",
    "glitch.slice(img, random_y, offset);", "// ни одного готового футажа",
    "camera.z = 4.5; project(vertex);", "wave = sin(2*pi*f*t) * env;",
    "if (!plugins) use_code(); // только код", "overlay.tc = timecode(frame);",
    "sticker.rotate(-2deg).scale(pop);", "finale: подпись VADIM",
]


def code_bg(frame, dark=150):
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    fnt = mono(25)
    scroll = (frame * 3) % 44
    y = -scroll - 20
    i0 = (frame * 3) // 44
    for k in range(48):
        line = CODE_LINES[(i0 + k) % len(CODE_LINES)]
        col = (86, 84, 80)
        if (i0 + k) % 5 == 0:
            col = (130, 62, 32)
        elif (i0 + k) % 7 == 0:
            col = (140, 138, 132)
        d.text((48 + ((i0 + k) % 3) * 26, y), line, font=fnt, fill=col)
        y += 44
    veil = Image.new("RGB", (W, H), (0, 0, 0))
    return Image.blend(img, veil, dark / 255.0)


# ---------------------------------------------------------------- оверлей камеры (REC / TC / SC)
def overlay(img, frame, scene_idx, light=False):
    d = ImageDraw.Draw(img)
    ink = (20, 20, 20) if light else CREAM
    accent = (200, 60, 10) if light else ORANGE
    m, ln, th = 54, 38, 5
    for cx, cy, sx, sy in [(m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)]:
        d.line([(cx, cy), (cx + ln * sx, cy)], fill=ink, width=th)
        d.line([(cx, cy), (cx, cy + ln * sy)], fill=ink, width=th)
    fnt = mono(29)
    if (frame // 15) % 2 == 0:
        d.ellipse([m + 4, 92, m + 20, 108], fill=(230, 40, 30))
    d.text((m + 30, 84), "REC", font=fnt, fill=ink)
    tc = f"TC 00:00:{frame // FPS:02d}:{(frame % FPS):02d}"
    w, _, _ = text_w(d, tc, fnt)
    d.text((W - m - w, 84), tc, font=fnt, fill=ink)
    d.text((m, H - 118), f"SC {scene_idx + 1:02d} / 08", font=fnt, fill=ink)
    who = f"{AUTHOR} / MOTION"
    w, _, _ = text_w(d, who, fnt)
    d.text((W - m - w, H - 118), who, font=fnt, fill=ink)
    bw, by = 380, H - 74
    d.line([(m, by), (m + bw, by)], fill=(70, 70, 70) if not light else (170, 165, 155), width=5)
    d.line([(m, by), (m + bw * (frame + 1) / TOTAL, by)], fill=accent, width=5)
    return img


def glitch(img, frame, strength=14):
    r = np.random.default_rng(1000 + frame)
    for _ in range(5):
        y = int(r.integers(0, H - 60))
        h = int(r.integers(12, 54))
        off = int(r.integers(-strength, strength + 1))
        strip = img.crop((0, y, W, y + h))
        img.paste(strip, (off, y))
    return img


# ================================================================ СЦЕНА 1: хук
def scene1(frame, local, lines_total):
    img = code_bg(frame, dark=132)
    d = ImageDraw.Draw(img)
    cx, base = W // 2, 700
    slide(d, cx, base, "СМОТРИТЕ,", fit(d, "СМОТРИТЕ,", 940, 168), CREAM, local / 10, -1)
    if local >= 10:
        slide(d, cx, base + 190, "КАК Я", fit(d, "КАК Я", 940, 168), ORANGE, (local - 10) / 10, 1)
    if local >= 20:
        slide(d, cx, base + 380, "УМЕЮ", fit(d, "УМЕЮ", 940, 190), CREAM, (local - 20) / 10, -1)
    if local >= 32:  # счётчик строк этого самого файла
        p = ease_out((local - 32) / 18)
        n = int(lines_total * p)
        bw, bh = int(560 * pop((local - 32) / 12)), 210
        x0, y0 = cx - bw // 2, 1330
        d.rectangle([x0, y0, x0 + bw, y0 + bh], fill=ORANGE)
        if bw > 300:
            center_text(d, cx, y0 + 26, str(n), display(120), BLACK)
            center_text(d, cx, y0 + bh + 22, "СТРОК КОДА — И НИ КАДРА ЛИШНЕГО", mono(28, True), CREAM)
    return img


# ================================================================ СЦЕНА 2: кинетическая типографика
def scene2(frame, local):
    img = Image.new("RGB", (W, H), ORANGE)
    d = ImageDraw.Draw(img)
    word = "ДВИЖЕНИЕ"
    side = display(150)
    for col_x, direction in [(36, 1), (W - 118, -1)]:
        off = (local * 7 * direction) % 360
        for k in range(-2, 8):
            y = k * 360 + (off if direction > 0 else 360 - off)
            tile = Image.new("RGBA", (720, 190), (0, 0, 0, 0))
            td = ImageDraw.Draw(tile)
            td.text((6, 0), word, font=side, fill=(255, 90, 26, 255),
                    stroke_width=3, stroke_fill=(10, 10, 10, 255))
            tile = tile.rotate(90, expand=True)
            img.paste(tile, (col_x - 40, int(y) - 360), tile)
    d = ImageDraw.Draw(img)
    for i, yy in enumerate([330, 356, 382, int(1490 + 0), 1516, 1542]):
        shift = ((local * 10) % 240) - 120 if i < 3 else 120 - ((local * 10) % 240)
        d.line([(shift, yy), (W + shift, yy)], fill=BLACK, width=7)
    big = Image.new("RGBA", (1500, 330), (0, 0, 0, 0))
    bd = ImageDraw.Draw(big)
    bd.text((10, 10), word, font=display(265), fill=(10, 10, 10, 255))
    big = big.rotate(90, expand=True)
    rise = (1 - ease_out(local / 22)) * 700
    img.paste(big, (W // 2 - big.width // 2, int(H // 2 - big.height // 2 + rise)), big)
    d = ImageDraw.Draw(img)
    d.text((54, 150), "01 — КИНЕТИЧЕСКАЯ ТИПОГРАФИКА", font=mono(30, True), fill=BLACK)
    return img


# ================================================================ СЦЕНА 3: куб без движка
def _face_texture(text, bg, fg, top=False):
    s = 640
    img = Image.new("RGBA", (s, s), bg + (255,))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, s - 1, s - 1], outline=(244, 237, 226, 255), width=10)
    if top:
        center_text(d, s // 2, s // 2 - 90, "3D", display(180), fg)
    elif not text:
        pass  # глухая грань без надписи
    else:
        words = text.split()
        fnt = fit(d, max(words, key=len), 560, 150)
        total_h = len(words) * (fnt.size + 8)
        y = s // 2 - total_h // 2
        for w_ in words:
            center_text(d, s // 2, y, w_, fnt, fg)
            y += fnt.size + 8
    return img


def _coeffs(out_pts, in_pts):
    """Коэффициенты PIL PERSPECTIVE: для пикселя (x,y) выхода -> (u,v) входа."""
    matrix, b = [], []
    for (x, y), (u, v) in zip(out_pts, in_pts):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        b.append(u)
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.append(v)
    res = np.linalg.solve(np.array(matrix, dtype=float), np.array(b, dtype=float))
    return np.array(res).reshape(8)


def _warp(img, texture, quad):
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    x0, y0 = max(0, int(min(xs))), max(0, int(min(ys)))
    x1, y1 = min(W, int(max(xs)) + 1), min(H, int(max(ys)) + 1)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return
    shifted = [(x - x0, y - y0) for x, y in quad]
    s = texture.width
    coeffs = _coeffs(shifted, [(0, 0), (s, 0), (s, s), (0, s)])
    face = texture.transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, coeffs, Image.BILINEAR)
    img.paste(face, (x0, y0), face)


CUBE_FACES = [  # (имя, вершины, текстура)
    ("КОД",      [4, 5, 6, 7], _face_texture("КОД", (16, 16, 16), CREAM)),
    ("РИТМ",     [5, 1, 2, 6], _face_texture("РИТМ", CREAM, BLACK)),
    ("ЗВУК",     [1, 0, 3, 2], _face_texture("ЗВУК", ORANGE, BLACK)),
    ("КАДР",     [0, 4, 7, 3], _face_texture("КАДР", CREAM, BLACK)),
    ("3D",       [0, 1, 5, 4], _face_texture("", ORANGE, BLACK, top=True)),
    ("",         [7, 6, 2, 3], _face_texture("", (30, 30, 30), CREAM)),
]
VERTS = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
                  [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], dtype=float)
NORMALS = np.array([[0, 0, 1], [1, 0, 0], [0, 0, -1], [-1, 0, 0], [0, -1, 0], [0, 1, 0]], dtype=float)


def _rot(v, ax, ay):
    cx, sx, cy, sy = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    return v @ rx.T @ ry.T


def scene3(frame, local):
    img = grid_bg()
    p = local / 53
    ay = ease_inout(p) * math.pi * 2
    ax = -0.46 + math.sin(local / 9) * 0.05
    pts3 = _rot(VERTS, ax, ay)
    norms = _rot(NORMALS, ax, ay)
    centre = np.array([W / 2, 900 + math.sin(local / 7) * 16])
    size, cam = 258, 4.6
    proj = []
    for v in pts3:
        f = cam / (cam - v[2])
        proj.append(centre + v[:2] * size * f)
    order = sorted(range(6), key=lambda i: pts3[CUBE_FACES[i][1]].mean(axis=0)[2])
    front_name, quads = "", []
    for i in order:
        if norms[i][2] <= 0.12:
            continue
        name, idx, tex = CUBE_FACES[i]
        quad = [tuple(proj[j]) for j in idx]
        _warp(img, tex, quad)
        quads.append(quad)
        if i == int(np.argmax(norms[:, 2])):
            front_name = name
    d = ImageDraw.Draw(img)
    for quad in quads:  # рёбра — поверх всех граней, чтобы не перекрывались заливкой
        d.line(quad + [quad[0]], fill=CREAM, width=7, joint="curve")
    d = ImageDraw.Draw(img)
    d.text((54, 150), "02 — 3D БЕЗ 3D-ДВИЖКА", font=mono(30, True), fill=CREAM)
    if front_name:
        d.text((70, 1480), "▸ " + front_name, font=mono(34, True), fill=ORANGE)
    return img


# ================================================================ СЦЕНА 4: частицы
def _particle_targets():
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    center_text(d, W // 2, 560, "15", display(560), 255)
    center_text(d, W // 2, 1230, "СЕКУНД", display(178), 255)
    ys, xs = np.nonzero(np.array(mask) > 0)
    pick = rng.choice(len(xs), size=2600, replace=len(xs) < 2600)
    return np.stack([xs[pick], ys[pick]], axis=1).astype(float)


P_TARGET = _particle_targets()
P_RING = np.stack([rng.uniform(0, 2 * np.pi, 2600), rng.uniform(80, 760, 2600)], axis=1)
P_COLOUR = [CREAM if r < 0.68 else (ORANGE if r < 0.93 else (170, 170, 170))
            for r in rng.random(2600)]


def scene4(frame, local):
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    d.text((54, 150), "03 — 2 600 ЧАСТИЦ", font=mono(30, True), fill=CREAM)
    centre = np.array([W / 2, 920.0])
    ring_xy = centre + np.stack([np.cos(P_RING[:, 0]) * P_RING[:, 1],
                                 np.sin(P_RING[:, 0]) * P_RING[:, 1] * 1.25], axis=1)
    if local < 14:  # вспышка-«звезда»
        p = ease_out(local / 14)
        pos = centre + (ring_xy - centre) * p
        for (x, y), (tx, ty), col in zip(pos, ring_xy, P_COLOUR):
            d.line([(centre[0], centre[1]), (x, y)], fill=col, width=3)
    elif local < 26:  # кольцо сжимается к буквам
        p = ease_inout((local - 14) / 12)
        pos = ring_xy * (1 - p) + P_TARGET * p
        d.point([tuple(v) for v in pos], fill=None)
        for (x, y), col in zip(pos, P_COLOUR):
            d.rectangle([x - 3, y - 3, x + 3, y + 3], fill=col)
    elif local < 44:  # собранный текст слегка дрожит
        jitter = np.stack([rng.uniform(-2.5, 2.5, 2600), rng.uniform(-2.5, 2.5, 2600)], axis=1)
        pos = P_TARGET + jitter
        for (x, y), col in zip(pos, P_COLOUR):
            d.rectangle([x - 3, y - 3, x + 3, y + 3], fill=col)
    else:  # разлёт
        p = (local - 44) / 10
        direction = P_TARGET - centre
        direction = direction / (np.linalg.norm(direction, axis=1, keepdims=True) + 1e-6)
        pos = P_TARGET + direction * (p ** 2) * 700
        for (x, y), (tx, ty), col in zip(pos, P_TARGET, P_COLOUR):
            d.line([(tx, ty), (x, y)], fill=col, width=3)
    return img


# ================================================================ СЦЕНА 5: счётчик кадров
BAR_SEED = rng.uniform(0.25, 1.0, 28)


def scene5(frame, local):
    img = grid_bg()
    d = ImageDraw.Draw(img)
    d.text((54, 150), "04 — КАДР ЗА КАДРОМ", font=mono(30, True), fill=CREAM)
    n = int(450 * ease_out(local / 40))
    done = local >= 40
    fnt = display(330)
    txt = f"{n:03d}"
    w, _, _ = text_w(d, txt, fnt)
    d.text(((W - w) / 2, 640), txt, font=fnt, fill=ORANGE if done else CREAM)
    if done:
        center_text(d, W // 2, 1010, "КАДРОВ", display(90), CREAM)
    for i in range(28):
        bh = BAR_SEED[i] * 190 * (0.55 + 0.45 * math.sin(local / 3.1 + i * 1.7))
        x = 84 + i * 33
        col = CREAM if i % 6 == 0 else ORANGE
        d.rectangle([x, 1420 - bh, x + 19, 1420], fill=col)
    d.line([(70, 1420), (1010, 1420)], fill=GREY, width=3)
    fnt = mono(28)
    d.text((70, 1450), "30 FPS", font=fnt, fill=CREAM)
    center_text(d, W // 2, 1450, "1080×1920", mono(28), CREAM)
    w, _, _ = text_w(d, "15.0 S", fnt)
    d.text((W - 70 - w, 1450), "15.0 S", font=fnt, fill=CREAM)
    return img


# ================================================================ СЦЕНА 6: геометрия
def scene6(frame, local):
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, 900
    for layer in range(7):
        r = 150 + layer * 105
        ang = local * (0.9 if layer % 2 == 0 else -0.7) * (1 + layer * 0.12)
        col = ORANGE if layer % 3 == 0 else CREAM
        square = []
        for k in range(4):
            a = math.radians(ang + k * 90 + layer * 12)
            square.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        d.line(square + [square[0]], fill=col, width=5)
        d.ellipse([cx - r * 0.72, cy - r * 0.72, cx + r * 0.72, cy + r * 0.72],
                  outline=col, width=3)
    stickers = [("БЕЗ ПЛАГИНОВ", CREAM), ("БЕЗ ШАБЛОНОВ", CREAM), ("ТОЛЬКО КОД", ORANGE)]
    idx = min(2, local // 18)
    sub = local % 18
    txt, bg = stickers[idx]
    scale = pop(sub / 9)
    fnt = fit(d, txt, int(760 * scale), int(104 * scale))
    w, h, box = text_w(d, txt, fnt)
    pad_x, pad_y = 42, 26
    sticker = Image.new("RGBA", (int(w + pad_x * 2), int(h + pad_y * 2)), bg + (255,))
    sd = ImageDraw.Draw(sticker)
    sd.text((pad_x - box[0], pad_y - box[1]), txt, font=fnt, fill=BLACK + (255,))
    sticker = sticker.rotate(-2 if idx < 2 else 1.5, expand=True, resample=Image.BILINEAR)
    img.paste(sticker, (cx - sticker.width // 2, cy - sticker.height // 2), sticker)
    return img


# ================================================================ СЦЕНА 7: show reel
def scene7(frame, local):
    invert = local >= 46 and (local // 3) % 2 == 0
    bg, ink = (BLACK, CREAM) if invert else (CREAM, BLACK)
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    for k in range(9):
        y = (k * 260 + (local * 9) % 260) - 120
        d.line([(0, y), (W, y)], fill=(30, 30, 30) if invert else (196, 190, 178), width=3)
    slide(d, W // 2, 700, "SHOW", fit(d, "SHOW", 940, 300), ink, local / 10, -1)
    slide(d, W // 2, 1010, "REEL", fit(d, "REEL", 940, 300), ORANGE, (local - 3) / 10 if local > 3 else 0, 1)
    if local > 16:
        center_text(d, W // 2, 1400, "КОД  •  РИТМ  •  ЧАСТИЦЫ  •  ЗВУК", mono(30, True), ink, tracking=2)
    return glitch(img, frame, 10) if local < 5 or local >= 46 else img


# ================================================================ СЦЕНА 8: финал
def scene8(frame, local):
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    scale = pop(local / 16)
    fnt = fit(d, AUTHOR, int(900 * scale), int(245 * scale))
    center_text(d, W // 2, 760, AUTHOR, fnt, CREAM)
    uw = int(760 * ease_out((local - 10) / 16)) if local > 10 else 0
    d.rectangle([W // 2 - uw // 2, 1045, W // 2 + uw // 2, 1061], fill=ORANGE)
    if local > 18:
        center_text(d, W // 2, 1120, "M O T I O N   •   C O D E   •   S O U N D", mono(31), CREAM)
    if local > 28:
        center_text(d, W // 2, 1215, "SHOWREEL • 2026", mono(29), GREY)
        center_text(d, W // 2, 1285, "СДЕЛАНО КОДОМ ЗА 15 СЕКУНД", mono(26), (86, 84, 80))
    return img


BUILDERS = [scene1, scene2, scene3, scene4, scene5, scene6, scene7, scene8]


def render_frame(frame, lines_total):
    for idx, (start, length, _label) in enumerate(SCENES):
        if start <= frame < start + length:
            local = frame - start
            builder = BUILDERS[idx]
            if builder is scene1:
                img = builder(frame, local, lines_total)
            else:
                img = builder(frame, local)
            light = idx == 6 and not (local >= 46 and (local // 3) % 2 == 0)
            if 0 < local < 4 and idx != 6:
                img = glitch(img, frame)
            return overlay(img, frame, idx, light=light)
    return overlay(scene8(frame, 71), frame, 7)


# ================================================================ ЗВУК (тоже код)
SR = 48000


def _env(n, attack=0.004, decay=0.18):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def _add(track, sig, at_sec):
    at = int(at_sec * SR)
    end = min(len(track), at + len(sig))
    if end > at:
        track[at:end] += sig[:end - at]


def make_soundtrack(path):
    n = SR * DUR
    mix = np.zeros(n)
    noise = np.random.default_rng(7).standard_normal(n + SR)
    beat = 60 / 120  # 120 BPM
    roots = [55.0, 55.0, 43.65, 49.0]  # A A F G
    for step in range(int(DUR / beat)):
        t0 = step * beat
        tt = np.arange(int(SR * 0.25)) / SR
        kick = np.sin(2 * np.pi * (42 + 90 * np.exp(-tt * 42)) * tt) * np.exp(-tt * 13)
        _add(mix, kick * 0.95, t0)
        root = roots[(step // 4) % 4]
        for eighth in range(2):
            bt = np.arange(int(SR * 0.22)) / SR
            f = root * (2 if eighth else 1)
            bass = (np.sin(2 * np.pi * f * bt) + 0.35 * np.sin(4 * np.pi * f * bt)) * _env(len(bt), 0.003, 0.09)
            _add(mix, bass * 0.36, t0 + eighth * beat / 2)
        hat_n = int(SR * 0.05)
        hat = np.diff(noise[:hat_n + 1]) * np.exp(-np.arange(hat_n) / SR * 90)
        _add(mix, hat * 0.16, t0 + beat / 2)
        if step % 4 in (1, 3):
            cn = int(SR * 0.14)
            clap = noise[:cn] * np.exp(-np.arange(cn) / SR * 32)
            _add(mix, clap * 0.20, t0)
    for start, _ln, _lb in SCENES[:-1]:  # удары на склейках сцен
        t0 = start / FPS
        tt = np.arange(int(SR * 0.4)) / SR
        sweep = np.sin(2 * np.pi * (700 * np.exp(-tt * 7) + 60) * tt) * np.exp(-tt * 9)
        _add(mix, sweep * 0.35, t0)
    rt = np.arange(int(SR * 1.5)) / SR  # подъём перед финалом
    riser = np.sin(2 * np.pi * (180 * np.exp(rt * 1.25)) * rt) * (rt / 1.5) ** 2
    _add(mix, riser * 0.10, 11.1)
    tt = np.arange(int(SR * 2.2)) / SR  # финальный аккорд Am
    chord = sum(np.sin(2 * np.pi * f * tt) for f in (220.0, 261.63, 329.63)) / 3
    _add(mix, chord * np.exp(-tt * 1.5) * 0.28, 378 / FPS)
    mix = np.tanh(mix * 1.15)
    mix *= 0.89 / max(1e-6, np.max(np.abs(mix)))
    mix[-int(SR * 0.25):] *= np.linspace(1, 0, int(SR * 0.25))
    pcm = (mix * 32767).astype("<i2")
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(stereo.tobytes())


# ================================================================ рендер
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="черновик 360×640, каждый 2-й кадр")
    ap.add_argument("--out", default=str(ROOT / "out9"))
    args = ap.parse_args()

    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("Нужен imageio-ffmpeg: pip install imageio-ffmpeg Pillow numpy")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    lines_total = len(Path(__file__).read_text(encoding="utf-8").splitlines())
    print(f"строк в render.py: {lines_total}")

    scale = 1 / 3 if args.preview else 1.0
    step = 2 if args.preview else 1
    w, h = int(W * scale), int(H * scale)
    name = "черновик.mp4" if args.preview else "клип.mp4"
    silent = out / "_silent.mp4"
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264",
           "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(silent)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for frame in range(0, TOTAL, step):
        img = render_frame(frame, lines_total)
        if scale != 1.0:
            img = img.resize((w, h), Image.BILINEAR)
        proc.stdin.write(img.tobytes())
        if frame % 90 == 0:
            print(f"кадр {frame}/{TOTAL}", flush=True)
    proc.stdin.close()
    proc.wait()

    wav = out / "_sound.wav"
    make_soundtrack(wav)
    final = out / name
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", str(final)], check=True)
    silent.unlink(missing_ok=True)
    wav.unlink(missing_ok=True)

    if not args.preview:  # обложка + раскадровка для проверки
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-ss", "13.4", "-i", str(final),
                        "-frames:v", "1", str(out / "обложка.png")], check=True)
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(final),
                        "-vf", "fps=1,scale=270:480,tile=5x3:padding=4:margin=4",
                        "-frames:v", "1", str(out / "раскадровка.png")], check=True)
        report = {"файл": name, "размер": f"{W}x{H}", "fps": FPS, "кадров": TOTAL,
                  "длительность_с": DUR, "строк_кода_рендера": lines_total,
                  "сцен": len(SCENES), "автор": AUTHOR}
        (out / "отчёт.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("готово:", final)


if __name__ == "__main__":
    main()
