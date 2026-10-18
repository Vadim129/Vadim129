"""Tiny text-sprite helper shared by the birthday-clip scripts."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

_CACHE: dict = {}


def trim(rgba, pad=2):
    a = rgba[:, :, 3]
    ys, xs = np.where(a > 6)
    if len(xs) == 0:
        return rgba
    x0, x1 = max(0, xs.min() - pad), min(rgba.shape[1], xs.max() + pad + 1)
    y0, y1 = max(0, ys.min() - pad), min(rgba.shape[0], ys.max() + pad + 1)
    return rgba[y0:y1, x0:x1]


def text_sprite(text, font_path, size, fill, stroke=None, stroke_w=0, tracking=0,
                shadow=0.0, glow=0.0):
    """Render a line of text to an RGBA sprite (cached)."""
    key = (text, font_path, size, fill, stroke, stroke_w, tracking, shadow, glow)
    if key in _CACHE:
        return _CACHE[key]
    font = ImageFont.truetype(font_path, int(size))
    probe = Image.new("RGBA", (8, 8))
    d = ImageDraw.Draw(probe)
    widths, hmax = [], 0
    for ch in text:
        bb = d.textbbox((0, 0), ch, font=font, stroke_width=stroke_w)
        adv = d.textlength(ch, font=font)
        widths.append(max(adv, bb[2] - bb[0]) + tracking)
        hmax = max(hmax, bb[3] - bb[1])
    tw = int(sum(widths) + size * 0.9)
    th = int(hmax + size * 0.95)
    img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = size * 0.45
    pad_top = size * 0.42
    for ch, wdt in zip(text, widths):
        bb = d.textbbox((0, 0), ch, font=font, stroke_width=stroke_w)
        d.text((x - bb[0], pad_top), ch, font=font, fill=fill,
               stroke_width=stroke_w, stroke_fill=stroke)
        x += wdt
    arr = np.array(img)
    if glow:
        a = arr[:, :, 3].astype(np.float32) / 255
        g = np.clip(cv2.GaussianBlur(a, (0, 0), glow) * 1.8, 0, 1)
        halo = np.zeros_like(arr, np.float32)
        halo[:, :, :3] = np.array(fill[:3], np.float32)
        halo[:, :, 3] = g * 255
        out = arr.astype(np.float32)
        oa = out[:, :, 3:4] / 255
        out[:, :, :3] = halo[:, :, :3] * (1 - oa) + out[:, :, :3] * oa
        out[:, :, 3:4] = np.maximum(halo[:, :, 3:4], out[:, :, 3:4])
        arr = out.astype(np.uint8)
    if shadow:
        s = cv2.GaussianBlur(arr[:, :, 3].astype(np.float32), (0, 0), shadow) * 0.5
        sh = np.zeros_like(arr)
        sh[:, :, 3] = s.astype(np.uint8)
        sh = np.roll(sh, int(shadow * 1.4), axis=0)
        sh = np.roll(sh, int(shadow * 0.9), axis=1)
        out = arr.astype(np.float32)
        oa = out[:, :, 3:4] / 255
        out[:, :, :3] = sh[:, :, :3] * (1 - oa) + out[:, :, :3] * oa
        out[:, :, 3:4] = np.maximum(sh[:, :, 3:4], out[:, :, 3:4])
        arr = out.astype(np.uint8)
    arr = cv2.cvtColor(trim(arr), cv2.COLOR_RGBA2BGRA)
    _CACHE[key] = arr
    return arr
