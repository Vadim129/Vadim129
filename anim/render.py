"""Living painting renderer.

Turns the still painting into a 33 s cinematic loop:

  * 2.5D camera (zoom / pan) with depth driven parallax
  * volumetric window shafts, breathing crystals, dust motes
  * waking eyes (glow + blinks)
  * the rook performs a full chess move: lift -> arc -> land -> ripple
  * colour grade, bloom, fog, film grain, fade in/out, end title

Usage
-----
    python3 anim/render.py --preview 2.0,13.9,17.0,18.3,27.0
    python3 anim/render.py                 # full render -> anim/media/living_painting.mp4

Frames are piped straight into ffmpeg (libx264).
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

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT = os.path.join(HERE, "media")

# ------------------------------------------------------------------ config
W, H = 1080, 1620          # 2:3 output, native aspect of the painting
FPS = 30
DURATION = 33.0
S = H / 2560.0             # source px -> output px at zoom 1
SRC_W, SRC_H = 1706, 2560


def configure(w, h):
    """Pick an output frame. Height drives the scale (the painting is 2:3 and
    2560 px tall), width just crops the sides — so 1080x1920 gives 9:16 with the
    same vertical framing as the original 1080x1620 cut."""
    global W, H, S
    W, H = int(w), int(h)
    S = H / float(SRC_H)

EYE_OPEN = 2.6             # eyes switch on
ROOK_LIFT = 15.2
ROOK_GO = 15.7
ROOK_LAND = 18.2
TITLE_IN = 27.8
FADE_OUT = (31.7, 33.0)
FADE_IN = (0.0, 1.4)

# camera keyframes: (t, cx, cy, zoom)
CAMERA = [
    (0.0, 853, 1360, 1.005),
    (6.0, 858, 1335, 1.050),
    (11.8, 918, 1200, 1.620),   # gaze: close on the head
    (13.6, 900, 1480, 1.500),   # tilt down to the hand
    (15.2, 858, 1565, 1.450),   # the piece under the finger
    (17.8, 945, 1630, 1.400),   # follow the rook
    (21.4, 928, 1600, 1.290),
    (24.4, 878, 1440, 1.160),
    (27.6, 853, 1330, 1.010),   # wide hero
    (33.0, 853, 1300, 1.030),
]

# rook travel in source pixels
ROOK_FROM = (1013.4, 1993.0)
ROOK_TO = (1104.0, 1974.0)


def smooth(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def smoother(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * t * (t * (t * 6 - 15) + 10)


def camera_at(t: float):
    for i in range(len(CAMERA) - 1):
        t0, x0, y0, z0 = CAMERA[i]
        t1, x1, y1, z1 = CAMERA[i + 1]
        if t0 <= t <= t1:
            k = smoother((t - t0) / max(1e-6, t1 - t0))
            return (
                x0 + (x1 - x0) * k,
                y0 + (y1 - y0) * k,
                z0 + (z1 - z0) * k,
            )
    return CAMERA[-1][1:]


def blink_amount(t: float) -> float:
    """1.0 = wide open, 0.0 = shut."""
    if t < EYE_OPEN:
        return 0.0
    b = 1.0
    for centre, width, depth in [
        (2.62, 0.09, 1.0),   # power-on stutter
        (3.05, 0.10, 0.85),
        (3.42, 0.12, 0.55),
        (8.30, 0.16, 1.0),
        (8.62, 0.13, 0.8),
        (12.60, 0.18, 1.0),
        (18.90, 0.15, 0.9),
        (25.10, 0.22, 1.0),
    ]:
        d = abs(t - centre) / width
        if d < 1.0:
            b = min(b, 1.0 - depth * (1.0 - d * d))
    return max(0.0, b)


# ---------------------------------------------------------------- rig pose
# (angle in degrees about the part pivot, scale about the pivot)
def rig_pose(t: float):
    """Per-part pose: (roll degrees, (scale_x, scale_y), dx, dy).
    Angles stay small (<=4 deg) because the rig warps one bitmap — big rotations
    would tear the painting. Translation does most of the "looking around"."""
    def osc(f, ph):
        return math.sin(math.tau * f * t + ph)

    def pulse(t0, dur, power=1.2):
        k = min(1.0, max(0.0, (t - t0) / dur))
        return math.sin(math.pi * k) ** power

    idle = 0.55 * osc(0.71, 0.4) + 0.3 * osc(1.63, 1.9)

    # ---------------- head
    # wake -> study the board -> cocked "thinking" tilt -> glance at the hand
    # -> two approving nods -> settle back to the viewer
    head_roll = 0.9 * osc(0.33, 0.2) + idle * 0.8
    head_roll += 1.6 * smooth((t - 4.2) / 2.2)
    head_roll += 4.2 * pulse(8.2, 2.8, 1.0)          # cocks its head, thinking
    head_roll -= 3.0 * pulse(12.2, 2.4, 1.0)
    head_roll += 1.5 * pulse(20.3, 0.9, 1.0)         # nod
    head_roll += 1.5 * pulse(21.25, 0.9, 1.0)
    head_roll += 2.2 * smooth((t - 23.6) / 2.8) - 2.2 * smooth((t - 29.0) / 3.0)

    # yaw read as a horizontal squish + sideways shift (no z-axis tearing)
    head_yaw = 3.0 * pulse(8.2, 2.8, 1.0) - 2.2 * pulse(12.2, 2.4, 1.0)
    head_yaw += 2.0 * smooth((t - 23.6) / 2.8) - 2.0 * smooth((t - 29.0) / 3.0)
    head_kx = 1.0 - 0.016 * head_yaw
    head_ky = 1.0 + 0.008 * head_yaw

    head_y = -14.0 * (1.0 - smooth(t / 2.8))         # lifts as it wakes
    head_y += 3.2 * math.sin(math.tau * 0.22 * t)     # slow breathing bob
    head_y -= 9.0 * pulse(8.2, 2.8, 1.0)              # leans in over the board
    head_y += 5.0 * pulse(12.2, 2.4, 1.0)
    head_y += 4.0 * pulse(20.3, 0.7, 1.6)             # nod down
    head_y += 4.0 * pulse(21.25, 0.7, 1.6)
    for nt in (28.2, 31.4):
        head_y += 2.2 * pulse(nt, 1.4, 1.0)

    head_x = 4.0 * osc(0.19, 1.1) + 7.0 * head_yaw / 3.0 * 1.6

    breath = 1.0 + 0.008 * math.sin(math.tau * t / 4.6)

    # ---------------- arms / hands
    larm_a = -1.6 * smooth((t - 4.2) / 2.2) + 1.6 * smooth((t - 7.4) / 2.2) + 1.4 * osc(0.27, 0.8) + idle * 0.5
    lfore_a = 1.4 * osc(0.31, 2.1) + 1.0 * osc(0.19, 0.3) + idle * 0.45
    lhand_a = 2.4 * osc(0.43, 1.2) + 1.6 * osc(0.24, 2.7)
    lhand_a += 7.0 * pulse(10.1, 1.1, 1.0)            # deliberate tap on the board
    lhand_a -= 4.0 * pulse(25.4, 1.4, 1.0)
    lhand_y = 4.0 * pulse(10.1, 1.1, 1.4)
    lhand_y -= 2.5 * pulse(25.4, 1.4, 1.4)

    rarm_a = -2.6 * pulse(14.9, 1.6, 1.2) + 2.6 * pulse(17.6, 2.4, 1.2)
    rarm_a += 1.0 * osc(0.21, 1.4) + idle * 0.5
    rhand_a = -3.6 * pulse(14.9, 1.6, 1.2) + 3.6 * pulse(17.6, 2.4, 1.2)
    rhand_a += 1.6 * osc(0.37, 0.6)
    rhand_y = -2.4 * pulse(14.9, 1.6, 1.4) + 2.4 * pulse(17.6, 2.4, 1.4)

    return {
        "head": (head_roll, (head_kx, head_ky), head_x, head_y),
        "torso": (0.4 * osc(0.21, 0.7), (breath, breath), 0.0, 0.0),
        "larm": (larm_a, 1.0, 0.0, 0.0),
        "lfore": (lfore_a, 1.0, 0.0, 0.0),
        "lhand": (lhand_a, 1.0, 0.0, lhand_y),
        "rarm": (rarm_a, 1.0, 0.0, 0.0),
        "rhand": (rhand_a, 1.0, 0.0, rhand_y),
    }


def rook_state(t: float):
    """Return (x, y, lift, shadow_alpha, speed)."""
    if t < ROOK_LIFT:
        return ROOK_FROM[0], ROOK_FROM[1], 0.0, 1.0, 0.0
    if t < ROOK_GO:
        k = smooth((t - ROOK_LIFT) / (ROOK_GO - ROOK_LIFT))
        return ROOK_FROM[0], ROOK_FROM[1], 26 * k, 1.0 - 0.35 * k, 0.0
    if t < ROOK_LAND:
        k = smoother((t - ROOK_GO) / (ROOK_LAND - ROOK_GO))
        x = ROOK_FROM[0] + (ROOK_TO[0] - ROOK_FROM[0]) * k
        y = ROOK_FROM[1] + (ROOK_TO[1] - ROOK_FROM[1]) * k
        lift = 26 + 64 * math.sin(math.pi * min(1.0, k * 1.05))
        speed = math.sin(math.pi * k)
        return x, y, lift, 0.65, speed
    return ROOK_TO[0], ROOK_TO[1], 0.0, 1.0, 0.0


# ------------------------------------------------------------------ assets
def depth_src():
    return cv2.imread(os.path.join(ASSETS, "depth.png"), cv2.IMREAD_GRAYSCALE)


class Scene:
    def __init__(self):
        self.plate = cv2.imread(os.path.join(ASSETS, "plate.png"))
        self.source = cv2.imread(os.path.join(ASSETS, "source.jpg"))
        self.rook = cv2.imread(os.path.join(ASSETS, "rook.png"), cv2.IMREAD_UNCHANGED)
        self.depth = cv2.imread(os.path.join(ASSETS, "depth.png"), cv2.IMREAD_GRAYSCALE)
        m = np.load(os.path.join(ASSETS, "masks.npz"))
        self.masks = np.stack(
            [
                (np.clip(m["beams"], 0, 1) * 255).astype(np.uint8),
                (np.clip(m["crystal"], 0, 1) * 255).astype(np.uint8),
                (np.clip(m["window"], 0, 1) * 255).astype(np.uint8),
            ],
            axis=-1,
        )
        self.meta = json.load(open(os.path.join(ASSETS, "meta.json")))

        # ---- articulation rig: seven feathered weight maps
        self.parts_src = m["parts"].astype(np.float32) / 255.0      # (7, SRC_H, SRC_W)
        self.slime_src = m["slime"].astype(np.float32) / 255.0
        self.drips_src = (m["drips"].astype(np.float32) / 255.0) if "drips" in m.files else np.zeros_like(self.slime_src)
        self.RIG_PARTS = ["head", "torso", "larm", "lfore", "lhand", "rarm", "rhand"]
        self.PIVOTS = {
            "head": (925.0, 1240.0),
            "torso": (985.0, 1520.0),
            "larm": (706.0, 1332.0),
            "lfore": (486.0, 1512.0),
            "lhand": (452.0, 1846.0),
            "rarm": (1332.0, 1716.0),
            "rhand": (930.0, 1560.0),
        }
        # quarter-resolution copies drive the displacement solve (it is smooth,
        # so the cheap grid is plenty) — full-res is used only for sampling
        self.parts_low = np.stack(
            [cv2.resize(p_, (SRC_W // 4, SRC_H // 4), interpolation=cv2.INTER_AREA) for p_ in self.parts_src]
        )
        self.depth_low = cv2.resize(depth_src(), (SRC_W // 4, SRC_H // 4), interpolation=cv2.INTER_AREA)

        # screen-space helpers
        u = np.arange(W, dtype=np.float32)[None, :] - W / 2
        v = np.arange(H, dtype=np.float32)[:, None] - H / 2
        self.U = np.broadcast_to(u, (H, W)).copy()
        self.V = np.broadcast_to(v, (H, W)).copy()

        # vignette
        rr = np.sqrt((self.U / (W * 0.5)) ** 2 + (self.V / (H * 0.5)) ** 2)
        self.vignette = np.clip(1.06 - 0.30 * np.clip(rr - 0.25, 0, 2) ** 1.7, 0.52, 1.0).astype(np.float32)

        # grain bank
        rng = np.random.default_rng(7)
        self.grain = [(rng.normal(0, 1.6, (H, W, 1))).astype(np.float32) for _ in range(12)]

        # dust motes in source coordinates
        rng = np.random.default_rng(21)
        n = 170
        self.dust = dict(
            x=rng.uniform(80, SRC_W - 80, n),
            y=rng.uniform(420, 2350, n),
            z=rng.uniform(0.15, 1.0, n),
            vy=rng.uniform(6, 26, n),
            vx=rng.uniform(-8, 8, n),
            ph=rng.uniform(0, math.tau, n),
            sz=rng.uniform(0.6, 2.3, n),
        )
        # landing dust burst
        self.puff = dict(
            ang=rng.uniform(0, math.tau, 90),
            r=rng.uniform(0.25, 1.0, 90),
            spd=rng.uniform(28, 120, 90),
            sz=rng.uniform(0.8, 2.4, 90),
        )

        # falling droplets seeded on the brightest drip heads
        rng2 = np.random.default_rng(33)
        drips = getattr(self, "drips_src", None)
        pts = []
        if drips is not None:
            dd = cv2.dilate((drips > 0.85).astype(np.uint8), np.ones((3, 3), np.uint8))
            n_, lab_, st_, ce_ = cv2.connectedComponentsWithStats(dd, 8)
            for i in range(1, n_):
                if 120 < st_[i, cv2.CC_STAT_AREA] < 3000:
                    pts.append((ce_[i][0], ce_[i][1]))
        if not pts:
            pts = [(1068.0, 1442.0), (1102.0, 1470.0), (1206.0, 1512.0)]
        pts = pts[:6]
        self.drops = dict(
            x=np.array([p[0] for p in pts]),
            y=np.array([p[1] for p in pts]),
            r=np.array([max(2.5, 4.5) for _ in pts]),
            per=np.array([rng2.uniform(6.5, 11.0) for _ in pts]),
            t0=np.array([rng2.uniform(0.8, 7.0) for _ in pts]),
        )

        # low fog tile
        rng = np.random.default_rng(4)
        base = rng.normal(0, 1, (180, 320)).astype(np.float32)
        base = cv2.GaussianBlur(base, (0, 0), 22)
        base = (base - base.min()) / (np.ptp(base) + 1e-6)
        self.fog_tile = base
        self.fog_mask = (np.clip((np.arange(H)[:, None] - H * 0.42) / (H * 0.5), 0, 1) ** 1.4).astype(np.float32)

        # glow sprites
        self.eye_glow = self._glow(96, 3.2)
        self.spark = self._glow(48, 2.0)
        self._build_title()

    @staticmethod
    def _glow(size, sigma):
        ax = np.arange(size, dtype=np.float32) - size / 2
        g = np.exp(-(ax[None, :] ** 2 + ax[:, None] ** 2) / (2 * sigma**2))
        return g / g.max()

    def _build_title(self):
        from PIL import Image, ImageDraw, ImageFont

        title = "ТИХИЙ ХОД"
        sub = "the quiet move"
        try:
            f1 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 92)
            f2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
        except OSError:  # pragma: no cover
            f1 = f2 = ImageFont.load_default()
        img = Image.new("RGBA", (W, 420), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # letter-spaced title
        text_w = sum(d.textlength(c, font=f1) + 18 for c in title) - 18
        x = (W - text_w) / 2
        for c in title:
            d.text((x, 70), c, font=f1, fill=(240, 232, 214, 255))
            x += d.textlength(c, font=f1) + 18
        tw = d.textlength(sub, font=f2)
        d.text(((W - tw) / 2, 214), sub, font=f2, fill=(206, 198, 182, 230))
        d.line([(W / 2 - 76, 196), (W / 2 + 76, 196)], fill=(214, 205, 188, 170), width=2)
        self.title_rgba = np.array(img)
        self.title_alpha = (self.title_rgba[:, :, 3].astype(np.float32) / 255)[..., None]
        self.title_rgb = self.title_rgba[:, :, :3].astype(np.float32)


# ------------------------------------------------------------------ frame
class Renderer:
    def __init__(self, scene: Scene):
        self.s = scene

    # ---- projection helpers
    def project(self, x, y, cx, cy, z):
        return (x - cx) * S * z + W / 2, (y - cy) * S * z + H / 2

    def render(self, t: float) -> np.ndarray:
        s = self.s
        cx, cy, z = camera_at(t)
        # handheld micro drift
        cx += 2.4 * math.sin(t * 0.63 + 0.4) + 1.1 * math.sin(t * 1.71)
        cy += 1.9 * math.cos(t * 0.51) + 0.9 * math.sin(t * 1.33 + 1.2)
        z *= 1.0 + 0.0016 * math.sin(t * 1.9)

        # parallax from a slow lateral drift (gives the 2.5D feel)
        par_x = 16.0 * math.sin(t * 0.19 + 0.7) + 6.0 * math.sin(t * 0.43)
        par_y = 7.0 * math.cos(t * 0.23 + 0.2)

        inv = 1.0 / (S * z)
        xs0 = cx + self.s.U * inv
        ys0 = cy + self.s.V * inv
        depth = s.depth
        di = np.clip(ys0, 0, SRC_H - 1).astype(np.int32)
        dj = np.clip(xs0, 0, SRC_W - 1).astype(np.int32)
        dnorm = depth[di, dj].astype(np.float32) / 255.0
        off = 0.5 - dnorm
        map_x = (xs0 + par_x * off).astype(np.float32)
        map_y = (ys0 + par_y * off).astype(np.float32)

        # ---- articulation: blend a rigid rotation of every body part
        self.pose = rig_pose(t)
        self._update_slime(t)
        rig_x, rig_y = self._rig_displacement(dnorm, par_x, par_y, inv, cx, cy, z)
        base = cv2.remap(s.plate, map_x - rig_x, map_y - rig_y,
                         cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        masks = cv2.remap(s.masks, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        beams = masks[:, :, 0].astype(np.float32) / 255.0
        crystal = masks[:, :, 1].astype(np.float32) / 255.0
        window = masks[:, :, 2].astype(np.float32) / 255.0

        frame = base.astype(np.float32) / 255.0

        # ---- viscous goo: the yellow-green slime creeps and glistens
        slime = cv2.remap(s.slime_src, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        if self.slime_flow is not None:
            flow_x = cv2.remap(self.slime_flow[0], map_x / 8.0, map_y / 8.0,
                               cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            flow_y = cv2.remap(self.slime_flow[1], map_x / 8.0, map_y / 8.0,
                               cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            slime_s = cv2.remap(s.source, map_x + flow_x, map_y + flow_y,
                                cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32) / 255.0
            a = (slime * 0.75)[..., None]
            frame = frame * (1 - a) + slime_s * a
        sheen = 0.5 + 0.5 * math.sin(t * 0.9 + 1.7)
        frame += (slime * (0.045 + 0.035 * sheen))[..., None] * np.array([0.55, 0.95, 0.25], np.float32)

        # ---- droplet body: rounded shading + a travelling highlight so the goo
        # reads as wet rather than as a colour wash
        drips = cv2.remap(s.drips_src, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        if drips.max() > 0.02:
            d_small = cv2.resize(drips, (W // 3, H // 3), interpolation=cv2.INTER_AREA)
            edge = cv2.GaussianBlur(d_small, (0, 0), 3) - d_small
            rim = cv2.resize(np.clip(edge * 2.4, 0, 1), (W, H), interpolation=cv2.INTER_LINEAR)
            frame += (rim * 0.22)[..., None] * np.array([0.62, 0.88, 0.30], np.float32)
            hl = cv2.GaussianBlur(np.roll(d_small, (-3, -3), axis=(0, 1)), (0, 0), 2.2)
            hl = cv2.resize(hl, (W, H), interpolation=cv2.INTER_LINEAR)
            flick = 0.55 + 0.45 * math.sin(t * 1.25 + 0.8)
            frame += (hl * drips * 0.34 * flick)[..., None] * np.array([0.95, 1.0, 0.80], np.float32)
            frame = np.clip(frame, 0, 2.0)

        # ---------------------------------------------------------- light
        wake = smooth((t - 1.4) / 2.2)
        shimmer = 1.0 + 0.16 * math.sin(t * 0.7) + 0.09 * math.sin(t * 1.53 + 1.1)
        warm = np.array([1.0, 0.955, 0.865], np.float32)
        frame += (beams * 0.20 * shimmer * wake)[..., None] * warm
        frame += (window * (0.05 + 0.03 * math.sin(t * 0.35)))[..., None]

        # crystal breathing (two detuned pulses)
        pulse = 0.55 + 0.30 * math.sin(t * 0.85 - 0.6) + 0.15 * math.sin(t * 2.1 + 0.3)
        pulse = max(0.15, pulse)
        crystal = np.clip((crystal - 0.10) / 0.85, 0, 1)
        crystal_glow = cv2.GaussianBlur(crystal, (0, 0), 22)
        frame += (crystal * 0.10 * pulse)[..., None] * np.array([0.55, 1.0, 0.62], np.float32)
        frame += (crystal_glow * 0.17 * pulse)[..., None] * np.array([0.35, 0.95, 0.55], np.float32)

        # ---------------------------------------------------------- hero piece hover
        hover = 0.0

        # ---------------------------------------------------------- rook
        rx, ry, lift, shadow_a, speed = rook_state(t)
        self._draw_rook(frame, rx, ry - hover, lift, shadow_a, speed, cx, cy, z)
        self._draw_hero_glow(frame, t, cx, cy, z)

        # landing ripple + dust burst
        if ROOK_LAND - 0.02 <= t < ROOK_LAND + 1.4:
            u = (t - ROOK_LAND) / 1.4
            self._landing_ripple(frame, u, cx, cy, z)

        # ---------------------------------------------------------- eyes
        eyes = s.meta["eyes"]
        open_amt = blink_amount(t)
        glow = smooth((t - EYE_OPEN + 0.12) / 0.5)
        flick = 1.0
        if EYE_OPEN <= t < EYE_OPEN + 0.55:
            flick = 0.55 + 0.45 * (0.5 + 0.5 * math.sin((t - EYE_OPEN) * 46))
        for i, e in enumerate(eyes):
            ex, ey = self._map_point((e["x"], e["y"]), "head", cx, cy, z)
            if -80 < ex < W + 80 and -80 < ey < H + 80:
                rad = max(9.0, e["r"] * S * z * 3.4)
                self._add_glow(frame, s.eye_glow, ex, ey, rad,
                               np.array([1.0, 0.985, 0.93]) * (0.55 * glow * flick))
                rad2 = max(4.0, e["r"] * S * z * 1.55)
                self._add_glow(frame, s.eye_glow, ex, ey, rad2,
                               np.array([1.0, 1.0, 0.97]) * (0.85 * glow * flick * (0.4 + 0.6 * open_amt)))

        # ---------------------------------------------------------- droplets
        self._draw_droplets(frame, t, cx, cy, z, map_x, map_y)

        # ---------------------------------------------------------- dust
        self._draw_dust(frame, t, cx, cy, z, par_x, par_y, wake)

        # ---------------------------------------------------------- fog
        fog_a = 0.055 * (0.6 + 0.4 * math.sin(t * 0.21))
        if fog_a > 0.001:
            ox = int(t * 5) % 320
            oy = int(t * 2.2) % 180
            tile = np.roll(np.roll(s.fog_tile, -oy, axis=0), -ox, axis=1)
            tile = cv2.resize(tile, (W, H), interpolation=cv2.INTER_LINEAR)
            frame += (tile * s.fog_mask * fog_a)[..., None] * np.array([0.72, 0.82, 0.95], np.float32)

        # ---------------------------------------------------------- grade
        frame = self._grade(frame, t)

        # ---------------------------------------------------------- title
        self._draw_title(frame, t)

        # ---------------------------------------------------------- fades
        if t < FADE_IN[1]:
            frame *= smooth((t - FADE_IN[0]) / (FADE_IN[1] - FADE_IN[0]))
        if t > FADE_OUT[0]:
            frame *= 1.0 - smooth((t - FADE_OUT[0]) / (FADE_OUT[1] - FADE_OUT[0]))

        # grain last
        g = s.grain[int(t * FPS) % len(s.grain)]
        frame = frame * 255.0 + g
        return np.clip(frame, 0, 255).astype(np.uint8)

    # ---------------------------------------------------------------- rig
    def _rig_displacement(self, dnorm, par_x, par_y, inv, cx, cy, z):
        """Blend a rigid rotation of every body part into one screen-space
        displacement field (full-res pixels). Inverse mapping: for the part
        rotating by angle a about pivot A, the source we must read is
        B_rig = A + R^-1(B - A), so the field is  d = (B - A) - R^-1(B - A)."""
        s = self.s
        hq, wq = H // 4, W // 4
        if getattr(self, "_grid4", None) is None or self._grid4[0].shape[1] != wq:
            # absolute screen coordinates (pivots are absolute too)
            u = (np.arange(wq, dtype=np.float32) * 4.0 + 2.0)[None, :]
            v = (np.arange(hq, dtype=np.float32) * 4.0 + 2.0)[:, None]
            self._grid4 = (u, v)
        U4, V4 = self._grid4

        xs = cx + (U4 - W / 2) * inv
        ys = cy + (V4 - H / 2) * inv
        dl = s.depth_low[
            np.clip((ys / 4).astype(np.int32), 0, SRC_H // 4 - 1),
            np.clip((xs / 4).astype(np.int32), 0, SRC_W // 4 - 1),
        ].astype(np.float32) / 255.0
        off = 0.5 - dl
        mx = xs + par_x * off
        my = ys + par_y * off

        lx = np.clip(mx / 4.0, 0, SRC_W / 4 - 1).astype(np.float32)
        ly = np.clip(my / 4.0, 0, SRC_H / 4 - 1).astype(np.float32)
        wl = np.stack([cv2.remap(p_, lx, ly, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                       for p_ in s.parts_low])
        tot = np.maximum(1.0, wl.sum(0))
        wl = wl / tot[None]

        gx = np.zeros((hq, wq), np.float32)
        gy = np.zeros((hq, wq), np.float32)
        for i, name in enumerate(s.RIG_PARTS):
            a, k, tx, ty = self.pose[name]
            kx, ky = k if isinstance(k, tuple) else (k, k)
            w = wl[i]
            if w.max() < 0.004:
                continue
            pvx, pvy = s.PIVOTS[name]
            px = (pvx - cx) * S * z + W / 2
            py = (pvy - cy) * S * z + H / 2
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            # the grid holds full-resolution screen coordinates
            dx = U4 - px
            dy = V4 - py
            gx += w * (dx * (kx * ca - 1.0) - dy * (ky * sa) + tx * S * z)
            gy += w * (dx * (kx * sa) + dy * (ky * ca - 1.0) + ty * S * z)

        gx = cv2.resize(gx, (W, H), interpolation=cv2.INTER_LINEAR)
        gy = cv2.resize(gy, (W, H), interpolation=cv2.INTER_LINEAR)
        return gx, gy

    def _update_slime(self, t):
        """Slowly evolving drip field (source px, stored at 1/8 resolution)."""
        h8, w8 = SRC_H // 8, SRC_W // 8
        if getattr(self, "_slime_grid", None) is None:
            yy, xx = np.mgrid[0:h8, 0:w8].astype(np.float32)
            self._slime_grid = (xx * 8.0, yy * 8.0)
        xx, yy = self._slime_grid
        ph = t * 0.42
        fx = 7.0 * np.sin(yy / 95.0 + ph) * np.sin(xx / 150.0 - ph * 0.7)
        fy = 10.0 * np.cos(xx / 115.0 + ph * 1.05) * np.sin(yy / 135.0 + ph * 0.6)
        fy += 6.0 + 4.0 * np.sin(xx / 55.0 + t * 0.22)      # gravity: the goo runs down
        self.slime_flow = (fx.astype(np.float32), fy.astype(np.float32))

    def _map_point(self, pt, part, cx, cy, z):
        """Forward-transform a source point through a part's pose."""
        s = self.s
        a, k, tx, ty = self.pose[part]
        kx, ky = k if isinstance(k, tuple) else (k, k)
        pvx, pvy = s.PIVOTS[part]
        px = (pvx - cx) * S * z + W / 2
        py = (pvy - cy) * S * z + H / 2
        sx = (pt[0] - cx) * S * z + W / 2
        sy = (pt[1] - cy) * S * z + H / 2
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        dx, dy = (sx - px) * kx, (sy - py) * ky
        return (px + dx * ca - dy * sa + tx * S * z,
                py + dx * sa + dy * ca + ty * S * z)

    # ---------------------------------------------------------------- pieces
    def _draw_rook(self, frame, x, y, lift, shadow_a, speed, cx, cy, z):
        s = self.s
        spr = s.rook
        sh, sw = spr.shape[:2]
        sx, sy = self.project(x, y - lift, cx, cy, z)
        scale = S * z * 1.02
        nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
        img = cv2.resize(spr[:, :, :3], (nw, nh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        alpha = cv2.resize(spr[:, :, 3], (nw, nh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        alpha = np.clip((alpha - 0.06) / 0.90, 0, 1)[..., None]

        # contact shadow on the board
        bx, by = self.project(x, y, cx, cy, z)
        sh_w = nw * (0.95 - 0.004 * lift)
        sh_h = max(4.0, sh_w * 0.20)
        self._soft_ellipse(frame, bx, by - 2, sh_w * 0.55, sh_h * 0.55,
                           0.42 * shadow_a * (1.0 - lift / 160.0),
                           np.array([0.16, 0.10, 0.10]))

        # speed glow instead of ghosting: a warm halo that only appears mid-flight
        if speed > 0.05:
            self._add_glow(frame, s.spark, sx, sy - nh * 0.45, nw * 0.9,
                           np.array([1.0, 0.88, 0.62]) * 0.22 * speed)
        self._blit(frame, img, alpha, sx, sy, nw, nh)

    def _draw_hero_glow(self, frame, t, cx, cy, z):
        """Golden 'charge' running from the fingertip down the piece before the move."""
        if not (13.35 <= t <= 15.55):
            return
        s = self.s
        tip = s.meta["hero_tip"]
        ex, ey = self._map_point(tip, "lhand", cx, cy, z)
        k = smooth((t - 13.35) / 1.0) * (1.0 - smooth((t - 14.9) / 0.65))
        if k <= 0.01:
            return
        flick = 0.75 + 0.25 * math.sin(t * 17.0)
        self._add_glow(frame, s.spark, ex, ey, 30 * S * z * 2.2,
                       np.array([1.0, 0.92, 0.66]) * 0.34 * k * flick)
        # pulses travelling down over the piece
        for i in range(3):
            ph = (t * 1.35 + i * 0.33) % 1.0
            py = ey + ph * 150 * S * z
            a = (1.0 - ph) * k * 0.16
            self._add_glow(frame, s.spark, ex + 2 * math.sin(ph * 9 + i), py,
                           26 * S * z, np.array([1.0, 0.88, 0.60]) * a)
        # a few sparks drifting up
        for i in range(7):
            ph = (t * 0.55 + i * 0.143) % 1.0
            sx = ex + (i - 3) * 6.5 * S * z + 5 * math.sin(t * 1.7 + i)
            sy = ey + 120 * S * z - ph * 190 * S * z
            self._add_glow(frame, s.spark, sx, sy, 7 * S * z * 3,
                           np.array([1.0, 0.90, 0.68]) * 0.28 * k * (1 - ph))

    def _landing_ripple(self, frame, u, cx, cy, z):
        s = self.s
        ex, ey = self.project(ROOK_TO[0], ROOK_TO[1], cx, cy, z)
        r = (10 + 150 * u) * S * z
        fade = (1 - u) ** 2
        tmp = np.zeros((H, W), np.float32)
        cv2.ellipse(tmp, (int(ex), int(ey - 2)), (int(r), int(r * 0.26)), 0, 0, 360,
                    float(fade * 0.30), 3, cv2.LINE_AA)
        tmp = cv2.GaussianBlur(tmp, (0, 0), 2.0)
        frame += tmp[..., None] * np.array([1.0, 0.88, 0.62], np.float32)
        # dust puff
        p = s.puff
        for i in range(len(p["ang"])):
            life = u - p["r"][i] * 0.22
            if life <= 0 or life > 0.9:
                continue
            dist = p["spd"][i] * life ** 0.6 * S * z * 0.9
            px = ex + math.cos(p["ang"][i]) * dist
            py = ey - 2 + math.sin(p["ang"][i]) * dist * 0.42 - 8 * life
            a = (1 - life / 0.9) ** 2 * 0.32
            self._add_glow(frame, s.spark, px, py, 5 + 12 * p["sz"][i] * S * z,
                           np.array([1.0, 0.92, 0.78]) * a)

    def _draw_droplets(self, frame, t, cx, cy, z, map_x, map_y):
        """A few beads detach from the goo, fall, and pop a tiny highlight."""
        s = self.s
        d = s.drops
        for i in range(len(d["x"])):
            period = d["per"][i]
            u = ((t - d["t0"][i]) % period) / period if t >= d["t0"][i] else -1
            if u < 0 or u > 0.86:
                continue
            fall = 0.5 * 520.0 * u * u + 12.0 * u
            sx, sy = d["x"][i], d["y"][i] + fall
            px, py = self.project(sx, sy, cx, cy, z)
            if not (-40 < px < W + 40 and -40 < py < H + 40):
                continue
            r = max(1.5, d["r"][i] * S * z * (1.0 - 0.25 * u))
            a = (1.0 - u / 0.86) ** 0.7
            self._add_glow(frame, s.spark, px, py + r * 0.6, r * 4.2,
                           np.array([0.45, 0.70, 0.22]) * 0.30 * a)
            self._add_glow(frame, s.spark, px - r * 0.5, py - r * 0.5, r * 2.6,
                           np.array([1.0, 1.0, 0.85]) * 0.55 * a)
            # impact splash
            if u > 0.72:
                k = (u - 0.72) / 0.14
                self._add_glow(frame, s.spark, px, py + r, r * (3.0 + 10 * k),
                               np.array([0.6, 0.95, 0.35]) * 0.35 * (1 - k))

    def _draw_dust(self, frame, t, cx, cy, z, par_x, par_y, wake):
        s = self.s
        d = s.dust
        n = len(d["x"])
        ys = d["y"] - d["vy"] * t
        span = 2350 - 380
        ys = 380 + np.mod(ys - 380, span)
        xs = d["x"] + d["vx"] * t + 12 * np.sin(t * 0.3 + d["ph"])
        depth_off = 0.5 - d["z"]
        xs = xs + par_x * depth_off * 1.4
        ys = ys + par_y * depth_off * 1.4
        px = (xs - cx) * S * z + W / 2
        py = (ys - cy) * S * z + H / 2
        vis = (px > -10) & (px < W + 10) & (py > -10) & (py < H + 10)
        if not np.any(vis):
            return
        layer = np.zeros((H, W), np.float32)
        tw = 0.35 + 0.65 * (0.5 + 0.5 * np.sin(t * 1.7 + d["ph"] * 2.3))
        for i in np.nonzero(vis)[0]:
            r = max(1, int(d["sz"][i] * S * z * (0.7 + 0.9 * d["z"][i]) * 1.9))
            a = 0.24 * tw[i] * d["z"][i] * wake
            cv2.circle(layer, (int(px[i]), int(py[i])), r, float(a), -1, cv2.LINE_AA)
        layer = cv2.GaussianBlur(layer, (0, 0), 2.2)
        frame += layer[..., None] * np.array([1.0, 0.94, 0.80], np.float32)

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _add_glow(frame, sprite, cx, cy, radius, color):
        n = sprite.shape[0]
        x0, y0 = int(cx - radius), int(cy - radius)
        x1, y1 = x0 + 2 * int(radius), y0 + 2 * int(radius)
        if x1 < 0 or y1 < 0 or x0 > frame.shape[1] or y0 > frame.shape[0]:
            return
        cx0, cy0 = max(0, x0), max(0, y0)
        cx1, cy1 = min(frame.shape[1], x1), min(frame.shape[0], y1)
        sx0 = int((cx0 - x0) / max(1e-6, (x1 - x0)) * n)
        sy0 = int((cy0 - y0) / max(1e-6, (y1 - y0)) * n)
        sx1 = max(sx0 + 1, int((cx1 - x0) / max(1e-6, (x1 - x0)) * n))
        sy1 = max(sy0 + 1, int((cy1 - y0) / max(1e-6, (y1 - y0)) * n))
        g = cv2.resize(sprite[sy0:sy1, sx0:sx1], (cx1 - cx0, cy1 - cy0), interpolation=cv2.INTER_LINEAR)
        frame[cy0:cy1, cx0:cx1] += g[..., None] * color

    @staticmethod
    def _soft_ellipse(frame, cx, cy, rx, ry, alpha, color):
        x0, y0 = int(cx - rx * 2.2), int(cy - ry * 2.6)
        x1, y1 = int(cx + rx * 2.2), int(cy + ry * 2.6)
        x0, y0 = max(0, x0), max(0, y0)
        x1 = min(frame.shape[1] - 1, x1)
        y1 = min(frame.shape[0] - 1, y1)
        if x1 <= x0 or y1 <= y0:
            return
        tmp = np.zeros((y1 - y0, x1 - x0), np.float32)
        cv2.ellipse(tmp, (int(cx - x0), int(cy - y0)), (max(1, int(rx)), max(1, int(ry))),
                    0, 0, 360, 1.0, -1, cv2.LINE_AA)
        tmp = cv2.GaussianBlur(tmp, (0, 0), max(1.0, min(rx, ry) * 0.7))
        sh = tmp[..., None]
        frame[y0:y1, x0:x1] = frame[y0:y1, x0:x1] * (1 - sh * alpha) + sh * alpha * color

    @staticmethod
    def _blit(frame, img, alpha, cx, cy, nw, nh):
        x0 = int(round(cx - nw / 2))
        y0 = int(round(cy - nh))
        x1, y1 = x0 + nw, y0 + nh
        cx0, cy0 = max(0, x0), max(0, y0)
        cx1, cy1 = min(frame.shape[1], x1), min(frame.shape[0], y1)
        if cx1 <= cx0 or cy1 <= cy0:
            return
        sx0, sy0 = cx0 - x0, cy0 - y0
        sx1, sy1 = sx0 + (cx1 - cx0), sy0 + (cy1 - cy0)
        a = alpha[sy0:sy1, sx0:sx1]
        frame[cy0:cy1, cx0:cx1] = frame[cy0:cy1, cx0:cx1] * (1 - a) + img[sy0:sy1, sx0:sx1] * a

    def _grade(self, frame, t):
        s = self.s
        # gentle S-curve + warm highlights / cool shadows
        f = np.clip(frame, 0, 1.6)
        f = f + 0.08 * (f ** 2) * (1.4 - f)          # contrast
        lum = 0.2126 * f[:, :, 2] + 0.7152 * f[:, :, 1] + 0.0722 * f[:, :, 0]
        f[:, :, 2] += 0.035 * lum                     # warm red
        f[:, :, 0] += 0.030 * (1 - lum)               # cool blue shadows
        # bloom
        small = cv2.resize(f, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        bright = np.clip(small - 0.72, 0, 1.2)
        bloom = cv2.GaussianBlur(bright, (0, 0), 7)
        bloom = cv2.resize(bloom, (W, H), interpolation=cv2.INTER_LINEAR)
        f += bloom * 0.30
        f *= s.vignette[..., None]
        return np.clip(f, 0, 1.6)

    def _draw_title(self, frame, t):
        if t < TITLE_IN - 0.2:
            return
        a = smooth((t - TITLE_IN) / 1.8)
        if a <= 0:
            return
        s = self.s
        th = s.title_rgb.shape[0]
        y0 = int(H * 0.70)
        y0 = min(y0, H - th - 1)
        # soft elliptical scrim so the type reads over the pale chess pieces
        # without a visible horizontal band
        if not hasattr(self, "_scrim"):
            uu = (np.arange(W, dtype=np.float32)[None, :] - W * 0.5) / (W * 0.72)
            vv = (np.arange(H, dtype=np.float32)[:, None] - H * 0.775) / (H * 0.30)
            rr = np.sqrt(uu**2 + vv**2)
            self._scrim = (np.clip(1.15 - rr, 0, 1) ** 1.25).astype(np.float32)
        frame *= (1.0 - 0.52 * a * self._scrim)[..., None]
        al = s.title_alpha * a
        region = frame[y0 : y0 + th, :, :]
        frame[y0 : y0 + th, :, :] = region * (1 - al) + s.title_rgb * al


# ------------------------------------------------------------------ encode
def ffmpeg_path():
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # pragma: no cover
        return "ffmpeg"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", type=str, default="", help="comma separated times -> PNG stills")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=DURATION)
    ap.add_argument("--out", type=str, default=os.path.join(OUT, "living_painting.mp4"))
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--width", type=int, default=0)
    ap.add_argument("--height", type=int, default=0)
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    if args.width and args.height:
        configure(args.width, args.height)
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
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    cmd = [
        ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = args.start
    for i in range(frames):
        t = t0 + i / FPS
        frame = r.render(t)
        proc.stdin.write(frame.tobytes())
        if i % 30 == 0:
            print(f"\rframe {i}/{frames}  t={t:5.1f}s", end="", flush=True)
    proc.stdin.close()
    proc.wait()
    print("\nwrote", args.out)


if __name__ == "__main__":
    main()
