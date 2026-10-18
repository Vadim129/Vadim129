"""Build the assets for the birthday clip from the pictures in the Drive folder.

Outputs (all in ``congr/assets``):
  girl.png        cut-out of the birthday girl with the cake (transparent bg)
  frog.png        cut-out of the frog holding the bouquet (transparent bg)
  man.png         cut-out of the man with flowers (transparent bg)
  frog_nobg.png   frog cut-out from the greeting card
  icons.png       the five good-luck badges from the card, on transparency
  text_*.png      lettering sprites rendered with the real script fonts
  paper.png       procedural watercolour paper
"""
from __future__ import annotations

import json
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
SRC = os.path.join(HERE, "..", "google_drive")
W, H = 1080, 1920


# ----------------------------------------------------------------- helpers
def feather(alpha, s=1.2):
    return cv2.GaussianBlur(alpha.astype(np.float32), (0, 0), s)


def trim(rgba, pad=4):
    a = rgba[:, :, 3]
    ys, xs = np.where(a > 8)
    if len(xs) == 0:
        return rgba
    x0, x1 = max(0, xs.min() - pad), min(rgba.shape[1], xs.max() + pad + 1)
    y0, y1 = max(0, ys.min() - pad), min(rgba.shape[0], ys.max() + pad + 1)
    return rgba[y0:y1, x0:x1]


def cut_light_bg(img, sat_max=52, val_min=176, close=9, erode=2):
    """Cut a subject photographed on a bright, low-saturation background."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    bg = ((hsv[:, :, 1] < sat_max) & (hsv[:, :, 2] > val_min)).astype(np.uint8)
    bg = cv2.morphologyEx(bg, cv2.MORPH_CLOSE, np.ones((close, close), np.uint8))
    fg = (1 - bg).astype(np.uint8)
    # keep the biggest blob (the subject), lose speckle
    n, lab, st, _ = cv2.connectedComponentsWithStats(fg, 8)
    if n > 1:
        keep = np.zeros_like(fg)
        for i in range(1, n):
            if st[i, cv2.CC_STAT_AREA] > 4000:
                keep[lab == i] = 1
        fg = keep
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    fg = cv2.erode(fg, np.ones((3, 3), np.uint8), iterations=erode)
    a = feather(fg)
    core = cv2.erode(fg, np.ones((3, 3), np.uint8), iterations=1)
    filled = cv2.inpaint(img, (1 - core) * 255, 3, cv2.INPAINT_TELEA)
    return np.dstack([filled, (a * 255).astype(np.uint8)])


def text_sprite(text, font, size, fill, stroke=None, stroke_w=0, tracking=0,
                shadow=0, glow=0, dpi_scale=1.0):
    """Render a line of text to an RGBA sprite (with optional glow/shadow)."""
    font = ImageFont.truetype(font, int(size * dpi_scale))
    tmp = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(tmp)
    widths, hgt = [], 0
    for ch in text:
        bb = d.textbbox((0, 0), ch, font=font, stroke_width=stroke_w)
        widths.append(bb[2] - bb[0] + tracking)
        hgt = max(hgt, bb[3] - bb[1])
    tw = int(sum(widths) + size * 0.8)
    th = int(hgt + size * 0.9)
    img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = size * 0.4
    base = d.textbbox((0, 0), "Ай", font=font)[1]
    for ch, wdt in zip(text, widths):
        bb = d.textbbox((0, 0), ch, font=font, stroke_width=stroke_w)
        d.text((x - bb[0], size * 0.42), ch, font=font, fill=fill,
               stroke_width=stroke_w, stroke_fill=stroke)
        x += wdt
    arr = np.array(img)
    if shadow or glow:
        a = arr[:, :, 3].astype(np.float32) / 255
        if glow:
            g = cv2.GaussianBlur(a, (0, 0), glow)
            g = np.clip(g * 1.4, 0, 1)
            halo = np.zeros_like(arr, np.float32)
            halo[:, :, :3] = np.array(fill[:3], np.float32) * 0.9
            halo[:, :, 3] = g * 255
            out = arr.astype(np.float32)
            oa = out[:, :, 3:4] / 255
            out[:, :, :3] = halo[:, :, :3] * (1 - oa) + out[:, :, :3] * oa
            out[:, :, 3:4] = np.maximum(halo[:, :, 3:4], out[:, :, 3:4])
            arr = out.astype(np.uint8)
        if shadow:
            s = cv2.GaussianBlur(arr[:, :, 3].astype(np.float32), (0, 0), shadow)
            sh = np.zeros_like(arr)
            sh[:, :, 3] = (s * 0.55).astype(np.uint8)
            sh = np.roll(sh, int(shadow * 1.2), axis=0)
            sh = np.roll(sh, int(shadow * 0.8), axis=1)
            out = arr.astype(np.float32)
            oa = out[:, :, 3:4] / 255
            out[:, :, :3] = sh[:, :, :3] * (1 - oa) + out[:, :, :3] * oa
            out[:, :, 3:4] = np.maximum(sh[:, :, 3:4], out[:, :, 3:4])
            arr = out.astype(np.uint8)
    return trim(arr)


# ----------------------------------------------------------------- lettering
SCRIPT = os.path.join(ASSETS, "fonts", "MarckScript-Regular.ttf")
SERIF = os.path.join(ASSETS, "fonts", "PlayfairDisplay[wght].ttf")
INK = (86, 52, 34, 255)          # warm brown ink
GOLD = (255, 226, 168, 255)
WINE = (150, 44, 74, 255)

TEXTS = {
    "julia": dict(text="Юля!", font=SCRIPT, size=150, fill=WINE, stroke=GOLD, stroke_w=3),
    "happy": dict(text="с днём рождения!", font=SCRIPT, size=104, fill=INK),
    "line1": dict(text="Улыбок, радости, тепла,", font=SCRIPT, size=78, fill=INK),
    "line2": dict(text="любви, цветов и вдохновения,", font=SCRIPT, size=78, fill=INK),
    "line3": dict(text="чтоб ты счастливою была!", font=SCRIPT, size=78, fill=INK),
    "fiftyone": dict(text="51", font=SERIF, size=132, fill=WINE),
    "wish1": dict(text="Крепкого здоровья!", font=SCRIPT, size=62, fill=INK),
    "wish2": dict(text="Счастья и радости!", font=SCRIPT, size=62, fill=INK),
    "wish3": dict(text="Вдохновения и новых идей!", font=SCRIPT, size=62, fill=INK),
    "wish4": dict(text="Успехов во всех начинаниях!", font=SCRIPT, size=62, fill=INK),
    "wish5": dict(text="Пусть мечты сбываются!", font=SCRIPT, size=62, fill=INK),
    "final": dict(text="С днём рождения, Юля!", font=SCRIPT, size=112, fill=WINE,
                  stroke=GOLD, stroke_w=2),
    "date": dict(text="18 октября", font=SERIF, size=64, fill=(120, 96, 74, 255)),
}


def build_texts():
    meta = {}
    for name, kw in TEXTS.items():
        kw = dict(kw)
        kw["fill"] = tuple(kw["fill"])
        if kw.get("stroke"):
            kw["stroke"] = tuple(kw["stroke"])
        spirte = text_sprite(**kw)
        cv2.imwrite(os.path.join(ASSETS, f"text_{name}.png"), spirte)
        meta[name] = dict(w=spirte.shape[1], h=spirte.shape[0])
    return meta


# ----------------------------------------------------------------- paper
def build_paper():
    rng = np.random.default_rng(4)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # soft cream base with a warm vertical gradient
    t = yy / H
    top = np.array([246, 241, 238], np.float32)     # BGR
    bot = np.array([226, 226, 240], np.float32)
    img = top[None, None, :] * (1 - t)[..., None] + bot[None, None, :] * t[..., None]
    # watercolour blooms
    for _ in range(26):
        cx, cy = rng.uniform(0, W), rng.uniform(0, H)
        r = rng.uniform(90, 420)
        col = np.array([rng.uniform(200, 235), rng.uniform(205, 240), rng.uniform(225, 250)], np.float32)
        d2 = ((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r)
        img = img * (1 - 0.10 * np.exp(-d2))[..., None] + col * (0.10 * np.exp(-d2))[..., None]
    # paper grain
    grain = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 1.1)
    img += grain[..., None] * 3.2
    fib = cv2.GaussianBlur(rng.normal(0, 1, (H // 4, W // 4)).astype(np.float32), (0, 0), 0.6)
    fib = cv2.resize(fib, (W, H), interpolation=cv2.INTER_CUBIC)
    img += fib[..., None] * 2.0
    return np.clip(img, 0, 255).astype(np.uint8)


# ----------------------------------------------------------------- main
def main():
    os.makedirs(ASSETS, exist_ok=True)

    # ---- birthday girl on white studio bg
    g = cv2.imread(os.path.join(SRC, "IMG_20261018_120152_021.jpg"))
    girl = cut_light_bg(g, sat_max=46, val_min=182, close=11, erode=2)
    girl = cv2.resize(trim(girl), None, fx=0.55, fy=0.55, interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(ASSETS, "girl.png"), girl)
    print("girl", girl.shape)

    # ---- man with the bouquet
    m = cv2.imread(os.path.join(SRC, "IMG_20261018_120145_847.jpg"))
    # his photo has a warm interior behind him: cut by hand-shaped polygon
    man = cut_light_bg(m, sat_max=40, val_min=150, close=15, erode=3)
    man = cv2.resize(trim(man), None, fx=0.42, fy=0.42, interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(ASSETS, "man.png"), man)
    print("man", man.shape)

    # ---- frog from the greeting card (paper background -> colour keyed)
    c = cv2.imread(os.path.join(SRC, "IMG_20261018_120148_565.jpg"))
    roi = c[420:1180, 0:700].copy()
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    hh, ss, vv = hsv[:, :, 0].astype(np.int16), hsv[:, :, 1].astype(np.int16), hsv[:, :, 2]
    green = ((hh > 28) & (hh < 90) & (ss > 55) & (vv > 40))
    hat = ((hh > 10) & (hh < 32) & (ss > 55) & (vv > 90))
    shirt = ((hh > 85) & (hh < 130) & (ss > 40) & (vv > 40))
    straw = ((hh > 14) & (hh < 34) & (ss > 45) & (vv > 110))
    fg = (green | hat | shirt | straw | (vv < 120)).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(fg, 8)
    keep = np.zeros_like(fg)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] > 3000:
            keep[lab == i] = 1
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    a = feather(keep, 1.2)
    core = cv2.erode(keep, np.ones((3, 3), np.uint8), iterations=1)
    filled = cv2.inpaint(roi, (1 - core) * 255, 3, cv2.INPAINT_TELEA)
    frog = trim(np.dstack([filled, (a * 255).astype(np.uint8)]))
    cv2.imwrite(os.path.join(ASSETS, "frog.png"), frog)
    cv2.imwrite(os.path.join(ASSETS, "frog_raw.png"), np.dstack([roi, (a * 255).astype(np.uint8)]))
    print("frog", frog.shape)

    # ---- five badges from the bottom of the card
    # five painted badges, cropped tight and keyed off the cream paper
    ICONS = {"health": (100, 1036, 216, 1130), "joy": (242, 1032, 360, 1130),
             "ideas": (392, 1034, 510, 1130), "success": (538, 1032, 660, 1130),
             "dream": (680, 1028, 800, 1126)}
    for name, (x0, y0, x1, y1) in ICONS.items():
        crop = c[y0:y1, x0:x1]
        hsv2 = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        s2, v2 = hsv2[:, :, 1].astype(np.int16), hsv2[:, :, 2].astype(np.int16)
        keep = ((s2 > 55) | (v2 < 150)).astype(np.uint8)
        keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        n2, lab2, st2, _ = cv2.connectedComponentsWithStats(keep, 8)
        big = np.zeros_like(keep)
        for i in range(1, n2):
            if st2[i, 4] > 800:
                big[lab2 == i] = 1
        al = cv2.GaussianBlur(big.astype(np.float32), (0, 0), 1.0)
        out = np.dstack([crop, (al * 255).astype(np.uint8)])
        cv2.imwrite(os.path.join(ASSETS, f"icon_{name}.png"), out)
    # one wide strip as a fallback
    cv2.imwrite(os.path.join(ASSETS, "icons_strip.png"), c[1000:1190, 120:853])

    # ---- raw crops used inside the photo cards (no matting: the studio
    # backgrounds read as clean photo cards on cream paper)
    g_raw = cv2.resize(g, (900, 900), interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(ASSETS, "girl_raw.png"), g_raw)
    frog_raw = c[452:1010, 0:392]
    cv2.imwrite(os.path.join(ASSETS, "frog_raw.png"), frog_raw)
    man_raw = m[650:2560, 90:1390]
    man_raw = cv2.resize(man_raw, (int(man_raw.shape[1] * 0.62), int(man_raw.shape[0] * 0.62)),
                         interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(ASSETS, "man_raw.png"), man_raw)
    print("raw", g_raw.shape, frog_raw.shape, man_raw.shape)

    # ---- paper + lettering
    cv2.imwrite(os.path.join(ASSETS, "paper.png"), build_paper())
    meta = build_texts()
    json.dump(meta, open(os.path.join(ASSETS, "texts.json"), "w"), indent=1)
    print("texts", {k: (v["w"], v["h"]) for k, v in meta.items()})


if __name__ == "__main__":
    main()
