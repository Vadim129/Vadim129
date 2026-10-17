"""DJ Frog — vertical club video renderer.

1080x1920, 120 s, 30 fps, synced to the 128 BPM track in ``media/track.wav``.

What moves
----------
* the frog is a mesh-warp rig: hat, head, jaw, torso and both arms each get a
  feathered weight map and a pivot; angles/translations are driven by the beat
  phase so the body bounces, the head bangs, the hat lags and the arms pump
* the jaw scales on 8th notes -> it looks like the frog is singing along
* procedural eyeballs (sclera + iris sprites) look around, squint on the drop
  and blink
* club stage: kicker lights, laser fans, strobes, confetti, speaker stacks that
  pulse on every kick, a DJ desk that hides the cropped legs
* camera punch-in on each kick, shake on section changes

Usage
-----
    python3 frog/render.py --preview 3,20,62,100
    python3 frog/render.py                       # full 120 s
    python3 frog/render.py --start 60 --end 90   # chunk
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT = os.path.join(HERE, "media")

W, H = 1080, 1920
FPS = 30
DURATION = 120.0
BPM = 128.0
BEAT = 60.0 / BPM
BAR = BEAT * 4
BARS = 64
SRC = 640.0

RIG_PARTS = ["hat", "head", "torso", "larm", "rarm", "jaw"]
PIVOTS = {
    "hat": (330.0, 150.0),
    "head": (330.0, 300.0),
    "torso": (330.0, 520.0),
    "larm": (196.0, 470.0),
    "rarm": (466.0, 470.0),
    "jaw": (330.0, 285.0),
}

# sections, in bars
SEC = dict(intro=(0, 8), build=(8, 12), groove=(12, 24), brk=(24, 32),
           drop=(32, 56), outro=(56, 64))


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def pos(x, power=1.0):
    """positive-safe power (python returns complex for negative**fraction)"""
    return max(0.0, float(x)) ** power


def beat_phase(t):
    return (t / BEAT) % 1.0


def beat_index(t):
    return int(math.floor(t / BEAT))


def bar_of(t):
    return int(t // BAR)


def section(t):
    b = bar_of(t)
    for k, (a, z) in SEC.items():
        if a <= b < z:
            return k
    return "outro"


def intensity(t):
    """0..1 overall energy of the current section (drives amplitude)."""
    b = bar_of(t)
    s = section(t)
    if s == "intro":
        return 0.35 + 0.35 * min(1.0, max(0.0, (b - 1) / 6.0))
    if s == "build":
        return 0.7 + 0.3 * (b - 8) / 4.0
    if s == "groove":
        return 0.9
    if s == "brk":
        return 0.45 + 0.25 * math.sin(math.pi * min(1.0, (b - 24) / 8.0))
    if s == "drop":
        return 1.0
    return max(0.15, 0.95 - (b - 56) / 8.0 * 0.8)


# ------------------------------------------------------------------ pose
def dance_pose(t):
    """Return {part: (angle_deg, (kx, ky), dx, dy)} in sprite pixels."""
    ph = beat_phase(t)
    en = intensity(t)
    bar = bar_of(t)
    s = section(t)

    # a kick "hit" envelope: 1 on the beat, decaying fast
    hit = math.exp(-ph * 5.5)
    # smooth bounce (highest on the beat)
    bounce = pos(math.sin(math.pi * ph), 1.6)

    # 2-bar sway (leans left/right across two bars)
    sway = math.sin(math.pi * t / (BAR * 2))
    # head bang, twice per bar on the drop
    bang_ph = (t / (BEAT * 2)) % 1.0
    bang = pos(math.sin(math.pi * bang_ph), 2.0)

    amp = 0.35 + 0.65 * en

    # ---------------- torso: bounce + squash/stretch + sway
    # side-step sway: the whole body slides a little on the beat
    side = 20.0 * sway * amp
    if s == "drop":
        side += 9.0 * math.sin(math.pi * ph) * (1 if bar % 2 == 0 else -1) * amp
    jump = 0.0
    if s == "drop":
        jump = 16.0 * hit * amp
    ky = 1.0 + (0.062 * bounce - 0.022) * amp
    kx = 1.0 - (0.034 * bounce - 0.011) * amp
    ty = (14.0 * bounce - 6.0) * amp - jump
    torso_a = 3.2 * sway * amp + 1.2 * math.sin(math.pi * ph) * amp

    # ---------------- head: bangs down on the beat, counter-rotates the sway
    head_a = -2.5 * sway * amp + 1.8 * math.sin(math.pi * ph + 1.1) * amp
    head_y = (7.0 * bang - 2.0) * amp
    head_x = 2.5 * sway * amp + side * 0.22
    if s == "drop":
        head_a += 6.0 * bang * math.sin(math.pi * bang_ph * 2)
        head_y += 4.0 * bounce
    if s == "brk":
        head_a += 4.0 * math.sin(math.pi * min(1.0, (bar - 24) / 8.0))
        head_y -= 4.0

    # ---------------- hat: lags the head (spring)
    lag = pos(math.sin(math.pi * (ph - 0.12)), 2.0)
    hat_a = -head_a * 0.75 + 3.0 * math.sin(math.pi * ph + 0.5) * amp - 2.0 * lag * amp
    hat_y = -2.5 * bounce * amp + 1.5 * lag
    hat_x = -1.5 * sway * amp

    # ---------------- arms: alternate pump, both up on the drop
    if s in ("drop", "build"):
        # shoulders pump up/out on every beat
        base = 15.0 if s == "drop" else 9.0
        la = -(base + 6.0 * hit * (1 if bar % 2 == 0 else 0.5)) * amp
        ra = (base + 6.0 * hit * (1 if bar % 2 == 1 else 0.5)) * amp
        la += 4.0 * math.sin(math.pi * ph + 0.4)
        ra -= 4.0 * math.sin(math.pi * ph + 0.4)
        lx, rx = -4.0, 4.0
        ly = ry = -6.0 * bounce
    else:
        la = -(7.0 + 9.0 * pos(math.sin(math.pi * ph), 1.5)) * amp
        ra = (7.0 + 9.0 * pos(math.sin(math.pi * (ph + 0.5)), 1.5)) * amp
        lx, rx = -2.0, 2.0
        ly = -4.0 * bounce * amp
        ry = -4.0 * pos(math.sin(math.pi * (ph + 0.5)), 1.6) * amp

    # ---------------- jaw: sings on 8th notes, wide open on the drop
    sing = 1.0 + 0.055 * (0.5 + 0.5 * math.sin(2 * math.pi * t / (BEAT / 2))) * amp
    if s == "drop":
        sing = 1.0 + 0.085 * (0.5 + 0.5 * math.sin(2 * math.pi * t / (BEAT / 2))) * amp
    jaw_jump = 2.0 * (sing - 1.0) * 60.0

    return {
        "torso": (torso_a, (kx, ky), side, ty),
        "head": (head_a, 1.0, head_x, head_y - ty * 0.35),
        "hat": (hat_a, 1.0, hat_x, hat_y - ty * 0.25),
        "larm": (la, 1.0, lx, ly),
        "rarm": (ra, 1.0, rx, ry),
        "jaw": (0.0, (1.0, sing), 0.0, jaw_jump),
    }


def eye_state(t):
    """(gaze_x, gaze_y, open_amount, squint) in sprite pixels."""
    ph = beat_phase(t)
    s = section(t)
    # look around in a slow pattern, snap to the crowd on the drop
    gx = 6.0 * math.sin(2 * math.pi * t / 9.0) + 2.0 * math.sin(2 * math.pi * t / 3.3)
    gy = 3.0 * math.cos(2 * math.pi * t / 7.0)
    if s == "drop":
        gx = 4.0 * math.sin(2 * math.pi * t / 4.0) + 3.0 * math.sin(math.pi * ph)
        gy = -4.0 + 2.0 * math.sin(math.pi * ph)
    if s == "brk":
        gx *= 0.4
        gy -= 3.0
    open_amt = 1.0
    # blinks
    for bt in (2.6, 7.4, 12.1, 17.8, 23.5, 29.2, 35.1, 41.6, 47.3, 53.8,
               59.2, 64.4, 70.1, 76.6, 82.3, 88.7, 95.2, 101.8, 108.4, 115.0):
        d = abs(t - bt)
        if d < 0.16:
            open_amt = min(open_amt, (d / 0.16) ** 0.7)
    squint = 0.0
    if s == "drop":
        squint = 0.22 + 0.10 * math.sin(2 * math.pi * t / 2.0)
    return gx, gy, max(0.08, open_amt), squint


# ------------------------------------------------------------------ scene
class Scene:
    def __init__(self):
        self.frog = cv2.imread(os.path.join(ASSETS, "frog.png"), cv2.IMREAD_UNCHANGED)
        self.parts = np.load(os.path.join(ASSETS, "masks.npz"))["parts"].astype(np.float32) / 255.0
        self.eyes = json.load(open(os.path.join(ASSETS, "eyes.json")))
        self.sclera = {k: cv2.imread(os.path.join(ASSETS, f"sclera{k}.png"), cv2.IMREAD_UNCHANGED)
                       for k in ("L", "R")}
        self.iris = {k: cv2.imread(os.path.join(ASSETS, f"iris{k}.png"), cv2.IMREAD_UNCHANGED)
                     for k in ("L", "R")}
        self.lidstack = {}
        for k in ("L", "R"):
            z = np.load(os.path.join(ASSETS, f"lidstack{k}.npz"))
            self.lidstack[k] = (z["tex"], z["cover"])
        self.sky = cv2.imread(os.path.join(ASSETS, "sky.png"))

        # pre-warped base frog (no eyes) for speed
        self.base = self.frog.copy()

        # low-res bokeh field for the animated background
        rng = np.random.default_rng(5)
        self.bokeh = []
        for i in range(26):
            self.bokeh.append(dict(
                x=rng.uniform(0, W), y=rng.uniform(0, H * 0.85),
                r=rng.uniform(18, 90), v=rng.uniform(4, 22),
                ph=rng.uniform(0, 6.28), hue=rng.uniform(0, 1),
            ))

        # confetti bank
        rng = np.random.default_rng(9)
        n = 220
        self.conf = dict(
            x=rng.uniform(-100, W + 100, n), y=rng.uniform(-H, 0, n),
            vy=rng.uniform(180, 420, n), vx=rng.uniform(-60, 60, n),
            rot=rng.uniform(0, 360, n), vr=rng.uniform(-220, 220, n),
            w=rng.uniform(6, 16, n), h=rng.uniform(10, 26, n),
            c=rng.integers(0, 6, n),
        )
        self.conf_cols = [(80, 160, 255), (120, 255, 180), (255, 120, 220),
                          (255, 230, 120), (140, 140, 255), (255, 255, 255)]

        # crowd silhouettes (procedural, deterministic)
        self.crowd = self._make_crowd(rng)

        # text textures
        self.textures = {}
        self._build_text()

    # ---- helpers
    def _make_crowd(self, rng):
        layer = np.zeros((H, W, 4), np.uint8)
        for side in (-1, 1):
            for i in range(46):
                cx = rng.uniform(0, W) if side < 0 else rng.uniform(0, W)
                cy = H - rng.uniform(-20, 60)
                r = rng.uniform(26, 52)
                cv2.circle(layer, (int(cx), int(cy)), int(r), (10, 8, 14, 255), -1)
        return layer

    def _build_text(self):
        from PIL import Image, ImageDraw, ImageFont

        def font(sz, bold=False, serif=False):
            base = "/usr/share/fonts/truetype/dejavu/"
            f = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
            try:
                return ImageFont.truetype(base + f, sz)
            except OSError:
                return ImageFont.load_default()

        def tex(name, text, sz, color, tracking=0, bold=True, glow=False):
            f = font(sz, bold)
            tmp = Image.new("RGBA", (W, sz * 2), (0, 0, 0, 0))
            d = ImageDraw.Draw(tmp)
            tw = sum(d.textlength(ch, font=f) + tracking for ch in text) - tracking
            x = (W - tw) / 2
            for ch in text:
                d.text((x, 10), ch, font=f, fill=color)
                x += d.textlength(ch, font=f) + tracking
            arr = np.array(tmp)
            ys, xs = np.nonzero(arr[:, :, 3])
            if len(ys) == 0:
                self.textures[name] = arr
                return
            arr = arr[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]
            if glow:
                a = arr[:, :, 3].astype(np.float32) / 255
                g = cv2.GaussianBlur(a, (0, 0), 14)
                out = np.zeros((arr.shape[0], arr.shape[1], 4), np.uint8)
                for c in range(3):
                    out[:, :, c] = (arr[:, :, c] * a + np.array(color[:3])[c] * g * 0.8).clip(0, 255)
                out[:, :, 3] = np.clip(arr[:, :, 3] + g * 255 * 0.7, 0, 255)
                arr = out
            self.textures[name] = arr

        tex("dj", "DJ FROG", 118, (255, 255, 255, 255), tracking=10, glow=True)
        tex("title", "MARSH GROOVE", 64, (220, 255, 200, 255), tracking=8)
        tex("drop", "DROP", 210, (255, 255, 255, 255), tracking=14, glow=True)
        tex("hands", "HANDS UP", 92, (190, 255, 210, 255), tracking=10, glow=True)
        tex("bpm", "128 BPM", 52, (190, 220, 255, 255), tracking=6, bold=False)

    # ---- rig warp
    def warp_frog(self, t):
        pose = dance_pose(t)
        h, w = SRC_H, SRC_W
        yy, xx = self._grid()
        gx = np.zeros((h, w), np.float32)
        gy = np.zeros((h, w), np.float32)
        for i, name in enumerate(RIG_PARTS):
            a, k, tx, ty = pose[name]
            kx, ky = k if isinstance(k, tuple) else (k, k)
            wgt = self.parts[i]
            if wgt.max() < 0.01:
                continue
            px, py = PIVOTS[name]
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            dx = xx - px
            dy = yy - py
            gx += wgt * (dx * (kx * ca - 1.0) - dy * (ky * sa) + tx)
            gy += wgt * (dx * (kx * sa) + dy * (ky * ca - 1.0) + ty)
        src = self.composite_eyes(t)
        warped = cv2.remap(src, (xx - gx).astype(np.float32), (yy - gy).astype(np.float32),
                           cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        return warped

    def _grid(self):
        if not hasattr(self, "_g"):
            yy, xx = np.mgrid[0:SRC_H, 0:SRC_W].astype(np.float32)
            self._g = (yy, xx)
        return self._g

    # ---- eyes composited in sprite space
    def composite_eyes(self, t):
        """Round eyeballs + skin lids that slide down over them."""
        img = self.base.copy()
        gx, gy, open_amt, squint = eye_state(t)
        gx += 0.8 * math.sin(t * 13.7)
        gy += 0.6 * math.sin(t * 17.3 + 1.1)
        cover = min(0.97, max(0.0, 1.0 - open_amt * (1.0 - squint * 0.5)))
        for k in ("L", "R"):
            e = self.eyes[k]
            sc = e["sclera_sprite"]
            ic = e["iris_sprite"]
            cxs, cys = e["cx"], e["cy"]
            x0 = int(round(cxs - sc / 2))
            y0 = int(round(cys - sc / 2))

            # round eyeball, iris re-aimed, kept perfectly round
            ball = cv2.resize(self.sclera[k], (sc, sc), interpolation=cv2.INTER_AREA)
            iris = cv2.resize(self.iris[k], (ic, ic), interpolation=cv2.INTER_AREA)
            ix = int(round(sc / 2 - ic / 2 + gx))
            iy = int(round(sc / 2 - ic / 2 + gy))
            self._blit_sprite(ball, iris, ix, iy)
            self._blit_sprite(img, ball, x0, y0)

            # lid = disc of the eyeball radius sliding down; only the lens where
            # it overlaps the eyeball is painted, so it never spills onto skin
            if cover > 0.02:
                R = e["eye_r"] + 1.2
                d = 2 * R * (1.0 - cover)
                tex, lv = self.lidstack[k]
                li = int(np.argmin(np.abs(lv - cover)))
                lid = self._lid_patch(sc, R, d, cover, tex[li], e["eye_r"])
                self._blit_sprite(img, lid, x0, y0)
        return img

    @staticmethod
    def _lid_patch(sc, R, d, cover, tex, Rr):
        """Mask = eyeball disc ∩ sliding lid disc; colour = skin tone shaded
        like a dome with a lit free edge and a crease shadow above it."""
        yy, xx = np.mgrid[0:sc, 0:sc].astype(np.float32)
        cx = cy = (sc - 1) / 2.0
        eye_d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        lid_d = np.sqrt((xx - cx) ** 2 + (yy - (cy - d)) ** 2)
        m = np.clip((Rr - eye_d) / 1.2, 0, 1) * np.clip((R - lid_d) / 1.1, 0, 1)
        # depth inside the visible lid band: 0 at the free edge, 1 at the top
        span = max(2.0, 2.0 * R * cover)
        t = np.clip((R - lid_d) / span, 0, 1)
        dome = 0.80 + 0.24 * np.sin(np.pi * np.clip(t * 1.05, 0, 1) ** 0.75)
        crease = 1.0 - 0.28 * np.clip((t - 0.86) / 0.14, 0, 1)
        rim = 1.0 + 0.18 * np.exp(-((t - 0.06) / 0.07) ** 2)
        shade = np.clip(dome * crease * rim, 0.55, 1.15)
        col = np.clip(tex.astype(np.float32) * shade[..., None], 0, 255)
        return np.dstack([col.astype(np.uint8), (m * 255).astype(np.uint8)])

    @staticmethod
    def _blit_sprite(dst, spr, x0, y0):
        h, w = spr.shape[:2]
        H_, W_ = dst.shape[:2]
        x0c, y0c = max(0, x0), max(0, y0)
        x1c, y1c = min(W_, x0 + w), min(H_, y0 + h)
        if x1c <= x0c or y1c <= y0c:
            return
        sx0, sy0 = x0c - x0, y0c - y0
        sx1, sy1 = sx0 + (x1c - x0c), sy0 + (y1c - y0c)
        patch = spr[sy0:sy1, sx0:sx1].astype(np.float32)
        a = patch[:, :, 3:4] / 255.0
        roi = dst[y0c:y1c, x0c:x1c].astype(np.float32)
        rgb = patch[:, :, :3] * a + roi[:, :, :3] * (1 - a)
        alpha = np.maximum(roi[:, :, 3:4] / 255.0, a)
        dst[y0c:y1c, x0c:x1c, :3] = rgb.astype(np.uint8)
        dst[y0c:y1c, x0c:x1c, 3] = (alpha[..., 0] * 255).astype(np.uint8)

SRC_H = SRC_W = 640


# ------------------------------------------------------------------ render
class Renderer:
    def __init__(self, scene: Scene):
        self.s = scene
        # static background at low res for the moving bokeh
        self.bg_small = cv2.resize(scene.sky, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        self.vign = self._vignette()

    def _vignette(self):
        u = (np.arange(W, dtype=np.float32)[None, :] - W / 2) / (W / 2)
        v = (np.arange(H, dtype=np.float32)[:, None] - H / 2) / (H / 2)
        r = np.sqrt(u ** 2 + v ** 2)
        return np.clip(1.04 - 0.30 * np.clip(r - 0.28, 0, 2) ** 1.5, 0.34, 1.0).astype(np.float32)

    def render(self, t):
        s = self.s
        sec = section(t)
        en = intensity(t)
        ph = beat_phase(t)
        hit = math.exp(-ph * 5.0)
        bar = bar_of(t)

        # ---------- camera: punch on the kick + sway
        punch = 1.0 + (0.028 if sec in ("drop", "groove", "build") else 0.012) * hit * en
        zoom = (1.02 + 0.02 * math.sin(t * 0.18)) * punch
        shake_x = shake_y = 0.0
        if sec == "drop":
            shake_x = 4.0 * hit * math.sin(t * 97.0)
            shake_y = 4.0 * hit * math.cos(t * 83.0)

        # ---------- background
        frame = cv2.resize(s.sky, (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32) * 0.58
        frame = self._bokeh(frame, t, en)
        frame = self._lasers(frame, t, sec, hit, en, front=False)

        # ---------- frog
        warped = s.warp_frog(t)
        # scale: 1500 px tall at zoom 1, feet (bottom of the crop) at y=1660
        base_h = 1310.0
        sc = base_h / SRC_H * zoom
        nw, nh = int(round(SRC_W * sc)), int(round(SRC_H * sc))
        spr = cv2.resize(warped, (nw, nh), interpolation=cv2.INTER_CUBIC)
        # mild sharpen so the 2.4x upscale keeps its bite
        blur = cv2.GaussianBlur(spr[:, :, :3], (0, 0), 1.2)
        spr[:, :, :3] = cv2.addWeighted(spr[:, :, :3], 1.35, blur, -0.35, 0)
        # bounce offset applied to the placement (feet stay put)
        bounce = pos(math.sin(math.pi * ph), 1.6) * en
        cx = W / 2 + shake_x
        cy = 1678 - 26 * bounce + shake_y
        x0 = int(round(cx - nw / 2))
        y0 = int(round(cy - nh))
        self._composite(frame, spr, x0, y0)

        # rim light on the frog, tinted by the stage
        self._rim_light(frame, spr, x0, y0, t, hit, sec)
        # beams also cut across the character so the stage reads as 3D
        frame = self._lasers(frame, t, sec, hit, en, front=True)

        # ---------- stage furniture
        self._speakers(frame, t, hit, en)
        self._desk(frame, t, hit, en)
        self._crowd(frame, t, hit)
        if sec == "drop" or (sec == "build" and bar >= 11):
            self._confetti(frame, t, en)
        self._strobe(frame, t, sec, hit)

        # ---------- grade
        frame = self._grade(frame, t, sec, hit)
        self._titles(frame, t, sec)

        # fades
        if t < 1.2:
            frame *= smooth(t / 1.2)
        if t > DURATION - 2.6:
            frame *= 1.0 - smooth((t - (DURATION - 2.6)) / 2.6)
        return np.clip(frame, 0, 255).astype(np.uint8)

    # ---------------------------------------------------------------- parts
    def _bokeh(self, frame, t, en):
        s = self.s
        small = self.bg_small.astype(np.float32)
        layer = np.zeros((H // 4, W // 4, 3), np.float32)
        for b in s.bokeh:
            x = (b["x"] / 4 + 8 * math.sin(t * 0.25 + b["ph"])) % (W // 4)
            y = (b["y"] / 4 + (t * b["v"] / 4) % (H // 4))
            col = (np.array([200, 120, 255]) if b["hue"] < 0.5 else np.array([120, 255, 220]))
            cv2.circle(layer, (int(x), int(y)), max(2, int(b["r"] / 4)),
                       tuple(float(c) for c in col * 0.10), -1, cv2.LINE_AA)
        layer = cv2.GaussianBlur(layer, (0, 0), 6)
        small += layer * (0.5 + 0.8 * en)
        frame += (cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)
                  - cv2.resize(self.bg_small, (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32)) * 0.55
        return np.clip(frame, 0, 255)

    def _lasers(self, frame, t, sec, hit, en, front=False):
        if en < 0.35:
            return frame
        layer = np.zeros((H, W), np.float32)
        n = 7
        origin = (W // 2, -70)
        for i in range(n):
            ang = math.radians(-62 + i * (124 / (n - 1)) + 16 * math.sin(t * 0.42 + i * 0.8))
            length = 2600
            x1 = origin[0] + math.sin(ang) * length
            y1 = origin[1] + math.cos(ang) * length
            if not front:
                a = 0.30 * en * (0.45 + 0.55 * hit)
                cv2.line(layer, origin, (int(x1), int(y1)), float(a), 7, cv2.LINE_AA)
            else:
                a = 0.15 * en * (0.35 + 0.65 * hit)
                cv2.line(layer, origin, (int(x1), int(y1)), float(a), 3, cv2.LINE_AA)
        layer = cv2.GaussianBlur(layer, (0, 0), 4.0 if front else 11.0)
        col = np.array([150, 255, 205], np.float32) if not front else np.array([120, 255, 190], np.float32)
        frame += layer[..., None] * col
        return np.clip(frame, 0, 255)

    def _composite(self, frame, spr, x0, y0):
        h, w = spr.shape[:2]
        x1, y1 = x0 + w, y0 + h
        cx0, cy0 = max(0, x0), max(0, y0)
        cx1, cy1 = min(W, x1), min(H, y1)
        if cx1 <= cx0 or cy1 <= cy0:
            return
        sx0, sy0 = cx0 - x0, cy0 - y0
        sx1, sy1 = sx0 + (cx1 - cx0), sy0 + (cy1 - cy0)
        patch = spr[sy0:sy1, sx0:sx1].astype(np.float32)
        a = patch[:, :, 3:4] / 255.0
        frame[cy0:cy1, cx0:cx1, :3] = patch[:, :, :3] * a + frame[cy0:cy1, cx0:cx1, :3] * (1 - a)

    def _rim_light(self, frame, spr, x0, y0, t, hit, sec):
        # a soft coloured spot behind the frog + a highlight edge
        g = self._glow(360, 3.0)
        cx = W / 2
        cy = 1180
        self._add_glow(frame, g, cx, cy, 620,
                       np.array([70, 40, 120]) * (0.5 + 0.4 * hit))

    @staticmethod
    def _glow(size, sigma):
        ax = np.arange(size, dtype=np.float32) - size / 2
        g = np.exp(-(ax[None, :] ** 2 + ax[:, None] ** 2) / (2 * sigma ** 2))
        return g / g.max()

    @staticmethod
    def _add_glow(frame, sprite, cx, cy, radius, color):
        n = sprite.shape[0]
        x0, y0 = int(cx - radius), int(cy - radius)
        x1, y1 = x0 + 2 * int(radius), y0 + 2 * int(radius)
        cx0, cy0 = max(0, x0), max(0, y0)
        cx1, cy1 = min(frame.shape[1], x1), min(frame.shape[0], y1)
        if cx1 <= cx0 or cy1 <= cy0:
            return
        g = cv2.resize(sprite, (max(1, cx1 - cx0), max(1, cy1 - cy0)), interpolation=cv2.INTER_LINEAR)
        frame[cy0:cy1, cx0:cx1] += g[..., None] * color

    def _speakers(self, frame, t, hit, en):
        # two stacks in the foreground, woofers pumping on the kick
        for side, x in (("L", 96), ("R", W - 96)):
            bw, bh = 178, 640
            x0 = x - bw // 2 if side == "L" else x - bw // 2
            y0 = 1000
            cv2.rectangle(frame, (int(x0), int(y0)), (int(x0 + bw), int(y0 + bh)), (12, 10, 16), -1, cv2.LINE_AA)
            for k, cyw in enumerate((0.28, 0.68)):
                r = int(44 * (1 + 0.05 * hit)) if k == 0 else int(30 * (1 + 0.08 * hit))
                cw = (int(x0 + bw / 2), int(y0 + bh * cyw))
                cv2.circle(frame, cw, int(r * 1.25), (26, 22, 30), -1, cv2.LINE_AA)
                cv2.circle(frame, cw, r, (10, 8, 12), -1, cv2.LINE_AA)
                cv2.circle(frame, cw, max(3, r // 3), (40, 34, 44), -1, cv2.LINE_AA)
            # glowing edge
            cv2.rectangle(frame, (int(x0) + 2, int(y0) + 2), (int(x0 + bw) - 2, int(y0 + bh) - 2),
                          (60, 200, 140), 2, cv2.LINE_AA)

    def _desk(self, frame, t, hit, en):
        # DJ desk hides the cropped thighs
        y0 = 1612
        pts = np.array([[0, y0], [W, y0], [W, H], [0, H]], np.int32)
        cv2.fillPoly(frame, [pts], (13, 11, 17))
        cv2.line(frame, (0, y0), (W, y0), (90, 255, 170), 3, cv2.LINE_AA)
        cv2.line(frame, (0, y0 + 6), (W, y0 + 6), (40, 120, 90), 1, cv2.LINE_AA)
        # EQ bars inside the panel
        n = 22
        pad = 80
        bw = (W - pad * 2) // n
        for i in range(n):
            v = 0.30 + 0.70 * abs(math.sin(t * (2 + (i % 5)) + i * 0.7)) * (0.45 + 0.55 * en)
            h = int(14 + v * 150 * (0.55 + 0.45 * hit))
            x = pad + i * bw
            col = (90, 255, 160) if i % 3 else (255, 190, 100)
            cv2.rectangle(frame, (x, H - 90 - h), (x + bw - 8, H - 90), col, -1, cv2.LINE_AA)

    def _crowd(self, frame, t, hit):
        layer = self.s.crowd.copy()
        dy = int(6 * hit)
        layer = np.roll(layer, dy, axis=0)
        a = layer[:, :, 3:4].astype(np.float32) / 255
        frame *= 1.0 - a * 0.85
        return frame

    def _confetti(self, frame, t, en):
        c = self.s.conf
        for i in range(len(c["x"])):
            x = (c["x"][i] + c["vx"][i] * t) % (W + 200) - 100
            y = (c["y"][i] + c["vy"][i] * t) % (H + 200) - 100
            rot = c["rot"][i] + c["vr"][i] * t
            w_, h_ = c["w"][i], c["h"][i]
            pts = cv2.boxPoints(((x, y), (w_, h_), rot))
            cv2.fillConvexPoly(frame, pts.astype(np.int32), self.s.conf_cols[int(c["c"][i])], cv2.LINE_AA)
        return frame

    def _strobe(self, frame, t, sec, hit):
        if sec != "drop":
            return
        fl = 0.0
        if (t / BEAT) % 4 < 0.12:
            fl = 0.10
        if fl > 0:
            frame += 255.0 * fl

    def _grade(self, frame, t, sec, hit):
        f = frame / 255.0
        f += 0.06 * (f ** 2) * (1.5 - f)
        # magenta/teal club split tone
        lum = 0.2126 * f[:, :, 2] + 0.7152 * f[:, :, 1] + 0.0722 * f[:, :, 0]
        f[:, :, 2] += 0.045 * lum
        f[:, :, 0] += 0.045 * (1 - lum)
        # bloom
        small = cv2.resize(f, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        bright = np.clip(small - 0.70, 0, 1.2)
        bloom = cv2.GaussianBlur(bright, (0, 0), 6)
        f += cv2.resize(bloom, (W, H), interpolation=cv2.INTER_LINEAR) * (0.35 + 0.2 * hit)
        f *= self.vign[..., None]
        return np.clip(f * 255.0, 0, 255)

    def _titles(self, frame, t, sec):
        s = self.s
        # persistent brand: top-centre (the frame is empty there), fades out
        # once the frog fills the shot
        brand_a = smooth((t - 1.6) / 1.4) * (1.0 - smooth((t - 30.0) / 3.0))
        self._text(frame, "dj", 0.5, 0, 96, alpha=0.98 * brand_a, scale=1.12)
        self._text(frame, "title", 0.5, 0, 214, alpha=0.85 * brand_a)
        self._text(frame, "bpm", 0.5, 0, 292, alpha=0.55 * brand_a)
        # section call-outs
        if 45.0 <= t < 52.5:
            a = smooth((t - 45.0) / 0.6) * (1 - smooth((t - 51.5) / 1.0))
            self._text(frame, "hands", 0.5, 0, 1424, alpha=a)
        for t0 in (60.0, 63.75, 67.5):
            if t0 <= t < t0 + 1.2:
                a = smooth((t - t0) / 0.12) * (1 - smooth((t - t0 - 0.75) / 0.45))
                sc = 0.74 + 0.12 * math.exp(-(t - t0) * 8)
                self._text(frame, "drop", 0.5, 0, 512, alpha=a, scale=sc)
        # end card
        if t > 112.0:
            a = smooth((t - 112.0) / 1.2)
            self._text(frame, "dj", 0.5, 0, 220, alpha=a)
            self._text(frame, "title", 0.5, 0, 380, alpha=a * 0.9)

    def _text(self, frame, name, cx_frac, dx, dy, alpha=1.0, scale=1.0):
        arr = self.s.textures.get(name)
        if arr is None or alpha <= 0.01:
            return
        h, w = arr.shape[:2]
        if scale != 1.0:
            nw, nh = int(w * scale), int(h * scale)
            arr = cv2.resize(arr, (nw, nh), interpolation=cv2.INTER_LINEAR)
            h, w = nh, nw
        x0 = int(W * cx_frac - w / 2 + dx)
        y0 = int(dy)
        x1, y1 = x0 + w, y0 + h
        cx0, cy0 = max(0, x0), max(0, y0)
        cx1, cy1 = min(W, x1), min(H, y1)
        if cx1 <= cx0 or cy1 <= cy0:
            return
        sx0, sy0 = cx0 - x0, cy0 - y0
        patch = arr[sy0:sy0 + (cy1 - cy0), sx0:sx0 + (cx1 - cx0)].astype(np.float32)
        a = patch[:, :, 3:4] / 255.0 * alpha
        roi = frame[cy0:cy1, cx0:cx1, :]
        frame[cy0:cy1, cx0:cx1, :] = patch[:, :, :3] * a + roi * (1 - a)


# ------------------------------------------------------------------ encode
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
    ap.add_argument("--end", type=float, default=DURATION)
    ap.add_argument("--out", type=str, default=os.path.join(OUT, "dj_frog.mp4"))
    ap.add_argument("--crf", type=int, default=18)
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    scene = Scene()
    r = Renderer(scene)

    if args.preview:
        for ts in args.preview.split(","):
            t = float(ts)
            img = r.render(t)
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
        proc.stdin.write(r.render(t).tobytes())
        if i % 60 == 0:
            print(f"\rframe {i}/{frames} t={t:5.1f}s", end="", flush=True)
    proc.stdin.close()
    proc.wait()
    print("\nwrote", args.out)


if __name__ == "__main__":
    main()
