#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Универсальный рендерер скилла video-by-code.

Ролик полностью описывается JSON-конфигом (см. examples/), каждый кадр
рисуется кодом (Pillow + NumPy), звук синтезируется кодом (NumPy),
сборка — ffmpeg (из imageio-ffmpeg, системный не нужен).

    python3 render.py config.json [--out DIR] [--preview] [--no-audio]

Внутренний холст всегда 1080×1920; config.width/height задают размер
готового видео (кадры масштабируются при кодировании).

Зависимости: pip install Pillow numpy imageio-ffmpeg
Шрифты: assets/fonts рядом с пакетом скилла (Montserrat, JetBrains Mono, OFL).
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

SKILL_DIR = Path(__file__).resolve().parent.parent
FONT_DIR = SKILL_DIR / "assets" / "fonts"

BASE_W, BASE_H = 1080, 1920   # внутренний холст
W, H = BASE_W, BASE_H

# палитра (переопределяется из config.palette), ключи — hex "#RRGGBB"
PAL = {"bg": (10, 10, 10), "ink": (244, 237, 226), "accent": (255, 90, 26),
       "muted": (120, 120, 118), "line": (26, 26, 26), "light": (244, 237, 226)}
FPS = 30


def hex2rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


# ------------------------------------------------------------------ шрифты
_cache = {}


def font(name, size):
    key = (name, int(size))
    if key not in _cache:
        _cache[key] = ImageFont.truetype(str(FONT_DIR / name), int(size))
    return _cache[key]


def display(size):
    return font("Montserrat_900Black.ttf", size)


def mono(size, bold=False):
    return font("JetBrainsMono_700Bold.ttf" if bold else "JetBrainsMono_400Regular.ttf", size)


def text_w(draw, txt, fnt):
    b = draw.textbbox((0, 0), txt, font=fnt)
    return b[2] - b[0], b[3] - b[1], b


def fit(draw, txt, max_w, start, name="Montserrat_900Black.ttf", min_size=18):
    size = int(start)
    while size > min_size:
        fnt = font(name, size)
        if draw.textbbox((0, 0), txt, font=fnt)[2] <= max_w:
            return fnt
        size -= 4
    return font(name, min_size)


def center_text(draw, cx, y, txt, fnt, fill, tracking=0):
    if not tracking:
        w, h, b = text_w(draw, txt, fnt)
        draw.text((cx - w / 2 - b[0], y - b[1]), txt, font=fnt, fill=fill)
        return w, h
    widths = [draw.textbbox((0, 0), ch, font=fnt)[2] for ch in txt]
    total = sum(widths) + tracking * (len(txt) - 1)
    x = cx - total / 2
    for ch, cw in zip(txt, widths):
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += cw + tracking
    return total, fnt.size


# ------------------------------------------------------------------ easing
def clamp01(x):
    return min(1.0, max(0.0, x))


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_inout(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def pop(x):
    x = clamp01(x)
    return 1 + 2.2 * ((x - 1) ** 3) + 1.2 * ((x - 1) ** 2) if x < 1 else 1.0


def slide(draw, cx, y, txt, fnt, fill, prog, direction=1):
    w, h, b = text_w(draw, txt, fnt)
    off = (1 - ease_out(prog)) * (w + 120) * direction
    draw.text((cx - w / 2 - b[0] + off, y - b[1]), txt, font=fnt, fill=fill)


# ------------------------------------------------------------------ фоны
_grid = None


def grid_bg():
    global _grid
    if _grid is None:
        img = Image.new("RGB", (W, H), PAL["bg"])
        d = ImageDraw.Draw(img)
        for x in range(0, W + 1, 90):
            d.line([(x, 0), (x, H)], fill=PAL["line"], width=1)
        for y in range(0, H + 1, 90):
            d.line([(0, y), (W, y)], fill=PAL["line"], width=1)
        _grid = img
    return _grid.copy()


CODE_LINES = [
    "const scene = scenes[current];", "frame = render(t * 30)",
    "if (t > cut) next_scene();", "particles.forEach(p => p.update(dt));",
    "cube.rotateY(angle += 0.04);", "ctx.fillStyle = '#FF5A1A';",
    "for (let i = 0; i < 2600; i++) spawn(i);", "text.pop(easeOutCubic(p));",
    "bass.note(freq, time, 0.24);", "while (frame < total) draw(frame++);",
    "const scale = spring(stiffness = 180);", "mask = text_to_points(text)",
    "ring.expand(radius * easeIn(p));", "bars[i] = 40 + noise(i, t) * 220;",
    "glitch.slice(img, random_y, offset);", "// ни одного готового футажа",
    "camera.z = 4.5; project(vertex);", "wave = sin(2*pi*f*t) * env;",
    "if (!plugins) use_code(); // только код", "overlay.tc = timecode(frame);",
    "sticker.rotate(-2deg).scale(pop);", "finale: author",
]


def code_bg(frame, dark=132):
    img = Image.new("RGB", (W, H), PAL["bg"])
    d = ImageDraw.Draw(img)
    fnt = mono(25)
    scroll = (frame * 3) % 44
    y = -scroll - 20
    i0 = (frame * 3) // 44
    dim_accent = tuple(int(c * 0.55) for c in PAL["accent"])
    for k in range(48):
        line = CODE_LINES[(i0 + k) % len(CODE_LINES)]
        col = (86, 84, 80)
        if (i0 + k) % 5 == 0:
            col = dim_accent
        elif (i0 + k) % 7 == 0:
            col = (140, 138, 132)
        d.text((48 + ((i0 + k) % 3) * 26, y), line, font=fnt, fill=col)
        y += 44
    return Image.blend(img, Image.new("RGB", (W, H), (0, 0, 0)), dark / 255.0)


def bg_by_name(name, frame=0):
    if name == "accent":
        return Image.new("RGB", (W, H), PAL["accent"])
    if name == "light":
        return Image.new("RGB", (W, H), PAL["light"])
    if name == "grid":
        return grid_bg()
    if name == "code":
        return code_bg(frame)
    return Image.new("RGB", (W, H), PAL["bg"])


# ------------------------------------------------------------------ оверлей
def overlay(img, frame, scene_idx, n_scenes, total_frames, label, light=False):
    d = ImageDraw.Draw(img)
    ink = PAL["bg"] if light else PAL["ink"]
    accent = PAL["accent"]
    m, ln, th = 54, 38, 5
    for cx, cy, sx, sy in [(m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)]:
        d.line([(cx, cy), (cx + ln * sx, cy)], fill=ink, width=th)
        d.line([(cx, cy), (cx, cy + ln * sy)], fill=ink, width=th)
    fnt = mono(29)
    if (frame // 15) % 2 == 0:
        d.ellipse([m + 4, 92, m + 20, 108], fill=(230, 40, 30))
    d.text((m + 30, 84), "REC", font=fnt, fill=ink)
    tc = f"TC 00:00:{frame // FPS:02d}:{frame % FPS:02d}" if frame < 3600 * FPS else f"TC {frame // FPS}s"
    w, _, _ = text_w(d, tc, fnt)
    d.text((W - m - w, 84), tc, font=fnt, fill=ink)
    d.text((m, H - 118), f"SC {scene_idx + 1:02d} / {n_scenes:02d}", font=fnt, fill=ink)
    w, _, _ = text_w(d, label, fnt)
    d.text((W - m - w, H - 118), label, font=fnt, fill=ink)
    bw, by = 380, H - 74
    d.line([(m, by), (m + bw, by)], fill=PAL["muted"], width=5)
    d.line([(m, by), (m + bw * (frame + 1) / total_frames, by)], fill=accent, width=5)
    return img


def glitch(img, frame, strength=14):
    r = np.random.default_rng(1000 + frame)
    for _ in range(5):
        y = int(r.integers(0, H - 60))
        h = int(r.integers(12, 54))
        off = int(r.integers(-strength, strength + 1))
        img.paste(img.crop((0, y, W, y + h)), (off, y))
    return img


def norm_lines(lines):
    """Строка -> {'text':..., 'color':'ink'|'accent'|'bg'}; по умолчанию цвета чередуются."""
    out = []
    for i, ln in enumerate(lines or []):
        if isinstance(ln, str):
            out.append({"text": ln, "color": "accent" if i == 1 else "ink"})
        else:
            out.append({"text": str(ln.get("text", "")), "color": ln.get("color", "ink")})
    return out


def col(name):
    return PAL.get(name, PAL["ink"])


def label_top(d, txt, fill=None):
    if txt:
        d.text((54, 150), txt, font=mono(30, True), fill=fill or PAL["ink"])


# ================================================================ СЦЕНЫ
def sc_hook_code(s, frame, local, L, meta):
    """Фон из бегущего кода + строки по очереди + оранжевый счётчик."""
    img = code_bg(frame, dark=132)
    d = ImageDraw.Draw(img)
    lines = norm_lines(s.get("lines", []))
    sizes = []
    for ln in lines:
        fnt = fit(d, ln["text"], 940, s.get("size", 168))
        sizes.append(fnt)
    line_h = int(max([f.size for f in sizes], default=160) * 1.14)
    y = int(s.get("y", 700))
    for i, (ln, fnt) in enumerate(zip(lines, sizes)):
        start = 0.04 + i * 0.17
        if local / L >= start:
            slide(d, W // 2, y + i * line_h, ln["text"], fnt, col(ln["color"]),
                  (local / L - start) / 0.17, -1 if i % 2 == 0 else 1)
    cnt = s.get("counter")
    if cnt and local / L >= 0.58:
        p = (local / L - 0.58) / 0.34
        value = cnt.get("value", "auto")
        n = meta["renderer_lines"] if value == "auto" else int(value)
        txt = str(int(n * ease_out(p)))
        bw = int(560 * pop(p / 0.6))
        bh, y0 = 210, int(s.get("counter_y", 1330))
        x0 = W // 2 - bw // 2
        d.rectangle([x0, y0, x0 + bw, y0 + bh], fill=PAL["accent"])
        if bw > 300:
            center_text(d, W // 2, y0 + 26, txt, display(120), PAL["bg"])
            if cnt.get("suffix"):
                center_text(d, W // 2, y0 + bh + 22, cnt["suffix"], mono(28, True), PAL["ink"])
    return img


def sc_big_text(s, frame, local, L, meta):
    """Универсальная текстовая сцена: крупные строки на выбранном фоне."""
    img = bg_by_name(s.get("bg", "black"), frame)
    d = ImageDraw.Draw(img)
    label_top(d, s.get("label"), PAL["bg"] if s.get("bg") in ("light", "accent") else None)
    lines = norm_lines(s.get("lines", []))
    sizes = [fit(d, ln["text"], 940, s.get("size", 190)) for ln in lines]
    line_h = int(max([f.size for f in sizes], default=180) * 1.14)
    y0 = (H - line_h * max(1, len(lines))) // 2 - 60
    for i, (ln, fnt) in enumerate(zip(lines, sizes)):
        start = 0.06 + i * 0.16
        if local / L < start:
            continue
        p = (local / L - start) / 0.16
        if s.get("effect", "slide") == "pop":
            sc = pop(p)
            f2 = fit(d, ln["text"], int(940 * sc), int(fnt.size * sc))
            center_text(d, W // 2, y0 + i * line_h, ln["text"], f2, col(ln["color"]))
        else:
            slide(d, W // 2, y0 + i * line_h, ln["text"], fnt, col(ln["color"]), p,
                  -1 if i % 2 == 0 else 1)
    if s.get("footer") and local / L > 0.55:
        center_text(d, W // 2, H - 420, s["footer"], mono(30, True), PAL["muted"])
    return img


def sc_kinetic(s, frame, local, L, meta):
    """Оранжевый фон, вертикальное слово, контурные колонки по краям."""
    img = Image.new("RGB", (W, H), PAL["accent"])
    d = ImageDraw.Draw(img)
    word = s.get("word", "ДВИЖЕНИЕ")
    side = display(150)
    for col_x, direction in [(36, 1), (W - 118, -1)]:
        off = (local * 7 * direction) % 360
        for k in range(-2, 8):
            y = k * 360 + (off if direction > 0 else 360 - off)
            tile = Image.new("RGBA", (720, 190), (0, 0, 0, 0))
            td = ImageDraw.Draw(tile)
            td.text((6, 0), word, font=side, fill=PAL["accent"] + (255,),
                    stroke_width=3, stroke_fill=PAL["bg"] + (255,))
            tile = tile.rotate(90, expand=True)
            img.paste(tile, (col_x - 40, int(y) - 360), tile)
    d = ImageDraw.Draw(img)
    for i, yy in enumerate([330, 356, 382, 1490, 1516, 1542]):
        shift = ((local * 10) % 240) - 120 if i < 3 else 120 - ((local * 10) % 240)
        d.line([(shift, yy), (W + shift, yy)], fill=PAL["bg"], width=7)
    big = Image.new("RGBA", (1500, 330), (0, 0, 0, 0))
    bd = ImageDraw.Draw(big)
    bd.text((10, 10), word, font=fit(bd, word, 1460, 265), fill=PAL["bg"] + (255,))
    big = big.rotate(90, expand=True)
    rise = (1 - ease_out(local / max(1, L * 0.4))) * 700
    img.paste(big, (W // 2 - big.width // 2, int(H // 2 - big.height // 2 + rise)), big)
    d = ImageDraw.Draw(img)
    label_top(d, s.get("label"), PAL["bg"])
    return img


# ---- куб ----
def _face_texture(text, bg, fg, outline=True):
    sz = 640
    img = Image.new("RGBA", (sz, sz), bg + (255,))
    d = ImageDraw.Draw(img)
    if outline:
        d.rectangle([0, 0, sz - 1, sz - 1], outline=PAL["ink"] + (255,), width=10)
    if text:
        words = text.split()
        fnt = fit(d, max(words, key=len), 560, 150)
        total_h = len(words) * (fnt.size + 8)
        y = sz // 2 - total_h // 2
        for w_ in words:
            center_text(d, sz // 2, y, w_, fnt, fg)
            y += fnt.size + 8
    return img


def _coeffs(out_pts, in_pts):
    matrix, b = [], []
    for (x, y), (u, v) in zip(out_pts, in_pts):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        b.append(u)
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.append(v)
    return np.linalg.solve(np.array(matrix, float), np.array(b, float))


def _warp(img, texture, quad):
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    x0, y0 = max(0, int(min(xs))), max(0, int(min(ys)))
    x1, y1 = min(W, int(max(xs)) + 1), min(H, int(max(ys)) + 1)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return
    shifted = [(x - x0, y - y0) for x, y in quad]
    sz = texture.width
    coeffs = _coeffs(shifted, [(0, 0), (sz, 0), (sz, sz), (0, sz)])
    face = texture.transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, coeffs, Image.BILINEAR)
    img.paste(face, (x0, y0), face)


_VERTS = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
                    [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], float)
_NORMALS = np.array([[0, 0, 1], [1, 0, 0], [0, 0, -1], [-1, 0, 0], [0, -1, 0], [0, 1, 0]], float)
_FACE_IDX = [[4, 5, 6, 7], [5, 1, 2, 6], [1, 0, 3, 2], [0, 4, 7, 3], [0, 1, 5, 4], [7, 6, 2, 3]]
_cube_cache = {}


def _rot(v, ax, ay):
    cx, sx, cy, sy = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    return v @ rx.T @ ry.T


def sc_cube(s, frame, local, L, meta):
    """Куб чистой проекцией: грани faces[0..3], верх — top."""
    faces = (s.get("faces") or ["КОД", "РИТМ", "ЗВУК", "КАДР"])[:4]
    faces += [""] * (4 - len(faces))
    key = tuple(faces) + (s.get("top", "3D"),)
    if key not in _cube_cache:
        styles = [(PAL["bg"], PAL["ink"]), (PAL["light"], PAL["bg"]),
                  (PAL["accent"], PAL["bg"]), (PAL["light"], PAL["bg"])]
        tex = [_face_texture(t, bg, fg) for t, (bg, fg) in zip(faces, styles)]
        tex.append(_face_texture(s.get("top", "3D"), PAL["accent"], PAL["bg"]))
        tex.append(_face_texture("", (30, 30, 30), PAL["ink"]))
        _cube_cache[key] = tex
    tex = _cube_cache[key]
    img = grid_bg()
    p = local / max(1, L - 1)
    ay = ease_inout(p) * math.pi * 2
    ax = -0.46 + math.sin(local / 9) * 0.05
    pts3 = _rot(_VERTS, ax, ay)
    norms = _rot(_NORMALS, ax, ay)
    centre = np.array([W / 2, 900 + math.sin(local / 7) * 16])
    size, cam = 258, 4.6
    proj = []
    for v in pts3:
        f = cam / (cam - v[2])
        proj.append(centre + v[:2] * size * f)
    order = sorted(range(6), key=lambda i: pts3[_FACE_IDX[i]].mean(axis=0)[2])
    quads, front_name = [], ""
    names = faces + [s.get("top", "3D"), ""]
    for i in order:
        if norms[i][2] <= 0.12:
            continue
        quad = [tuple(proj[j]) for j in _FACE_IDX[i]]
        _warp(img, tex[i], quad)
        quads.append(quad)
        if i == int(np.argmax(norms[:, 2])):
            front_name = names[i]
    d = ImageDraw.Draw(img)
    for quad in quads:
        d.line(quad + [quad[0]], fill=PAL["ink"], width=7, joint="curve")
    label_top(d, s.get("label"))
    if front_name:
        d.text((70, 1480), "▸ " + front_name, font=mono(34, True), fill=PAL["accent"])
    return img


# ---- частицы ----
_particle_cache = {}


def sc_particles_text(s, frame, local, L, meta):
    """Вспышка -> кольцо -> текст из частиц -> разлёт. Текст: big над small."""
    count = int(s.get("count", 2600))
    key = (s.get("big", "15"), s.get("small", ""), count)
    rng = np.random.default_rng(129)
    if key not in _particle_cache:
        mask = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(mask)
        center_text(d, W // 2, 560, key[0], display(560), 255)
        if key[1]:
            center_text(d, W // 2, 1230, key[1], display(178), 255)
        ys, xs = np.nonzero(np.array(mask) > 0)
        pick = rng.choice(len(xs), size=count, replace=len(xs) < count)
        target = np.stack([xs[pick], ys[pick]], axis=1).astype(float)
        ring = np.stack([rng.uniform(0, 2 * np.pi, count), rng.uniform(80, 760, count)], axis=1)
        colors = [PAL["ink"] if r < 0.68 else (PAL["accent"] if r < 0.93 else (170, 170, 170))
                  for r in rng.random(count)]
        _particle_cache[key] = (target, ring, colors)
    target, ring, colors = _particle_cache[key]
    img = Image.new("RGB", (W, H), PAL["bg"])
    d = ImageDraw.Draw(img)
    label_top(d, s.get("label") or f"03 — {count:,} ЧАСТИЦ".replace(",", " "))
    centre = np.array([W / 2, 920.0])
    ring_xy = centre + np.stack([np.cos(ring[:, 0]) * ring[:, 1],
                                 np.sin(ring[:, 0]) * ring[:, 1] * 1.25], axis=1)
    p = local / L
    if p < 0.26:
        q = ease_out(p / 0.26)
        pos = centre + (ring_xy - centre) * q
        for (x, y), col_ in zip(pos, colors):
            d.line([(centre[0], centre[1]), (x, y)], fill=col_, width=3)
    elif p < 0.48:
        q = ease_inout((p - 0.26) / 0.22)
        pos = ring_xy * (1 - q) + target * q
        for (x, y), col_ in zip(pos, colors):
            d.rectangle([x - 3, y - 3, x + 3, y + 3], fill=col_)
    elif p < 0.82:
        jit_rng = np.random.default_rng(500 + local)
        pos = target + jit_rng.uniform(-2.5, 2.5, target.shape)
        for (x, y), col_ in zip(pos, colors):
            d.rectangle([x - 3, y - 3, x + 3, y + 3], fill=col_)
    else:
        q = (p - 0.82) / 0.18
        direction = target - centre
        direction = direction / (np.linalg.norm(direction, axis=1, keepdims=True) + 1e-6)
        pos = target + direction * (q ** 2) * 700
        for (x, y), (tx, ty), col_ in zip(pos, target, colors):
            d.line([(tx, ty), (x, y)], fill=col_, width=3)
    return img


_bar_seed = np.random.default_rng(3).uniform(0.25, 1.0, 28)


def sc_counter(s, frame, local, L, meta):
    """Большой счётчик 0 -> to, эквалайзер, подписи meta[0..2] внизу."""
    img = grid_bg()
    d = ImageDraw.Draw(img)
    label_top(d, s.get("label"))
    to = int(s.get("to", 450))
    done_at = 0.74
    n = int(to * ease_out((local / L) / done_at))
    done = local / L >= done_at
    fnt = fit(d, str(to), 940, 330)
    txt = f"{n:03d}" if to < 1000 else str(n)
    w, _, _ = text_w(d, txt, fnt)
    d.text(((W - w) / 2, 640), txt, font=fnt, fill=PAL["accent"] if done else PAL["ink"])
    if done and s.get("suffix"):
        center_text(d, W // 2, 1010, s["suffix"], display(90), PAL["ink"])
    for i in range(28):
        bh = _bar_seed[i] * 190 * (0.55 + 0.45 * math.sin(local / 3.1 + i * 1.7))
        x = 84 + i * 33
        d.rectangle([x, 1420 - bh, x + 19, 1420],
                    fill=PAL["ink"] if i % 6 == 0 else PAL["accent"])
    d.line([(70, 1420), (1010, 1420)], fill=PAL["muted"], width=3)
    meta_l = s.get("meta") or ["30 FPS", "1080×1920", "15.0 S"]
    fnt = mono(28)
    if len(meta_l) > 0:
        d.text((70, 1450), meta_l[0], font=fnt, fill=PAL["ink"])
    if len(meta_l) > 1:
        center_text(d, W // 2, 1450, meta_l[1], mono(28), PAL["ink"])
    if len(meta_l) > 2:
        w, _, _ = text_w(d, meta_l[2], fnt)
        d.text((W - 70 - w, 1450), meta_l[2], font=fnt, fill=PAL["ink"])
    return img


def sc_geometry(s, frame, local, L, meta):
    """Вращающиеся квадраты/окружности + сменяющиеся стикеры-плашки."""
    img = Image.new("RGB", (W, H), PAL["bg"])
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, 900
    for layer in range(7):
        r = 150 + layer * 105
        ang = local * (0.9 if layer % 2 == 0 else -0.7) * (1 + layer * 0.12)
        col_ = PAL["accent"] if layer % 3 == 0 else PAL["ink"]
        square = []
        for k in range(4):
            a = math.radians(ang + k * 90 + layer * 12)
            square.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        d.line(square + [square[0]], fill=col_, width=5)
        d.ellipse([cx - r * 0.72, cy - r * 0.72, cx + r * 0.72, cy + r * 0.72],
                  outline=col_, width=3)
    stickers = s.get("stickers") or ["БЕЗ ПЛАГИНОВ", "ТОЛЬКО КОД"]
    seg = L / len(stickers)
    idx = min(len(stickers) - 1, int(local // seg))
    sub = local % seg
    txt = stickers[idx]
    bg = PAL["accent"] if idx == len(stickers) - 1 else PAL["light"]
    scale = pop(sub / max(1, seg * 0.5))
    fnt = fit(d, txt, int(760 * scale), int(104 * scale))
    w, h, b = text_w(d, txt, fnt)
    pad_x, pad_y = 42, 26
    sticker = Image.new("RGBA", (int(w + pad_x * 2), int(h + pad_y * 2)), bg + (255,))
    sd = ImageDraw.Draw(sticker)
    sd.text((pad_x - b[0], pad_y - b[1]), txt, font=fnt, fill=PAL["bg"] + (255,))
    sticker = sticker.rotate(-2 if idx < len(stickers) - 1 else 1.5, expand=True,
                             resample=Image.BILINEAR)
    img.paste(sticker, (cx - sticker.width // 2, cy - sticker.height // 2), sticker)
    return img


def sc_showreel(s, frame, local, L, meta):
    """Светлая сцена: две крупные строки, подпись, инверсия в конце."""
    p = local / L
    invert = p >= 0.85 and (local // 3) % 2 == 0
    bg = PAL["bg"] if invert else PAL["light"]
    ink = PAL["light"] if invert else PAL["bg"]
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    for k in range(9):
        y = (k * 260 + (local * 9) % 260) - 120
        d.line([(0, y), (W, y)], fill=PAL["ink"] if invert else (196, 190, 178), width=3)
    lines = norm_lines(s.get("lines", ["SHOW", "REEL"]))
    if len(lines) > 0:
        slide(d, W // 2, 700, lines[0]["text"], fit(d, lines[0]["text"], 940, 300), ink,
              (local / L) / 0.2, -1)
    if len(lines) > 1:
        slide(d, W // 2, 1010, lines[1]["text"], fit(d, lines[1]["text"], 940, 300),
              PAL["accent"], max(0.0, (local / L - 0.06) / 0.2), 1)
    if s.get("sub") and local / L > 0.3:
        center_text(d, W // 2, 1400, s["sub"], mono(30, True), ink, tracking=2)
    if local / L < 0.1 or p >= 0.85:
        img = glitch(img, frame, 10)
    return img


def sc_finale(s, frame, local, L, meta):
    """Финал: автор крупно, оранжевая черта, подписи."""
    img = Image.new("RGB", (W, H), PAL["bg"])
    d = ImageDraw.Draw(img)
    author = s.get("title") or meta["author"]
    scale = pop((local / L) / 0.22)
    fnt = fit(d, author, int(900 * scale), int(245 * scale))
    center_text(d, W // 2, 760, author, fnt, PAL["ink"])
    if local / L > 0.14:
        uw = int(760 * ease_out(((local / L) - 0.14) / 0.22))
        d.rectangle([W // 2 - uw // 2, 1045, W // 2 + uw // 2, 1061], fill=PAL["accent"])
    if s.get("sub") and local / L > 0.25:
        center_text(d, W // 2, 1120, s["sub"], mono(31), PAL["ink"])
    extras = s.get("extra") or []
    for i, line in enumerate(extras):
        if local / L > 0.38 + i * 0.1:
            center_text(d, W // 2, 1215 + i * 70, line, mono(29 - i * 3),
                        PAL["muted"] if i == 0 else (86, 84, 80))
    return img


BUILDERS = {
    "hook_code": sc_hook_code,
    "big_text": sc_big_text,
    "kinetic": sc_kinetic,
    "cube": sc_cube,
    "particles_text": sc_particles_text,
    "counter": sc_counter,
    "geometry": sc_geometry,
    "showreel": sc_showreel,
    "finale": sc_finale,
}
LIGHT_TYPES = {"showreel"}  # сцены со светлым фоном (тёмный оверлей)


# ------------------------------------------------------------------ звук
SR = 48000


def _env(n, attack=0.004, decay=0.18):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def _add(track, sig, at_sec):
    at = int(at_sec * SR)
    end = min(len(track), at + len(sig))
    if end > at:
        track[at:end] += sig[:end - at]


def make_soundtrack(path, total_s, boundaries, finale_at, bpm=120):
    n = int(SR * total_s)
    mix = np.zeros(n)
    noise = np.random.default_rng(7).standard_normal(n + SR)
    beat = 60 / bpm
    roots = [55.0, 55.0, 43.65, 49.0]
    beat_end = finale_at if finale_at is not None else total_s
    step = 0
    while step * beat < beat_end - 0.05:
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
        step += 1
    for t0 in boundaries[1:]:
        tt = np.arange(int(SR * 0.4)) / SR
        sweep = np.sin(2 * np.pi * (700 * np.exp(-tt * 7) + 60) * tt) * np.exp(-tt * 9)
        _add(mix, sweep * 0.35, t0)
    if finale_at is not None and finale_at > 1.6:
        rt = np.arange(int(SR * 1.5)) / SR
        riser = np.sin(2 * np.pi * (180 * np.exp(rt * 1.25)) * rt) * (rt / 1.5) ** 2
        _add(mix, riser * 0.10, finale_at - 1.5)
        tt = np.arange(int(SR * 2.2)) / SR
        chord = sum(np.sin(2 * np.pi * f * tt) for f in (220.0, 261.63, 329.63)) / 3
        _add(mix, chord * np.exp(-tt * 1.5) * 0.28, finale_at)
    mix = np.tanh(mix * 1.15)
    mix *= 0.89 / max(1e-6, np.max(np.abs(mix)))
    fade = int(SR * 0.25)
    mix[-fade:] *= np.linspace(1, 0, fade)
    pcm = (mix * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(np.repeat(pcm[:, None], 2, axis=1).tobytes())


# ------------------------------------------------------------------ главный рендер
def main():
    ap = argparse.ArgumentParser(description="Видео кодом по JSON-сценарию")
    ap.add_argument("config")
    ap.add_argument("--out", default=None)
    ap.add_argument("--preview", action="store_true", help="360×640, crf 28")
    ap.add_argument("--no-audio", action="store_true")
    args = ap.parse_args()

    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("Нужны зависимости: pip install Pillow numpy imageio-ffmpeg")

    cfg_path = Path(args.config)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    for key, val in (cfg.get("palette") or {}).items():
        if key in PAL:
            PAL[key] = hex2rgb(val)
    global FPS
    FPS = int(cfg.get("fps", 30))
    out_w = 360 if args.preview else int(cfg.get("width", 1080))
    out_h = 640 if args.preview else int(cfg.get("height", 1920))
    author = cfg.get("author", "AUTHOR")

    scenes = cfg["scenes"]
    spans, t = [], 0
    for s in scenes:
        if s["type"] not in BUILDERS:
            sys.exit(f"Неизвестный тип сцены: {s['type']}. Доступно: {sorted(BUILDERS)}")
        n = max(1, round(float(s.get("duration", 1.8)) * FPS))
        spans.append((t, n, s))
        t += n
    total = t
    total_s = total / FPS
    out = Path(args.out) if args.out else cfg_path.with_suffix("").with_name(cfg_path.stem + "_out")
    out.mkdir(parents=True, exist_ok=True)
    meta = {"author": author,
            "renderer_lines": len(Path(__file__).read_text(encoding="utf-8").splitlines())}
    ov = cfg.get("overlay") or {}
    ov_label = ov.get("label", f"{author} / MOTION")
    ov_on = ov.get("enabled", True)

    def render_frame(frame):
        for idx, (start, length, s) in enumerate(spans):
            if start <= frame < start + length:
                local = frame - start
                img = BUILDERS[s["type"]](s, frame, local, length, meta)
                if local < 4 and s["type"] not in LIGHT_TYPES:
                    img = glitch(img, frame)
                light = s["type"] in LIGHT_TYPES and not (
                    s["type"] == "showreel" and local / length >= 0.85 and (local // 3) % 2 == 0)
                if s.get("bg") == "light":
                    light = True
                return overlay(img, frame, idx, len(spans), total, ov_label, light) if ov_on else img
        return spans[-1][2] and render_frame(total - 1)

    name = cfg.get("output", "клип.mp4")
    if args.preview:
        name = "черновик.mp4"
    silent = out / "_silent.mp4"
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{BASE_W}x{BASE_H}", "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264",
           "-preset", "veryfast", "-crf", "28" if args.preview else "20",
           "-pix_fmt", "yuv420p", str(silent)]
    if (out_w, out_h) != (BASE_W, BASE_H):
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{BASE_W}x{BASE_H}", "-r", str(FPS), "-i", "-", "-an",
               "-vf", f"scale={out_w}:{out_h}", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "28" if args.preview else "20", "-pix_fmt", "yuv420p", str(silent)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for frame in range(total):
        proc.stdin.write(render_frame(frame).tobytes())
        if frame % 90 == 0:
            print(f"кадр {frame}/{total}", flush=True)
    proc.stdin.close()
    proc.wait()

    final = out / name
    if args.no_audio or not (cfg.get("audio") or {}).get("enabled", True):
        silent.replace(final)
    else:
        wav = out / "_sound.wav"
        boundaries = [start / FPS for start, _, _ in spans]
        finale_at = None
        for start, _, s in spans:
            if s["type"] == "finale":
                finale_at = start / FPS
        make_soundtrack(wav, total_s, boundaries, finale_at,
                        bpm=int((cfg.get("audio") or {}).get("bpm", 120)))
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", str(final)], check=True)
        silent.unlink(missing_ok=True)
        wav.unlink(missing_ok=True)
    print(json.dumps({"готово": str(final), "кадров": total, "секунд": total_s,
                      "размер": f"{out_w}x{out_h}", "fps": FPS}, ensure_ascii=False))


if __name__ == "__main__":
    main()
