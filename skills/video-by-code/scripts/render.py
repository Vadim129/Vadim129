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
    size = max(1, int(size))
    key = (name, size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(str(FONT_DIR / name), size)
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


# ---- Telegram/чат-сцены (персонаж с фото + пузырьки сообщений) ----
_img_cache = {}


def load_image(path, base_dir):
    key = str(path)
    if key not in _img_cache:
        p = Path(path)
        if not p.is_absolute():
            p = Path(base_dir) / p
        _img_cache[key] = Image.open(p).convert("RGB")
    return _img_cache[key]


def paste_round(img, photo, box, radius=48, border=None, border_w=8):
    """Фото в скруглённой карточке (как стикер в чате)."""
    x, y, w, h = [int(v) for v in box]
    card = photo.copy()
    card.thumbnail((w * 2, h * 2))
    left = max(0, (card.width - w) // 2)
    top = max(0, (card.height - h) // 2)
    card = card.crop((left, top, left + w, top + h)).resize((w, h))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    img.paste(card, (x, y), mask)
    if border:
        ImageDraw.Draw(img).rounded_rectangle([x, y, x + w - 1, y + h - 1],
                                              radius=radius, outline=border, width=border_w)
    return img


def paste_circle_avatar(img, photo, cx, cy, r, ring=None, ring_w=6):
    size = int(r * 2)
    av = photo.copy()
    av.thumbnail((size * 2, size * 2))
    left = max(0, (av.width - size) // 2)
    top = max(0, (av.height - size) // 2)
    av = av.crop((left, top, left + size, top + size)).resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    img.paste(av, (int(cx - r), int(cy - r)), mask)
    if ring:
        ImageDraw.Draw(img).ellipse([cx - r, cy - r, cx + r, cy + r], outline=ring, width=ring_w)
    return img


def draw_plane(d, cx, cy, scale, color):
    """Самолётик Telegram полигоном (без шрифтовых глифов)."""
    pts = [(-1.0, 0.15), (1.0, -0.9), (0.25, 0.95), (-0.05, 0.35), (-0.55, 0.55)]
    poly = [(cx + x * scale, cy + y * scale) for x, y in pts]
    d.polygon(poly, fill=color)
    d.line([(cx - 0.05 * scale, cy + 0.35 * scale), (cx + 1.0 * scale, cy - 0.9 * scale)],
           fill=color, width=max(2, int(scale * 0.06)))


def chat_header(img, s, photo, base_dir):
    d = ImageDraw.Draw(img)
    bar = s.get("header_color", "#17212B")
    d.rectangle([0, 0, W, 190], fill=hex2rgb(bar) if isinstance(bar, str) else bar)
    d.text((48, 62), "‹", font=display(90), fill=PAL["ink"])
    if photo is not None:
        paste_circle_avatar(img, photo, 190, 95, 62)
    head = s.get("header") or {}
    d.text((280, 48), head.get("title", "Чат"), font=mono(40, True), fill=PAL["ink"])
    d.text((280, 108), head.get("sub", "online"), font=mono(30), fill=PAL["muted"])
    d.text((W - 90, 62), "⋮", font=display(60), fill=PAL["ink"])
    return img


def wrap_text(d, txt, fnt, max_w):
    words, lines, cur = txt.split(), [], ""
    for w_ in words:
        trial = (cur + " " + w_).strip()
        if d.textbbox((0, 0), trial, font=fnt)[2] <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def draw_bubble(img, txt, side, y, s, rot=0, style="bubble"):
    """Один пузырёк; возвращает его высоту. side: left=бот, right=собеседник."""
    meas = ImageDraw.Draw(img)
    fnt = font("Montserrat_700Bold.ttf", int(s.get("bubble_size", 46)))
    lines = wrap_text(meas, txt, fnt, 640)
    line_h = int(fnt.size * 1.22)
    tw = max(meas.textbbox((0, 0), ln, font=fnt)[2] for ln in lines)
    bw, bh = tw + 56, line_h * len(lines) + 42
    if style == "cloud":
        bw, bh = bw + 30, bh + 24
    x = 56 if side == "left" else W - 56 - bw
    layer = Image.new("RGBA", (int(bw + 40), int(bh + 40)), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    fillc = s.get("bot_bubble", "#182533") if side == "left" else s.get("user_bubble", "#2B5278")
    fillc = hex2rgb(fillc) if isinstance(fillc, str) else fillc
    radius = 44 if style == "cloud" else 34
    ld.rounded_rectangle([20, 10, 20 + bw, 10 + bh], radius=radius, fill=fillc + (255,))
    if style == "bubble":  # хвостик
        tx = 52 if side == "left" else bw - 30
        ld.polygon([(20 + tx, 10 + bh - 14), (20 + tx + 26, 10 + bh - 14),
                    (20 + tx + (4 if side == "left" else 22), 10 + bh + 12)], fill=fillc + (255,))
    for i, ln in enumerate(lines):
        ld.text((48, 28 + i * line_h), ln, font=fnt, fill=(255, 255, 255, 255))
    if rot:
        layer = layer.rotate(rot, expand=True, resample=Image.BILINEAR)
    img.paste(layer, (int(x - 20), int(y - 10)), layer)
    return bh + 22


def character_pose(s, local, L):
    """(dx, dy, scale, angle) персонажа по эффекту сцены."""
    effect = s.get("image_effect", "float")
    p_in = pop((local / L) / 0.22)
    dx = dy = 0
    angle = 0.0
    scale = p_in
    if effect == "shy":
        angle = -3.0
        dy = int(math.sin(local / 6) * 6)
    elif effect == "vibrate":
        r = np.random.default_rng(700 + local)
        dx, dy = int(r.integers(-9, 10)), int(r.integers(-9, 10))
        scale = 1.0
    elif effect == "pulse":
        scale = 1.0 + 0.035 * math.sin(local / 4.5)
    elif effect == "invite":
        dy = -abs(int(math.sin(local / 5) * 22))
        scale = 1.0
    elif effect == "float":
        dy = int(math.sin(local / 8) * 12)
        scale = 1.0
    return dx, dy, scale, angle


def sc_tg_chat(s, frame, local, L, meta):
    """Чат: шапка, персонаж с фото, пузырьки по расписанию, кнопка."""
    img = Image.new("RGB", (W, H), hex2rgb(s.get("chat_bg", "#0E1621")))
    d = ImageDraw.Draw(img)
    for gx in range(60, W, 150):  # тихий «паттерн» чата
        for gy in range(240, H - 60, 150):
            d.ellipse([gx, gy, gx + 7, gy + 7], fill=(28, 38, 50))
    photo = load_image(s["image"], meta["base_dir"]) if s.get("image") else None
    if photo is not None and not s.get("hide_image"):
        size = int(s.get("image_size", 640))
        cx = int(s.get("image_cx", W // 2))
        cy = int(s.get("image_cy", 1090))
        dx, dy, scale, angle = character_pose(s, local, L)
        size2 = max(40, int(size * scale))
        tile = Image.new("RGBA", (size2 + 30, size2 + 30), (0, 0, 0, 0))
        paste_round(tile, photo, (15, 15, size2, size2), radius=56,
                    border=(255, 255, 255), border_w=9)
        if angle:
            tile = tile.rotate(angle, expand=True, resample=Image.BILINEAR)
        img.paste(tile, (cx - tile.width // 2 + dx, cy - tile.height // 2 + dy), tile)
        if s.get("image_effect") == "pulse":  # пульс-кольца вокруг
            d = ImageDraw.Draw(img)
            for k in range(3):
                r = 360 + ((local * 9 + k * 130) % 390)
                alpha = max(0, 120 - (r - 360) // 3)
                ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ImageDraw.Draw(ring).ellipse([cx - r, cy - r, cx + r, cy + r],
                                             outline=PAL["accent"] + (alpha,), width=6)
                img = Image.alpha_composite(img.convert("RGBA"), ring).convert("RGB")
    d = ImageDraw.Draw(img)
    first_bubble_at = min([float(b.get("at", 0.05)) for b in (s.get("bubbles") or [])],
                          default=0.16)
    if s.get("typing") and local / L < first_bubble_at:
        dots = "•" * (1 + (local // 8) % 3)
        draw_bubble(img, f"{s.get('typing_text', 'печатает')} {dots}", "left", 240, s)
    if s.get("center_avatar") and photo is not None:
        paste_circle_avatar(img, photo, W // 2, 800, 128, ring=PAL["accent"], ring_w=6)
        center_text(ImageDraw.Draw(img), W // 2, 960,
                    s.get("center_name", ""), mono(34, True), PAL["ink"])
    y = int(s.get("bubbles_y", 240))
    for b in s.get("bubbles") or []:
        if local / L < float(b.get("at", 0.05)):
            continue
        yy = int(b["y"]) if "y" in b else y
        h = draw_bubble(img, b["text"], b.get("side", "left"), yy, s,
                        rot=float(b.get("rot", 0)), style=b.get("style", "bubble"))
        if "y" not in b:
            y += h
    btn = s.get("button")
    if btn and local / L >= float(btn.get("at", 0.4)):
        morph_at = float(btn.get("morph_at", 2.0))
        mprog = clamp01(((local / L) - morph_at) / 0.12) if local / L >= morph_at else 0.0
        morphing = mprog >= 0.5
        txt = btn.get("morph_to", btn["text"]) if morphing else btn["text"]
        bw, bh = int(560 * (1 - 0.28 * math.sin(math.pi * mprog))), 118
        bx, by = W // 2 - bw // 2, int(btn.get("y", 1620))
        glow = pop(((local / L) - float(btn.get("at", 0.4))) / 0.15)
        d.rounded_rectangle([bx - 8, by - 8, bx + bw + 8, by + bh + 8], radius=62,
                            outline=PAL["accent"], width=3)
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=56,
                            fill=(23, 33, 43) if morphing else PAL["accent"])
        fnt = fit(d, txt, 470, 48, name="JetBrainsMono_700Bold.ttf" if morphing
                  else "Montserrat_800ExtraBold.ttf")
        if not morphing:
            draw_plane(d, bx + 78, by + bh // 2, 34, (255, 255, 255))
            center_text(d, bx + bw // 2 + 26, by + 32, txt, fnt, (255, 255, 255))
        else:
            center_text(d, bx + bw // 2, by + 36, txt, fnt, PAL["accent"])
    chat_header(img, s, photo, meta["base_dir"])
    return img


def sc_tg_intro(s, frame, local, L, meta):
    """Заставка чата: самолёт в круге, название, аватар бота, кольца пинга."""
    img = Image.new("RGB", (W, H), hex2rgb(s.get("chat_bg", "#0E1621")))
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, 690
    for k in range(3):  # расходящиеся кольца «пинга»
        r = 130 + ((local * 7 + k * 90) % 270)
        ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse([cx - r, cy - r, cx + r, cy + r],
                                     outline=PAL["accent"] + (max(0, 140 - (r - 130) // 2),),
                                     width=5)
        img = Image.alpha_composite(img.convert("RGBA"), ring).convert("RGB")
    d = ImageDraw.Draw(img)
    sc = pop((local / L) / 0.25)
    r = int(118 * sc)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PAL["accent"])
    draw_plane(d, cx - 8, cy + 4, 95 * sc, (255, 255, 255))
    if local / L > 0.3:
        center_text(d, cx, cy + 190, s.get("title", "Acid Crunch"),
                    fit(d, s.get("title", "Acid Crunch"), 900, 96), PAL["ink"])
    if s.get("image") and local / L > 0.5:
        photo = load_image(s["image"], meta["base_dir"])
        paste_circle_avatar(img, photo, cx, cy + 470, int(105 * pop(((local / L) - 0.5) / 0.3)),
                            ring=PAL["accent"], ring_w=7)
    if s.get("sub") and local / L > 0.62:
        center_text(d, cx, cy + 620, s["sub"], mono(34), PAL["muted"])
    return img


def sc_tg_outro(s, frame, local, L, meta):
    """Финал чата: логотип + название + строка «смотри дальше»."""
    img = Image.new("RGB", (W, H), hex2rgb(s.get("chat_bg", "#0E1621")))
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, 640
    sc = pop((local / L) / 0.3)
    r = int(105 * sc)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PAL["accent"])
    draw_plane(d, cx - 6, cy + 3, 84 * sc, (255, 255, 255))
    if s.get("image") and local / L > 0.2:
        photo = load_image(s["image"], meta["base_dir"])
        paste_circle_avatar(img, photo, cx, cy + 350, 88, ring=PAL["accent"], ring_w=6)
    if local / L > 0.15:
        center_text(d, cx, cy + 180, s.get("title", "Acid Crunch"),
                    fit(d, s.get("title", "Acid Crunch"), 900, 92), PAL["ink"])
    if local / L > 0.35:
        center_text(d, cx, cy + 520, s.get("text", "Смотри дальше"),
                    fit(d, s.get("text", "Смотри дальше"), 880, 74), PAL["accent"])
    return img


def _shade(rgb, f):
    return tuple(max(0, min(255, int(c * f))) for c in rgb)


def _pop_title_line(d, cx, y, line, p):
    txt = line["text"] if isinstance(line, dict) else str(line)
    color_name = line.get("color", "ink") if isinstance(line, dict) else "ink"
    size = int(line.get("size", 110)) if isinstance(line, dict) else 110
    sc = pop(p / 0.35)
    fnt = fit(d, txt, int(940 * sc), int(size * sc))
    w, h, b = text_w(d, txt, fnt)
    if isinstance(line, dict) and line.get("bg"):
        pad_x, pad_y = 34, 16
        rect = [cx - w / 2 - pad_x, y - pad_y, cx + w / 2 + pad_x, y + h + pad_y]
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle(rect, radius=26,
                                                fill=hex2rgb(line["bg"]) + (255,))
        return layer, (cx, y, txt, fnt, col(color_name) if color_name in PAL else hex2rgb(color_name), b, w, h)
    d.text((cx - w / 2 - b[0], y - b[1]), txt, font=fnt,
           fill=col(color_name) if color_name in PAL else hex2rgb(color_name))
    return None, None


def sc_pop_stage(s, frame, local, L, meta):
    """Яркая поп-сцена: крупный персонаж, заголовки, стикеры, облако, подпись диктора."""
    bg = hex2rgb(s.get("bg", "#FFC800"))
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    pattern = s.get("pattern", "sunburst")
    cx0, cy0 = W // 2, 1020
    if pattern == "sunburst":
        dark = _shade(bg, 0.88)
        ang0 = local * 0.7
        for k in range(24):
            if k % 2:
                continue
            a1 = math.radians(ang0 + k * 15)
            a2 = math.radians(ang0 + (k + 1) * 15)
            d.polygon([(cx0, cy0), (cx0 + 1500 * math.cos(a1), cy0 + 1500 * math.sin(a1)),
                       (cx0 + 1500 * math.cos(a2), cy0 + 1500 * math.sin(a2))], fill=dark)
    elif pattern == "halftone":
        dot = _shade(bg, 0.82)
        off = (local * 2) % 72
        for gx in range(-72, W + 72, 72):
            for gy in range(120, H, 72):
                r = 7 + ((gx + gy) % 5)
                d.ellipse([gx + off - r, gy - r, gx + off + r, gy + r], fill=dot)
    elif pattern == "stripes":
        dark = _shade(bg, 0.86)
        off = (local * 6) % 160
        for x in range(-H, W + 160, 160):
            d.polygon([(x + off, 0), (x + 70 + off, 0), (x + 70 + off - H, H),
                       (x + off - H, H)], fill=dark)
    p = local / L
    if s.get("badge") and p > 0.03:
        bt = s["badge"]
        fnt = mono(30, True)
        w, _, b = text_w(d, bt, fnt)
        bx, by = W // 2 - (w + 52) / 2, 64
        d.rounded_rectangle([bx, by, bx + w + 52, by + 58], radius=29, fill=PAL["bg"])
        d.text((bx + 26 - b[0], by + 12), bt, font=fnt, fill=(255, 255, 255))
    title_y = int(s.get("title_y", 170))
    layers = []
    for i, line in enumerate(s.get("title") or []):
        at = float(line.get("at", 0.04 + i * 0.08)) if isinstance(line, dict) else 0.04 + i * 0.08
        if p < at:
            continue
        size = int(line.get("size", 110)) if isinstance(line, dict) else 110
        layer, pending = _pop_title_line(d, W // 2, title_y, line, p - at)
        if layer is not None:
            layers.append((layer, pending))
        title_y += int(size * 1.18)
    for layer, _pending in layers:
        img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    d = ImageDraw.Draw(img)
    for _layer, pending in layers:
        if pending:
            cx, y, txt, fnt, fillc, b, w, h = pending
            d.text((cx - w / 2 - b[0], y - b[1]), txt, font=fnt, fill=fillc)
    photo = load_image(s["image"], meta["base_dir"]) if s.get("image") else None
    if photo is not None:
        size = int(s.get("image_size", 680))
        cx = int(s.get("image_cx", W // 2))
        cy = int(s.get("image_cy", 1100))
        dx, dy, escale, angle = character_pose(s, local, L)
        entr = pop(p / 0.2) if s.get("image_effect", "float") == "float" else 1.0
        size2 = max(40, int(size * escale * entr))
        shadow = Image.new("RGBA", (size2 + 60, size2 + 60), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle([34, 40, 34 + size2, 40 + size2],
                                                 radius=60, fill=(0, 0, 0, 110))
        img.paste(shadow, (cx - size2 // 2 - 30 + dx, cy - size2 // 2 - 30 + dy), shadow)
        tile = Image.new("RGBA", (size2 + 30, size2 + 30), (0, 0, 0, 0))
        paste_round(tile, photo, (15, 15, size2, size2), radius=56,
                    border=(255, 255, 255), border_w=14)
        if angle:
            tile = tile.rotate(angle, expand=True, resample=Image.BILINEAR)
        img.paste(tile, (cx - tile.width // 2 + dx, cy - tile.height // 2 + dy), tile)
        d = ImageDraw.Draw(img)
    cloud = s.get("cloud")
    if cloud and p >= float(cloud.get("at", 0.3)):
        cp = pop((p - float(cloud.get("at", 0.3))) / 0.25)
        meas = ImageDraw.Draw(img)
        fnt = font("Montserrat_700Bold.ttf", int(54 * cp))
        lines = wrap_text(meas, cloud["text"], fnt, 600)
        line_h = int(fnt.size * 1.2)
        tw = max(meas.textbbox((0, 0), ln, font=fnt)[2] for ln in lines)
        bw, bh = tw + 64, line_h * len(lines) + 48
        bx = int(cloud.get("x", W // 2 - bw // 2))
        by = int(cloud.get("y", 300))
        layer = Image.new("RGBA", (int(bw + 30), int(bh + 60)), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle([8, 8, 8 + bw, 8 + bh], radius=48, fill=(255, 255, 255, 255),
                             outline=(10, 10, 10, 255), width=7)
        ld.polygon([(bw // 2 - 10, 8 + bh - 6), (bw // 2 + 52, 8 + bh - 6),
                    (bw // 2 + 4, 8 + bh + 40)], fill=(255, 255, 255, 255),
                   outline=(10, 10, 10, 255), width=6)
        for i, ln in enumerate(lines):
            ld.text((40, 30 + i * line_h), ln, font=fnt, fill=(10, 10, 10, 255))
        img.paste(layer, (bx - 8, by - 8), layer)
        d = ImageDraw.Draw(img)
    for st in s.get("stickers") or []:
        if p < float(st.get("at", 0.2)):
            continue
        sp = pop((p - float(st.get("at", 0.2))) / 0.3)
        txt = st["text"]
        fnt = fit(ImageDraw.Draw(img), txt, int(int(st.get("max_w", 520)) * sp),
                  int(int(st.get("size", 52)) * sp), name="Montserrat_800ExtraBold.ttf")
        meas = ImageDraw.Draw(img)
        w, h, b = text_w(meas, txt, fnt)
        bgc = hex2rgb(st.get("bg", "#FFFFFF"))
        fgc = hex2rgb(st.get("color", "#0A0A0A"))
        pad_x, pad_y = 30, 18
        lw, lh = int(w + pad_x * 2), int(h + pad_y * 2)
        layer = Image.new("RGBA", (lw + 16, lh + 16), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        if st.get("style") == "burst":
            pts = []
            for k in range(24):
                rx = lw / 2 if k % 2 == 0 else lw / 3.4
                ry = lh * 0.46 if k % 2 == 0 else lh * 0.30
                a = math.pi * k / 12
                pts.append((lw / 2 + 8 + rx * math.cos(a), lh / 2 + 8 + ry * math.sin(a)))
            ld.polygon(pts, fill=bgc + (255,), outline=(10, 10, 10, 255), width=5)
        else:
            ld.rounded_rectangle([8, 8, 8 + lw, 8 + lh], radius=24, fill=bgc + (255,),
                                 outline=(10, 10, 10, 255), width=5)
        ld.text((8 + pad_x - b[0], 8 + pad_y - b[1]), txt, font=fnt, fill=fgc + (255,))
        if st.get("rot"):
            layer = layer.rotate(float(st["rot"]), expand=True, resample=Image.BILINEAR)
        img.paste(layer, (int(st.get("x", 60)), int(st.get("y", 400))), layer)
        d = ImageDraw.Draw(img)
    cap = s.get("caption")
    if cap and p >= float(cap.get("at", 0.05)):
        txt = cap["text"] if isinstance(cap, dict) else str(cap)
        meas = ImageDraw.Draw(img)
        fnt = font("Montserrat_700Bold.ttf", 46)
        lines = wrap_text(meas, txt, fnt, 880)
        line_h = 56
        bh = line_h * len(lines) + 42
        by = H - 120 - bh
        d.rounded_rectangle([44, by, W - 44, by + bh], radius=30, fill=(8, 8, 8))
        d.rounded_rectangle([44, by, 196, by + 44], radius=22, fill=PAL["accent"])
        d.text((66, by + 8), "ДИКТОР", font=mono(24, True), fill=(255, 255, 255))
        for i, ln in enumerate(lines):
            center_text(d, W // 2, by + 34 + i * line_h, ln, fnt, (255, 255, 255))
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
    "tg_intro": sc_tg_intro,
    "tg_chat": sc_tg_chat,
    "tg_outro": sc_tg_outro,
    "pop_stage": sc_pop_stage,
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


def _event_sig(kind, noise):
    """Короткие эффекты для чат-сцен: пинг, бум, шип, клик и др."""
    if kind == "ping":
        tt = np.arange(int(SR * 0.35)) / SR
        sig = (np.sin(2 * np.pi * 1318 * tt) * np.exp(-tt * 14)
               + 0.6 * np.sin(2 * np.pi * 1760 * np.maximum(0, tt - 0.07))
               * np.exp(-np.maximum(0, tt - 0.07) * 16) * (tt > 0.07))
        return sig * 0.5
    if kind == "pop":
        tt = np.arange(int(SR * 0.12)) / SR
        return np.sin(2 * np.pi * (480 - 2600 * tt) * tt) * np.exp(-tt * 30) * 0.5
    if kind == "boom":
        tt = np.arange(int(SR * 0.4)) / SR
        return (np.sin(2 * np.pi * (150 * np.exp(-tt * 9) + 42) * tt) * np.exp(-tt * 8)
                + noise[:len(tt)] * np.exp(-tt * 22) * 0.4) * 0.8
    if kind == "hiss":
        tt = np.arange(int(SR * 0.55)) / SR
        return np.diff(noise[:len(tt) + 1]) * np.exp(-tt * 5) * 0.34
    if kind == "click":
        tt = np.arange(int(SR * 0.06)) / SR
        return (np.sin(2 * np.pi * 1900 * tt) + noise[:len(tt)] * 0.6) * np.exp(-tt * 90) * 0.5
    if kind == "whoosh":
        tt = np.arange(int(SR * 0.6)) / SR
        env = np.sin(np.pi * np.clip(tt / 0.6, 0, 1)) ** 2
        return (noise[:len(tt)] * 0.24 + np.sin(2 * np.pi * (280 + 900 * tt) * tt) * 0.05) * env
    if kind == "pulse":
        tt = np.arange(int(SR * 0.22)) / SR
        return np.sin(2 * np.pi * 68 * tt) * np.exp(-tt * 16) * 0.7
    if kind == "chord":
        tt = np.arange(int(SR * 1.1)) / SR
        sig = sum(np.sin(2 * np.pi * f * tt) for f in (261.63, 329.63, 392.0, 523.25)) / 4
        return sig * np.exp(-tt * 2.6) * 0.5
    return np.zeros(1)


def _chiptune(mix, noise, total_s, bpm, sections=None):
    """Ретро-фон: квадратная арпеджио-мелодия + треугольный бас, тихо.

    sections: [{start, end, gain, hats, octave}] — музыка под структуру
    (куплет тише, припев ярче/выше, бридж без хэтов). Без sections —
    прежнее поведение."""
    eighth = 60 / bpm / 2
    melody = [523, 659, 784, 659, 440, 523, 659, 523,
              349, 440, 523, 440, 392, 494, 587, 494]
    basses = [131, 98, 110, 87]
    def _sec(t0):
        for sec in sections or []:
            if float(sec.get("start", 0)) <= t0 < float(sec.get("end", total_s)):
                return (float(sec.get("gain", 1.0)), bool(sec.get("hats", True)),
                        int(sec.get("octave", 0)))
        return 1.0, True, 0
    step = 0
    while step * eighth < total_s:
        t0 = step * eighth
        g, hats_on, oct_up = _sec(t0)
        nn = int(SR * eighth * 0.92)
        tt = np.arange(nn) / SR
        f = melody[step % len(melody)]
        square = np.tanh(2.2 * np.sin(2 * np.pi * f * tt)) * np.exp(-tt * 5)
        _add(mix, square * 0.055 * g, t0)
        if oct_up:
            hi = np.tanh(2.2 * np.sin(2 * np.pi * f * 2 * tt)) * np.exp(-tt * 5)
            _add(mix, hi * 0.028 * g, t0)
        if step % 2 == 0:
            nb = int(SR * eighth * 1.8)
            tb = np.arange(nb) / SR
            fb = basses[(step // 8) % len(basses)]
            _add(mix, np.sin(2 * np.pi * fb * tb) * np.exp(-tb * 4) * 0.075 * g, t0)
        if hats_on:
            hat = noise[:int(SR * 0.03)] * np.exp(-np.arange(int(SR * 0.03)) / SR * 120)
            _add(mix, hat * 0.02 * g, t0)
        step += 1


def make_soundtrack(path, total_s, boundaries, finale_at, bpm=120,
                    style="beat", events=None, music_sections=None):
    n = int(SR * total_s)
    mix = np.zeros(n)
    noise = np.random.default_rng(7).standard_normal(n + SR)
    if style == "chiptune":
        _chiptune(mix, noise, total_s, bpm, music_sections)
        for ev in events or []:
            _add(mix, _event_sig(ev.get("type", "pop"), noise) * float(ev.get("gain", 1.0)),
                 float(ev.get("at", 0)))
        mix = np.tanh(mix * 1.1)
        mix *= 0.87 / max(1e-6, np.max(np.abs(mix)))
        fade = int(SR * 0.25)
        mix[-fade:] *= np.linspace(1, 0, fade)
        pcm = (mix * 32767).astype("<i2")
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes(np.repeat(pcm[:, None], 2, axis=1).tobytes())
        return
    if style == "none":
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes(np.zeros((n, 2), dtype="<i2").tobytes())
        return
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
    meta = {"author": author, "base_dir": cfg_path.resolve().parent,
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
        audio_cfg = cfg.get("audio") or {}
        make_soundtrack(wav, total_s, boundaries, finale_at,
                        bpm=int(audio_cfg.get("bpm", 120)),
                        style=audio_cfg.get("style", "beat"),
                        events=audio_cfg.get("events"),
                        music_sections=audio_cfg.get("music_sections"))
        voice = audio_cfg.get("voice") or []
        if voice:  # подмешать реплики поверх музыки/эффектов
            mixed = out / "_mixed.wav"
            inputs, filters = ["-i", str(wav)], []
            for i, v in enumerate(voice):
                vp = Path(v["file"])
                if not vp.is_absolute():
                    vp = cfg_path.resolve().parent / vp
                inputs += ["-i", str(vp)]
                delay = int(float(v.get("at", 0)) * 1000)
                filters.append(f"[{i + 1}:a]adelay={delay}|{delay},"
                               f"volume={float(v.get('gain', 1.0))}[v{i}]")
            music_vol = float(audio_cfg.get("music_volume", 0.45))
            labels = "".join(f"[v{i}]" for i in range(len(voice)))
            filters.append(f"[0:a]volume={music_vol}[bg]")
            filters.append(f"[bg]{labels}amix=inputs={len(voice) + 1}:duration=first:"
                           f"normalize=0,alimiter=limit=0.95[a]")
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", *inputs,
                            "-filter_complex", ";".join(filters), "-map", "[a]",
                            str(mixed)], check=True)
            wav.unlink(missing_ok=True)
            wav = mixed
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", str(final)], check=True)
        silent.unlink(missing_ok=True)
        wav.unlink(missing_ok=True)
    print(json.dumps({"готово": str(final), "кадров": total, "секунд": total_s,
                      "размер": f"{out_w}x{out_h}", "fps": FPS}, ensure_ascii=False))


if __name__ == "__main__":
    main()
