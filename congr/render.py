"""Render the birthday clip: 1080x1920, 30 fps, one continuous take."""
from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from typekit import text_sprite  # noqa: E402

ASSETS = os.path.join(HERE, "assets")
OUT = os.path.join(HERE, "media")
W, H = 1080, 1920
FPS = 30
DUR = 37.9

SCRIPT = os.path.join(ASSETS, "fonts", "MarckScript-Regular.ttf")
SERIF = os.path.join(ASSETS, "fonts", "PlayfairDisplay[wght].ttf")

INK = (92, 58, 40, 255)
WINE = (142, 42, 78, 255)
GOLD = (255, 229, 173, 255)
DEEP = (74, 46, 34, 255)
DATE_COL = (134, 106, 84, 255)

PETAL_COLS = [(206, 190, 246), (214, 198, 250), (188, 168, 238), (200, 206, 250),
              (222, 206, 250), (186, 176, 236)]


# ------------------------------------------------------------------ helpers
def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def overshoot(x):
    x = min(1.0, max(0.0, x))
    return 1 + 2.4 * (x - 1) ** 3 + 1.4 * (x - 1) ** 2


def rounded_mask(w, h, r):
    m = np.zeros((h, w), np.uint8)
    cv2.rectangle(m, (r, 0), (w - r - 1, h - 1), 255, -1)
    cv2.rectangle(m, (0, r), (w - 1, h - r - 1), 255, -1)
    for cx, cy in ((r, r), (w - r - 1, r), (r, h - r - 1), (w - r - 1, h - r - 1)):
        cv2.circle(m, (cx, cy), r, 255, -1, cv2.LINE_AA)
    return m


def circle_mask(d):
    m = np.zeros((d, d), np.uint8)
    cv2.circle(m, (d // 2, d // 2), d // 2 - 1, 255, -1, cv2.LINE_AA)
    return m


def paste(canvas, rgba, cx, cy, scale=1.0, rot=0.0, alpha=1.0,
          shadow=0.0, shadow_dy=0.0, shadow_alpha=0.30):
    if alpha <= 0.004 or scale <= 0.01:
        return
    img = rgba
    if img.shape[2] == 3:
        img = np.dstack([img, np.full(img.shape[:2], 255, np.uint8)])
    if abs(scale - 1.0) > 1e-3:
        nw = max(1, int(round(img.shape[1] * scale)))
        nh = max(1, int(round(img.shape[0] * scale)))
        img = cv2.resize(img, (nw, nh),
                         interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    if abs(rot) > 0.05:
        h, w = img.shape[:2]
        c = (w / 2, h / 2)
        M = cv2.getRotationMatrix2D(c, rot, 1.0)
        cos, sin = abs(M[0, 0]), abs(M[0, 1])
        nw, nh = int(h * sin + w * cos) + 2, int(h * cos + w * sin) + 2
        M[0, 2] += nw / 2 - c[0]
        M[1, 2] += nh / 2 - c[1]
        img = cv2.warpAffine(img, M, (nw, nh), flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    h, w = img.shape[:2]
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    x1, y1 = x0 + w, y0 + h
    cx0, cy0 = max(0, x0), max(0, y0)
    cx1, cy1 = min(W, x1), min(H, y1)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    sx0, sy0 = cx0 - x0, cy0 - y0
    patch = img[sy0:sy0 + (cy1 - cy0), sx0:sx0 + (cx1 - cx0)].astype(np.float32)
    a = (patch[:, :, 3:4] / 255.0) * alpha
    if shadow > 0:
        sh = cv2.GaussianBlur(patch[:, :, 3], (0, 0), shadow) * shadow_alpha * alpha
        dy = int(round(shadow_dy))
        ys0, ys1 = cy0 + dy, cy1 + dy
        if ys0 >= 0 and ys1 <= H:
            roi = canvas[ys0:ys1, cx0:cx1].astype(np.float32)
            m = sh[..., None] / 255.0
            canvas[ys0:ys1, cx0:cx1] = (
                roi * (1 - m) + np.array([116, 112, 128], np.float32) * m).astype(np.uint8)
    roi = canvas[cy0:cy1, cx0:cx1].astype(np.float32)
    canvas[cy0:cy1, cx0:cx1] = (patch[:, :, :3] * a + roi * (1 - a)).astype(np.uint8)


def fit(spr, max_w):
    if spr.shape[1] <= max_w:
        return spr, 1.0
    k = max_w / spr.shape[1]
    return cv2.resize(spr, (int(spr.shape[1] * k), int(spr.shape[0] * k)),
                      interpolation=cv2.INTER_AREA), k


class Kit:
    def __init__(self):
        self.paper = cv2.imread(os.path.join(ASSETS, "paper.png"))
        self.paper_big = cv2.resize(self.paper, (int(W * 1.09), int(H * 1.09)),
                                    interpolation=cv2.INTER_CUBIC)
        self.raw = {}
        for key in ("girl", "frog", "man"):
            self.raw[key] = cv2.imread(os.path.join(ASSETS, f"{key}_raw.png"), cv2.IMREAD_COLOR)
        self.cards = {}
        self.petals = self._make_petals()
        self.spark = self._make_spark()
        self.confetti = self._make_confetti()
        self.vign = self._vignette()
        self.washes = self._make_washes()
        self.leak = self._make_leak()
        self.grain = self._make_grain()

    # -------------------------------------------------------------- sprites
    @staticmethod
    def _make_petals(n=30):
        rng = np.random.default_rng(11)
        out = []
        for i in range(n):
            size = int(rng.integers(20, 40))
            s = size * 3
            spr = np.zeros((s, s, 4), np.uint8)
            col = PETAL_COLS[i % len(PETAL_COLS)]
            c = s // 2
            ang = int(rng.integers(-25, 25))
            cv2.ellipse(spr, (c, c), (int(size * 0.62), int(size * 0.34)),
                        ang, 0, 360, (float(col[0]), float(col[1]), float(col[2]), 255),
                        -1, cv2.LINE_AA)
            core = np.zeros((s, s), np.uint8)
            cv2.ellipse(core, (c, c), (int(size * 0.44), int(size * 0.20)),
                        ang, 0, 360, 90, -1, cv2.LINE_AA)
            core = cv2.GaussianBlur(core, (0, 0), size * 0.10)
            rgb = spr[:, :, :3].astype(np.float32)
            rgb = np.clip(rgb + core[:, :, None].astype(np.float32) * 0.35, 0, 255)
            spr[:, :, :3] = rgb.astype(np.uint8)
            spr = cv2.GaussianBlur(spr, (0, 0), 1.4)
            spr = spr[c - size: c + size, c - size: c + size]
            out.append(dict(spr=spr,
                            x=float(rng.uniform(-40, W + 40)),
                            y=float(rng.uniform(-200, H)),
                            v=float(rng.uniform(14, 36)),
                            amp=float(rng.uniform(14, 44)),
                            om=float(rng.uniform(0.25, 0.8)),
                            ph=float(rng.uniform(0, 6.28)),
                            spin=float(rng.uniform(-30, 30)),
                            rot0=float(rng.uniform(0, 360)),
                            alpha=float(rng.uniform(0.25, 0.55))))
        return out

    @staticmethod
    def _make_spark(size=96):
        s = size
        spr = np.zeros((s, s, 4), np.uint8)
        c = s // 2
        glow = np.zeros((s, s), np.float32)
        for r, a in ((3, 255), (8, 120), (16, 40)):
            g = np.zeros((s, s), np.uint8)
            cv2.circle(g, (c, c), r, a, -1, cv2.LINE_AA)
            glow += g.astype(np.float32)
        glow = np.clip(cv2.GaussianBlur(glow, (0, 0), s * 0.09), 0, 255)
        spr[:, :, 3] = glow.astype(np.uint8)
        spr[:, :, :3] = (238, 246, 255)
        for ang in (0, 90):
            dx = int(math.cos(math.radians(ang)) * s * 0.46)
            dy = int(math.sin(math.radians(ang)) * s * 0.46)
            cv2.line(spr, (c - dx, c - dy), (c + dx, c + dy),
                     (238, 246, 255, 200), 2, cv2.LINE_AA)
        return cv2.GaussianBlur(spr, (0, 0), 0.8)

    @staticmethod
    def _make_confetti(n=90):
        rng = np.random.default_rng(5)
        cols = [(150, 120, 235), (120, 180, 240), (150, 200, 200), (110, 190, 235),
                (170, 160, 250), (140, 150, 210)]
        out = []
        for i in range(n):
            w_, h_ = int(rng.integers(8, 15)), int(rng.integers(13, 22))
            spr = np.zeros((h_ + 4, w_ + 4, 4), np.uint8)
            spr[2:2 + h_, 2:2 + w_] = cols[i % len(cols)] + (255,)
            out.append(dict(spr=spr, x=float(rng.uniform(0, W)),
                            y=float(rng.uniform(-H, 0)),
                            v=float(rng.uniform(180, 330)),
                            amp=float(rng.uniform(10, 40)),
                            om=float(rng.uniform(0.6, 1.6)),
                            ph=float(rng.uniform(0, 6.28)),
                            spin=float(rng.uniform(-240, 240)),
                            rot0=float(rng.uniform(0, 360))))
        return out

    @staticmethod
    def _vignette():
        u = (np.arange(W, dtype=np.float32)[None, :] - W / 2) / (W / 2)
        v = (np.arange(H, dtype=np.float32)[:, None] - H / 2) / (H / 2)
        r = np.sqrt(u * u + v * v)
        return np.clip(1.03 - 0.08 * np.clip(r - 0.55, 0, 2) ** 1.5, 0.78, 1.0).astype(np.float32)

    @staticmethod
    def _make_washes():
        out = []
        specs = [((236, 210, 246), 0.16, 0.18, 540), ((252, 226, 206), 0.82, 0.26, 620),
                 ((250, 224, 226), 0.14, 0.70, 560), ((246, 226, 236), 0.88, 0.84, 520)]
        for col, fx, fy, rad in specs:
            s = rad * 2
            ax = np.arange(s, dtype=np.float32) - rad
            g = np.exp(-(ax[None, :] ** 2 + ax[:, None] ** 2) / (2 * (rad * 0.45) ** 2))
            spr = np.zeros((s, s, 3), np.float32)
            spr[:] = np.array(col, np.float32)
            out.append((spr, g.astype(np.float32), int(fx * W), int(fy * H), rad))
        return out

    @staticmethod
    def _make_leak():
        ax = np.arange(W, dtype=np.float32)[None, :] / W
        ay = np.arange(H, dtype=np.float32)[:, None] / H
        g = np.exp(-(((ax - 0.92) ** 2) / 0.05 + ((ay - 0.05) ** 2) / 0.04))
        leak = np.zeros((H, W, 3), np.float32)
        leak[:, :, 2] = g * 30
        leak[:, :, 1] = g * 14
        return leak

    @staticmethod
    def _make_grain(n=40):
        rng = np.random.default_rng(9)
        g = rng.normal(0, 2.0, (n, H, W)).astype(np.float32)
        return np.repeat(g[:, :, :, None], 3, axis=3)

    # -------------------------------------------------------------- cards
    ANCHOR = {"girl": 0.45, "frog": 0.28, "man": 0.18}
    # tighter windows (fractions of the source) used for the medallions
    REGION = {"girl": (0.26, 0.00, 0.76, 0.72),
              "frog": (0.00, 0.00, 1.00, 1.00),
              "man": (0.02, 0.02, 0.98, 0.98)}

    def card(self, name, w, h, border=20, radius=24, gold=True):
        key = (name, w, h, border, radius, gold)
        if key in self.cards:
            return self.cards[key]
        src = self.raw[name]
        sw, sh = src.shape[1], src.shape[0]
        iw, ih = w - 2 * border, h - 2 * border
        sc = max(iw / sw, ih / sh)
        nw, nh = int(round(sw * sc)), int(round(sh * sc))
        img = cv2.resize(src, (nw, nh), interpolation=cv2.INTER_AREA)
        ox = (nw - iw) // 2
        oy = int((nh - ih) * self.ANCHOR.get(name, 0.5))
        img = img[oy:oy + ih, ox:ox + iw]
        card = np.zeros((h, w, 3), np.uint8)
        card[:, :] = (250, 247, 242)
        card[border:border + ih, border:border + iw] = img
        if gold:
            cv2.rectangle(card, (border - 6, border - 6), (w - border + 5, h - border + 5),
                          (196, 214, 238), 1, cv2.LINE_AA)
        self.cards[key] = np.dstack([card, rounded_mask(w, h, radius)])
        return self.cards[key]

    def medallion(self, name, d=470, ring=9, inner=18):
        """Circular portrait with a cream mat + hairline rule around it."""
        key = ("med", name, d, ring, inner)
        if key in self.cards:
            return self.cards[key]
        src = self.raw[name]
        if name in self.REGION:
            fx0, fy0, fx1, fy1 = self.REGION[name]
            Hh, Ww = src.shape[:2]
            src = src[int(fy0 * Hh):int(fy1 * Hh), int(fx0 * Ww):int(fx1 * Ww)]
        sw, sh = src.shape[1], src.shape[0]
        dfull = d + 2 * ring
        # photo window = inside the cream mat
        dd = d - 2 * inner
        sc = max(dd / sw, dd / sh)
        img = cv2.resize(src, (max(dd, int(sw * sc)), max(dd, int(sh * sc))),
                         interpolation=cv2.INTER_AREA)
        ox = (img.shape[1] - dd) // 2
        oy = int((img.shape[0] - dd) * self.ANCHOR.get(name, 0.5))
        img = img[oy:oy + dd, ox:ox + dd].copy()
        out = np.zeros((dfull, dfull, 4), np.uint8)
        out[:, :, :3] = (250, 247, 242)
        out[:, :, 3] = circle_mask(dfull)
        pm = circle_mask(dd).astype(np.float32) / 255
        pm = cv2.GaussianBlur(pm, (0, 0), 1.2)
        x0 = ring + inner
        roi = out[x0:x0 + dd, x0:x0 + dd, :3].astype(np.float32)
        out[x0:x0 + dd, x0:x0 + dd, :3] = (
            img.astype(np.float32) * pm[..., None] + roi * (1 - pm[..., None])).astype(np.uint8)
        bgr = np.ascontiguousarray(out[:, :, :3])
        cv2.circle(bgr, (dfull // 2, dfull // 2), dd // 2 + 3, (206, 220, 238), 1, cv2.LINE_AA)
        cv2.circle(bgr, (dfull // 2, dfull // 2), dfull // 2 - 3, (206, 220, 238), 1, cv2.LINE_AA)
        out[:, :, :3] = bgr
        self.cards[key] = out
        return out


# ------------------------------------------------------------------ scene
def background(kit, t):
    ox = 0.05 * (kit.paper_big.shape[1] - W) * (0.5 + 0.5 * math.sin(t * 0.07))
    oy = 0.05 * (kit.paper_big.shape[0] - H) * (0.5 + 0.5 * math.sin(t * 0.05 + 1.2))
    x0, y0 = int(ox), int(oy)
    frame = kit.paper_big[y0:y0 + H, x0:x0 + W].copy()
    for spr, g, cx, cy, rad in kit.washes:
        dx = int(26 * math.sin(t * 0.09 + cx * 0.01))
        dy = int(20 * math.cos(t * 0.07 + cy * 0.01))
        x0w, y0w = cx - rad + dx, cy - rad + dy
        x1w, y1w = x0w + spr.shape[1], y0w + spr.shape[0]
        cx0, cy0 = max(0, x0w), max(0, y0w)
        cx1, cy1 = min(W, x1w), min(H, y1w)
        if cx1 <= cx0 or cy1 <= cy0:
            continue
        sub = spr[cy0 - y0w:cy1 - y0w, cx0 - x0w:cx1 - x0w]
        sg = g[cy0 - y0w:cy1 - y0w, cx0 - x0w:cx1 - x0w][..., None]
        roi = frame[cy0:cy1, cx0:cx1].astype(np.float32)
        frame[cy0:cy1, cx0:cx1] = (roi * (1 - sg * 0.5) + sub * sg * 0.5).astype(np.uint8)
    for p in kit.petals:
        y = (p["y"] + p["v"] * t) % (H + 240) - 120
        x = p["x"] + p["amp"] * math.sin(p["om"] * t + p["ph"])
        paste(frame, p["spr"], x, y, 1.0, p["rot0"] + p["spin"] * t, p["alpha"])
    return frame


def sparkles(frame, t, pts):
    for (x, y, ph, size) in pts:
        v = 0.5 + 0.5 * math.sin(t * 2.1 + ph)
        a = max(0.0, v - 0.35) / 0.65
        if a <= 0.02:
            continue
        paste(frame, kit.spark, x, y, size * (0.7 + 0.5 * a), 0, a * 0.8)


def confetti(frame, t, t0, n=90, dur=6.0):
    lt = t - t0
    if lt < 0 or lt > dur:
        return
    for p in kit.confetti[:n]:
        y = -60 + p["v"] * lt
        if y > H + 80:
            continue
        x = (p["x"] + p["amp"] * math.sin(p["om"] * lt + p["ph"])) % W
        paste(frame, p["spr"], x, y, 1.0, p["rot0"] + p["spin"] * lt, 0.95)


def text(frame, s, cx, cy, alpha=1.0, scale=1.0, rot=0.0, shadow=6.0):
    if alpha <= 0.01:
        return
    paste(frame, s, cx, cy, scale, rot, alpha, shadow=shadow, shadow_dy=7, shadow_alpha=0.16)


def flourish(frame, cx, cy, wdt, alpha=1.0, col=(158, 116, 76)):
    if alpha <= 0.01:
        return
    ov = frame.astype(np.float32)
    colv = tuple(float(v) for v in col)
    pts = []
    for i in range(61):
        x = -wdt / 2 + wdt * i / 60
        y = 5 * math.sin(math.pi * (i / 60)) ** 2
        pts.append((cx + x, cy + y))
    for i in range(len(pts) - 1):
        cv2.line(ov, (int(pts[i][0]), int(pts[i][1])),
                 (int(pts[i + 1][0]), int(pts[i + 1][1])), colv, 2, cv2.LINE_AA)
    hx, hy = cx, cy + 2
    cv2.circle(ov, (int(hx - 7), int(hy - 3)), 7, colv, 2, cv2.LINE_AA)
    cv2.circle(ov, (int(hx + 7), int(hy - 3)), 7, colv, 2, cv2.LINE_AA)
    cv2.line(ov, (int(hx - 13), int(hy - 2)), (int(hx), int(hy + 11)), colv, 2, cv2.LINE_AA)
    cv2.line(ov, (int(hx + 13), int(hy - 2)), (int(hx), int(hy + 11)), colv, 2, cv2.LINE_AA)
    frame[:] = (frame.astype(np.float32) * (1 - alpha) + ov * alpha).astype(np.uint8)


# ------------------------------------------------------------------ scenes
def scene_title(kit, t):
    """0 - 4.2 s: name + greeting."""
    f = background(kit, t)
    a1 = smooth((t - 0.15) / 0.8)
    a2 = smooth((t - 0.95) / 0.85)
    a3 = smooth((t - 1.75) / 0.8)
    rise1 = 70 * (1 - ease_out((t - 0.15) / 1.0))
    rise2 = 56 * (1 - ease_out((t - 0.95) / 1.0))
    g = 1.0 + 0.015 * smooth((t - 2.4) / 1.7)
    s1 = text_sprite("Юля!", SCRIPT, 300, WINE, GOLD, 3)
    s2 = text_sprite("с днём рождения!", SCRIPT, 124, INK)
    s3 = text_sprite("18 октября", SERIF, 60, DATE_COL)
    text(f, s1, W / 2, 790 + rise1, a1, g)
    text(f, s2, W / 2, 985 + rise2, a2, g)
    if a3 > 0:
        y = 1090 + 30 * (1 - ease_out((t - 1.75) / 0.9))
        flourish(f, W / 2, y - 20, 430, a3 * 0.85)
        text(f, s3, W / 2, y + 50, a3 * 0.95)
    sparkles(f, t, [(200, 620, 0.4, 0.9), (890, 690, 2.1, 1.1), (300, 1030, 3.2, 0.7),
                    (810, 1000, 1.4, 0.8), (540, 545, 4.4, 1.0), (150, 1180, 5.2, 0.8)])
    return f


def scene_girl(kit, t):
    """4.2 - 10 s: the birthday girl."""
    f = background(kit, t)
    lt = t - 4.2
    a = smooth(lt / 0.9)
    push = 1.0 + 0.05 * smooth(lt / 5.4)
    cy = 950 + 7 * math.sin(lt * 0.9)
    card = kit.card("girl", 800, 980)
    paste(f, card, W / 2, cy, (0.95 + 0.05 * ease_out(lt / 0.9)) * push,
          -2.0 * (1 - ease_out(lt / 1.2)), a, shadow=26, shadow_dy=18)
    pop = overshoot((lt - 0.5) / 0.55)
    if pop > 0.02:
        cx, cy2, r = 872, 505, 104
        ov = f.astype(np.float32)
        cv2.circle(ov, (cx, cy2), int(r * pop), (253, 250, 245), -1, cv2.LINE_AA)
        cv2.circle(ov, (cx, cy2), int(r * pop), (186, 206, 234), 3, cv2.LINE_AA)
        cv2.circle(ov, (cx, cy2), int((r - 13) * pop), (206, 220, 238), 1, cv2.LINE_AA)
        f[:] = np.clip(ov, 0, 255).astype(np.uint8)
        s51 = text_sprite("51", SERIF, 96, WINE)
        text(f, s51, cx, cy2 + 2, smooth((lt - 0.68) / 0.3), pop)
    s1 = text_sprite("нашей имениннице", SCRIPT, 84, INK)
    s1, _ = fit(s1, 900)
    text(f, s1, W / 2, 1550, smooth((lt - 0.9) / 0.8))
    s2 = text_sprite("18 октября", SERIF, 50, DATE_COL)
    text(f, s2, W / 2, 1636, smooth((lt - 1.5) / 0.8) * 0.95)
    sparkles(f, t, [(120, 470, 0.9, 0.9), (940, 1330, 2.6, 0.8), (170, 1420, 4.1, 1.0),
                    (900, 1700, 1.8, 0.7)])
    return f


def scene_poem(kit, t):
    """10 - 16 s: the verse."""
    f = background(kit, t)
    lt = t - 10.0
    hdr = text_sprite("Юля,", SCRIPT, 120, WINE, GOLD, 2)
    text(f, hdr, W / 2, 330, smooth((lt - 0.05) / 0.7))
    rows = [("Улыбок, радости, тепла,", 10.6),
            ("любви, цветов и вдохновения,", 11.3),
            ("чтоб ты счастливою была!", 12.0)]
    for i, (line, t0) in enumerate(rows):
        aa = smooth((t - t0) / 0.7)
        if aa <= 0:
            continue
        spr = text_sprite(line, SCRIPT, 82, INK)
        spr, _ = fit(spr, 900)
        y = 505 + i * 118 + 34 * (1 - ease_out((t - t0) / 0.75))
        text(f, spr, W / 2, y, aa)
    med = kit.medallion("girl", 460, ring=9)
    am = smooth((lt - 2.4) / 1.0)
    paste(f, med, W / 2, 1350, 0.94 + 0.06 * ease_out((lt - 2.4) / 1.0), 0, am,
          shadow=24, shadow_dy=16)
    sparkles(f, t, [(160, 520, 1.2, 0.9), (905, 470, 3.4, 1.0), (540, 215, 0.2, 0.8),
                    (230, 1140, 5.1, 0.8), (860, 1180, 2.2, 0.9)])
    return f


def scene_flowers(kit, t):
    """16 - 26 s: frog + man with bouquets."""
    f = background(kit, t)
    lt = t - 16.0
    hdr = text_sprite("цветы для тебя!", SCRIPT, 104, WINE, GOLD, 2)
    hdr, _ = fit(hdr, 940)
    text(f, hdr, W / 2, 330, smooth((lt - 0.05) / 0.75))
    a1 = smooth(lt / 0.8)
    slide1 = 130 * (1 - ease_out(lt / 1.0))
    card1 = kit.card("frog", 540, 640, border=18, radius=20)
    paste(f, card1, 330 - slide1, 1000 + 10 * math.sin(lt * 0.8), 1.0,
          3.2 - 3.2 * ease_out(lt / 1.2), a1, shadow=24, shadow_dy=16)
    a2 = smooth((lt - 4.5) / 0.9)
    slide2 = 150 * (1 - ease_out((lt - 4.5) / 1.1))
    card2 = kit.card("man", 500, 660, border=18, radius=20)
    paste(f, card2, 760 + slide2, 1120 + 9 * math.sin(lt * 0.7 + 1), 1.0,
          -3.0 + 3.0 * ease_out((lt - 4.5) / 1.3), a2, shadow=24, shadow_dy=16)
    cap = text_sprite("с любовью и теплом", SCRIPT, 70, INK)
    text(f, cap, W / 2, 1585, smooth((lt - 5.3) / 0.8) * 0.95)
    sparkles(f, t, [(140, 700, 0.6, 1.0), (930, 900, 2.9, 0.8), (540, 1500, 4.2, 0.9)])
    return f


def scene_wishes(kit, t):
    """26 - 31 s: the five badges."""
    f = background(kit, t)
    lt = t - 26.0
    hdr = text_sprite("пусть всё сбудется", SCRIPT, 100, WINE, GOLD, 2)
    hdr, _ = fit(hdr, 940)
    text(f, hdr, W / 2, 340, smooth(lt / 0.75))
    items = [("health", "Крепкого здоровья!"),
             ("joy", "Счастья и радости!"),
             ("ideas", "Вдохновения и новых идей!"),
             ("success", "Успехов во всех начинаниях!"),
             ("dream", "Пусть мечты сбываются!")]
    for i, (icon, label) in enumerate(items):
        t0 = 26.5 + i * 0.55
        a = smooth((t - t0) / 0.55)
        if a <= 0:
            continue
        y = 640 + i * 200 + 36 * (1 - ease_out((t - t0) / 0.65))
        spr = cv2.imread(os.path.join(ASSETS, f"icon_{icon}.png"), cv2.IMREAD_UNCHANGED)
        if spr is None:
            continue
        spr = cv2.resize(spr, (150, 150), interpolation=cv2.INTER_AREA)
        paste(f, spr, 155, y, 1.0, 0, a, shadow=8, shadow_dy=4)
        s = text_sprite(label, SCRIPT, 66, DEEP)
        s, _ = fit(s, 760)
        text(f, s, 252 + s.shape[1] / 2, y + 4, a, 1.0)
    sparkles(f, t, [(120, 520, 1.1, 0.8), (940, 560, 3.7, 0.9), (540, 1700, 0.4, 1.0)])
    return f


def scene_final(kit, t):
    """31 - 38 s: sign-off."""
    f = background(kit, t)
    lt = t - 31.0
    a = smooth(lt / 0.8)
    s1 = text_sprite("с днём рождения,", SCRIPT, 116, INK)
    s2 = text_sprite("Юля!", SCRIPT, 240, WINE, GOLD, 3)
    text(f, s1, W / 2, 470 + 30 * (1 - ease_out(lt / 0.9)), a)
    text(f, s2, W / 2, 675 + 34 * (1 - ease_out((lt - 0.2) / 1.0)),
         smooth((lt - 0.2) / 0.75))
    flourish(f, W / 2, 815, 380, smooth((lt - 0.7) / 0.7) * 0.85)
    trio = [("girl", 31.5, 232, 300, 380, -5.0),
            ("frog", 31.8, 540, 300, 340, 0.0),
            ("man", 32.1, 848, 300, 380, 5.0)]
    for name, t0, cx, wdt, hgt, rot in trio:
        aa = smooth((t - t0) / 0.65)
        if aa <= 0:
            continue
        c = kit.card(name, wdt, hgt, border=11, radius=14)
        dy = 46 * (1 - ease_out((t - t0) / 0.75))
        paste(f, c, cx, 1115 + dy, 1.0, rot * (1 - ease_out((t - t0) / 1.05)), aa,
              shadow=20, shadow_dy=13)
    s3 = text_sprite("18 октября", SERIF, 56, DATE_COL)
    text(f, s3, W / 2, 1575, smooth((lt - 1.9) / 0.9) * 0.95)
    s4 = text_sprite("от всех, кто тебя любит", SCRIPT, 56, (150, 118, 92, 255))
    text(f, s4, W / 2, 1648, smooth((lt - 3.4) / 1.0) * 0.9)
    confetti(f, t, 32.3, n=90, dur=5.7)
    sparkles(f, t, [(180, 590, 0.7, 1.0), (900, 600, 2.4, 1.0), (540, 860, 4.6, 0.8),
                    (140, 1450, 1.9, 0.8), (940, 1470, 3.1, 0.9)])
    return f


SCENES = [
    (0.0, scene_title), (4.2, scene_girl), (10.0, scene_poem),
    (16.0, scene_flowers), (26.0, scene_wishes), (31.0, scene_final),
]

kit = None


def render(t):
    idx = 0
    for i, (t0, _) in enumerate(SCENES):
        if t >= t0:
            idx = i
    t0, fn = SCENES[idx]
    frame = fn(kit, t)
    if idx > 0 and t - t0 < 0.55:
        prev_fn = SCENES[idx - 1][1]
        w = smooth((t - t0) / 0.55)
        old = prev_fn(kit, t)
        frame = (old.astype(np.float32) * (1 - w) + frame.astype(np.float32) * w)
        wash = 0.3 * math.sin(math.pi * w)
        frame = frame * (1 - wash) + kit.paper[:H, :W].astype(np.float32) * wash
        frame = frame.astype(np.uint8)
    fr = frame.astype(np.float32) * kit.vign[..., None]
    fr = fr + kit.leak * (0.55 + 0.45 * math.sin(t * 0.35))
    fr = fr + kit.grain[int(t * FPS * 3) % kit.grain.shape[0]]
    return np.clip(fr, 0, 255).astype(np.uint8)


def ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", type=str, default="")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=DUR)
    ap.add_argument("--out", type=str, default=os.path.join(OUT, "silent.mp4"))
    ap.add_argument("--crf", type=int, default=18)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    global kit
    kit = Kit()

    if args.preview:
        for ts in args.preview.split(","):
            t = float(ts)
            img = render(t)
            p = os.path.join(OUT, f"still_{t:06.2f}.png")
            cv2.imwrite(p, img)
            print("wrote", p)
        return

    frames = int(round((args.end - args.start) * FPS))
    cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-an", "-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(frames):
        t = args.start + i / FPS
        proc.stdin.write(render(t).tobytes())
        if i % 60 == 0:
            print(f"\rframe {i}/{frames} t={t:5.1f}s", end="", flush=True)
    proc.stdin.close()
    proc.wait()
    print("\nwrote", args.out)


if __name__ == "__main__":
    main()
