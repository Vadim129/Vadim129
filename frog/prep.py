"""Build the dancing-frog assets from the single 640x640 portrait.

Outputs in ``frog/assets``:
  frog.png      RGBA cut-out of the whole character (hat included)
  eyes.json     iris centres / radii / palettes for the eyeball compositor
  irisL/R.png   the painted iris, cut out and normalised
  sky.png       procedural club backdrop (gradient + bokeh + floor)
  masks.npz     part weight maps for the mesh-warp dance rig

The frog is cropped at the thighs, so the stage is built around that: a
"DJ desk" and light beams come in the renderer, not here.
"""
from __future__ import annotations

import json
import os

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
SRC = os.path.join(ASSETS, "frog.jpg")


def blank(h, w):
    return np.zeros((h, w), np.float32)


def poly(m, pts, v=1.0):
    cv2.fillPoly(m, [np.array(pts, np.int32)], float(v), lineType=cv2.LINE_AA)


def ell(m, c, ax, v=1.0, ang=0):
    cv2.ellipse(m, c, ax, ang, 0, 360, float(v), -1, lineType=cv2.LINE_AA)


def soft(m, s):
    return cv2.GaussianBlur(m.astype(np.float32), (0, 0), s)


# ---------------------------------------------------------------- main
img = cv2.imread(SRC)
H, W = img.shape[:2]
print("source", W, H)

# remove thin white studio lines trapped inside the character (e.g. the sliver
# of background between the arms and the shirt): a 5x5 median kills 1-2 px
# strips but leaves wide bright areas such as the eye whites untouched
med = cv2.medianBlur(img, 5)
minc, maxc = img.min(2), img.max(2)
whiteish = ((minc > 185) & ((maxc - minc) < 34)).astype(np.uint8)
thick = cv2.erode(whiteish, np.ones((5, 5), np.uint8)) > 0
thin = (whiteish > 0) & (~thick)
img = np.where(thin[..., None], med, img)
print("cleaned thin light lines:", int(thin.sum()))

# ---------------------------------------------------------------- cut-out
f = img.astype(np.float32)
dist = np.sqrt(((255.0 - f) ** 2).sum(2))
sat = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[:, :, 1].astype(np.float32)
raw = ((dist > 26) | (sat > 26)).astype(np.uint8)
n, lab, st, _ = cv2.connectedComponentsWithStats(raw, 8)
m = (lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
ff = m.copy()
mask2 = np.zeros((H + 2, W + 2), np.uint8)
cv2.floodFill(ff, mask2, (0, 0), 1)
m = np.clip(m + (ff == 0).astype(np.uint8), 0, 1)
# the fill above also pulls in *enclosed* background (the white gap between the
# shirt hem and the cropped thighs, and the sliver between arms and body) —
# drop large pure-white blobs that are not part of the eyes
whitebg = ((img.min(2) > 195) & ((img.max(2) - img.min(2)) < 30)).astype(np.uint8)
for ex, ey, er in ((242.4, 215.1, 58), (396.5, 215.2, 58)):
    cv2.circle(whitebg, (int(ex), int(ey)), int(er), 0, -1)
n3, lab3, st3, _ = cv2.connectedComponentsWithStats(whitebg, 8)
dropped = 0
for i in range(1, n3):
    if st3[i, cv2.CC_STAT_AREA] >= 120:
        m[lab3 == i] = 0
        dropped += 1
print("dropped enclosed background blobs:", dropped)
# choke the matte one pixel and de-fringe: the outside is filled with colour
# propagated from the frog, so soft edge pixels no longer carry the white studio
# background (which shows badly against the dark stage)
m_core = cv2.erode(m, np.ones((3, 3), np.uint8), iterations=2)
alpha = cv2.GaussianBlur(m_core.astype(np.float32), (0, 0), 0.6)
filled = cv2.inpaint(img, (1 - m_core) * 255, 3, cv2.INPAINT_TELEA)
filled = cv2.GaussianBlur(filled, (0, 0), 0.6)
rgba = cv2.cvtColor(filled, cv2.COLOR_BGR2BGRA)
rgba[:, :, 3] = (alpha * 255).astype(np.uint8)
cv2.imwrite(os.path.join(ASSETS, "frog.png"), rgba)
print("frog.png", rgba.shape)

# ---------------------------------------------------------------- eyes
# measured on the source: iris centres, sclera radii, iris radius, gaze offset
# detected from the pupils (dark blobs): (242.4, 215.1) and (396.5, 215.2)
EYES = {
    "L": dict(cx=242.4, cy=215.1, sclera=54.0, iris=36.0),
    "R": dict(cx=396.5, cy=215.2, sclera=54.0, iris=36.0),
}
for k, e in EYES.items():
    x0 = int(e["cx"] - e["iris"] - 3)
    y0 = int(e["cy"] - e["iris"] - 3)
    s = int(2 * e["iris"] + 7)
    patch = img[y0 : y0 + s, x0 : x0 + s]
    # alpha: inside a circle
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    r = np.sqrt((xx - s / 2 + 0.5) ** 2 + (yy - s / 2 + 0.5) ** 2)
    a = np.clip((e["iris"] + 1.5 - r) / 2.0, 0, 1)
    out = cv2.cvtColor(patch, cv2.COLOR_BGR2BGRA)
    out[:, :, 3] = (a * 255).astype(np.uint8)
    cv2.imwrite(os.path.join(ASSETS, f"iris{k}.png"), out)
    e["iris_sprite"] = s
    e["iris_origin"] = [x0 + s / 2, y0 + s / 2]
    # sclera sprite: the eye disc with the iris/pupil knocked out, so the
    # renderer can re-aim the iris every frame
    r = e["sclera"]
    x0 = int(e["cx"] - r - 2); y0 = int(e["cy"] - r - 2); s_ = int(2 * r + 4)
    patch = img[y0 : y0 + s_, x0 : x0 + s_].copy()
    yy, xx = np.mgrid[0:s_, 0:s_].astype(np.float32)
    dist = np.sqrt((xx - s_ / 2 + 0.5) ** 2 + (yy - s_ / 2 + 0.5) ** 2)
    # soft disc alpha
    a = np.clip((r + 1.0 - dist) / 2.0, 0, 1)
    # knock out the iris and fill the hole with the *painted* sclera colour,
    # sampled from a ring just outside the iris (so the patch tone matches)
    iris_hole = np.clip((e["iris"] * 0.99 - dist) / 2.0, 0, 1)[..., None]
    # whiteness is the brightest cluster inside the eye disc
    flat = patch.reshape(-1, 3).astype(np.float32)
    vv = flat.mean(1)
    inside = (dist < e["sclera"]).reshape(-1)
    cand = flat[inside & (vv > np.percentile(vv[inside], 72))]
    white = np.median(cand, axis=0).astype(np.float32) * 1.03
    white = np.clip(white, 0, 255)
    base = patch.astype(np.float32)
    # slight spherical shading so the fill does not look flat
    shade = 1.0 - 0.10 * np.clip(dist / (e["sclera"] + 1e-3), 0, 1) ** 2
    patch = (base * (1 - iris_hole) + (white[None, None, :] * shade[..., None]) * iris_hole).astype(np.uint8)
    out = cv2.cvtColor(patch, cv2.COLOR_BGR2BGRA)
    out[:, :, 3] = (a * 255).astype(np.uint8)
    cv2.imwrite(os.path.join(ASSETS, f"sclera{k}.png"), out)

    # ---------------------------------------------------------- eyelid
    # Curtain model: the lid is the frog's own brow skin, pulled down over the
    # eyeball and compressed.  A small stack of levels is baked here so the
    # renderer only has to pick the nearest one.
    Rr = 48.6                     # eyeball radius that the lid has to cover
    px0, py0 = e["cx"] - x0, e["cy"] - y0       # eye centre in sprite px
    b, g_, r_ = img[:, :, 0].astype(np.int16), img[:, :, 1].astype(np.int16), img[:, :, 2].astype(np.int16)
    skin = ((g_ > b * 1.05) & (g_ > r_ * 0.98) & (g_ > 45)).astype(np.uint8)
    skin = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    flesh = cv2.inpaint(img, (1 - skin) * 255, 4, cv2.INPAINT_TELEA)
    flesh = cv2.GaussianBlur(flesh, (0, 0), 0.8)
    top = e["cy"] - Rr - 3.0                    # image y of the eyeball top
    levels, NLEV = [], 26
    yy2, xx2 = np.mgrid[0:s_, 0:s_].astype(np.float32)
    dd = np.maximum(0.0, yy2 - (py0 - Rr))
    for li in range(NLEV):
        cov = 0.06 + 0.94 * li / (NLEV - 1)
        span = max(3.0, 2 * Rr * cov)            # thickness of the visible band
        mapy = top - dd * (24.0 / span)          # squeeze a 24 px brow band
        mapx = xx2 + (x0 + 0.0)
        mapy = mapy + (y0 + 0.0)
        lv = cv2.remap(flesh, mapx.astype(np.float32), mapy.astype(np.float32),
                       cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        levels.append(lv)
    # the socket sits in the hat's shadow, so darken the pulled-down skin to
    # the tone of the flesh that actually borders the eyeball
    yy3, xx3 = np.mgrid[0:s_, 0:s_].astype(np.float32)
    ring = (np.sqrt((xx3 - px0) ** 2 + (yy3 - py0) ** 2) > Rr + 1) & \
           (np.sqrt((xx3 - px0) ** 2 + (yy3 - py0) ** 2) < Rr + 7)
    src_patch = img[y0:y0 + s_, x0:x0 + s_]
    ring_lum = float(np.median(src_patch[ring].mean(axis=1)))
    band_lum = float(np.median(np.stack(levels)[:, :, :, :].mean(axis=3)[:, ring].mean(axis=1)))
    scale = float(np.clip(ring_lum / max(band_lum, 1.0), 0.52, 0.97))
    levels = [np.clip(lv.astype(np.float32) * scale, 0, 255).astype(np.uint8) for lv in levels]
    EYES[k]["lid_shade"] = round(scale, 3)
    np.savez_compressed(os.path.join(ASSETS, f"lidstack{k}.npz"),
                        tex=np.stack(levels), cover=np.linspace(0.06, 1.0, NLEV))
    # flat fallback tone (also used for the crease tint)
    sel = img[y0:y0 + s_, x0:x0 + s_][(np.sqrt((xx2 - px0) ** 2 + (yy2 - py0) ** 2) > Rr + 1) &
                                      (np.sqrt((xx2 - px0) ** 2 + (yy2 - py0) ** 2) < Rr + 9)]
    g = (sel[:, 1] > sel[:, 2] * 1.06) & (sel[:, 1] > sel[:, 0] * 0.98) & (sel[:, 1] > 55)
    if g.sum() >= 25:
        sel = sel[g]
    EYES[k]["lid_col"] = [round(float(v), 1) for v in np.median(sel, axis=0)]
    EYES[k]["eye_r"] = round(float(Rr), 1)
    EYES[k]["centre_sprite"] = [round(float(px0), 2), round(float(py0), 2)]

    EYES[k]["sclera_sprite"] = s_
    EYES[k]["sclera_origin"] = [e["cx"], e["cy"]]

json.dump(EYES, open(os.path.join(ASSETS, "eyes.json"), "w"), indent=1)
print("eyes", EYES)

# ---------------------------------------------------------------- club backdrop
SW, SH = 1080, 1920
yy = np.linspace(0, 1, SH, dtype=np.float32)[:, None]
xx = np.linspace(0, 1, SW, dtype=np.float32)[None, :]
sky = np.zeros((SH, SW, 3), np.float32)
# deep indigo -> teal -> warm floor glow
top = np.array([34, 12, 26], np.float32)      # BGR
mid = np.array([70, 30, 52], np.float32)
bot = np.array([36, 22, 18], np.float32)
t = yy[..., 0]
sky += top[None, None, :] * ((1 - t) ** 1.6)[:, None, None]
sky += mid[None, None, :] * (np.clip(np.sin(np.pi * np.clip(t * 1.15, 0, 1)), 0, None) ** 1.2)[:, None, None]
sky += bot[None, None, :] * (t ** 2.2)[:, None, None]
# big soft light pools behind the character
for (cx_, cy_, rad, col, amp) in [
    (0.50, 0.30, 0.55, (120, 60, 200), 0.55),
    (0.18, 0.18, 0.30, (200, 120, 60), 0.30),
    (0.85, 0.22, 0.32, (170, 70, 150), 0.32),
    (0.5, 0.86, 0.45, (60, 120, 170), 0.30),
]:
    d = np.sqrt(((xx - cx_) * (SW / SH)) ** 2 + ((yy[..., 0] - cy_)[:, None]) ** 2)
    sky += (np.exp(-(d / rad) ** 2) * amp)[..., None] * np.array(col, np.float32)
# bokeh disc bank (drawn once, reused every frame) in a separate alpha layer
rng = np.random.default_rng(12)
bokeh = blank(SH, SW)
for _ in range(150):
    cx_ = rng.uniform(0, SW)
    cy_ = rng.uniform(0, SH * 0.8)
    r = rng.uniform(6, 46)
    a = rng.uniform(0.05, 0.30) * (1.0 - cy_ / SH * 0.6)
    cv2.circle(bokeh, (int(cx_), int(cy_)), int(r), float(a), -1, cv2.LINE_AA)
bokeh = cv2.GaussianBlur(bokeh, (0, 0), 5)
sky += bokeh[..., None] * np.array([180, 170, 200], np.float32)
sky = np.clip(sky, 0, 255).astype(np.uint8)
cv2.imwrite(os.path.join(ASSETS, "sky.png"), sky)

# ---------------------------------------------------------------- rig weights
def blob(pts, blur=16, gain=1.7):
    m = blank(H, W)
    poly(m, pts)
    return np.clip(soft(m, blur) * gain, 0, 1)


def capsule(p0, p1, r0, r1=None, blur=12):
    m = blank(H, W)
    for i in range(41):
        k = i / 40
        x = p0[0] + (p1[0] - p0[0]) * k
        y = p0[1] + (p1[1] - p0[1]) * k
        r = r0 + ((r0 if r1 is None else r1) - r0) * k
        ell(m, (int(x), int(y)), (int(r), int(r)))
    return np.clip(soft(m, blur) * 1.6, 0, 1)


# hat = wide brim + crown, avoiding the eyes
w_hat = blank(H, W)
poly(w_hat, [(20, 175), (60, 95), (140, 45), (230, 20), (340, 14), (450, 30), (530, 78),
             (590, 150), (612, 205), (470, 212), (330, 150), (200, 200), (60, 205)])
ell(w_hat, (330, 95), (150, 78))
w_hat[195:250, 190:470] *= 0.15          # keep the brim edge off the eyes
w_hat = np.clip(soft(w_hat, 10) * 1.5, 0, 1)

w_head = blob([(196, 168), (230, 120), (330, 108), (452, 130), (478, 190), (486, 290),
               (470, 372), (404, 420), (300, 436), (214, 404), (186, 320), (182, 240)], blur=14)
w_torso = blob([(214, 368), (296, 380), (432, 364), (486, 430), (498, 578), (470, 636),
                (206, 636), (178, 566), (188, 430)], blur=16)
w_larm = capsule((170, 470), (150, 620), 34, 30, blur=10)
w_rarm = capsule((474, 470), (494, 620), 34, 30, blur=10)

# jaw / lower face: drives the "singing" scale on the beat
w_jaw = blank(H, W)
poly(w_jaw, [(206, 268), (250, 262), (330, 268), (420, 262), (466, 276),
             (470, 372), (404, 420), (300, 436), (214, 404), (198, 330)])
w_jaw *= w_head
w_jaw = np.clip(soft(w_jaw, 9) * 1.5, 0, 1)
# the jaw takes over its region so the head rotation does not water it down
w_head = w_head * (1.0 - 0.9 * w_jaw)

stack = np.stack([w_hat, w_head, w_torso, w_larm, w_rarm, w_jaw])
tot = np.maximum(1.0, stack.sum(0, keepdims=True))
stack = np.clip(stack / tot, 0, 1)
np.savez_compressed(os.path.join(ASSETS, "masks.npz"), parts=(stack * 255).astype(np.uint8))

# preview
vis = img.copy()
cols = [(0, 0, 255), (0, 255, 255), (0, 255, 0), (255, 128, 0), (255, 0, 255), (128, 255, 255)]
for i, c in enumerate(cols):
    mm = (stack[i] * 0.45)[..., None]
    vis = (vis * (1 - mm * 0.6) + np.array(c, np.float32) * mm * 0.6).astype(np.uint8)
cv2.imwrite(os.path.join(HERE, "tmp", "rig.png"), vis)
print("rig masks ok", [int((stack[i] > 0.5).sum()) for i in range(stack.shape[0])])
