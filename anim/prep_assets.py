"""Build every layer the 2.5D compositor needs from the single painting.

Outputs (all in ``anim/assets``):
  plate.png      painting with the moving rook removed (inpainted)
  rook.png       RGBA sprite of the rook that makes the move
  depth.png      8-bit depth proxy (0 = far .. 255 = near)
  masks.npz      float masks: crystals, window light, robot body, hero piece, foliage
  meta.json      coordinates the renderer needs (eyes, rook anchor, beam origin ...)

The masks are hand-authored polygons because the picture is a painting: there is
no clean semantic segmentation available, but the geometry is fixed, so a small
set of shapes plus Gaussian feathering gives artefact-free parallax.
"""
from __future__ import annotations

import json
import os

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
SRC = os.path.join(ASSETS, "source.jpg")

# ---------------------------------------------------------------- helpers


def blank(h, w):
    return np.zeros((h, w), np.float32)


def poly(mask, pts, value):
    cv2.fillPoly(mask, [np.array(pts, np.int32)], float(value), lineType=cv2.LINE_AA)


def ellipse(mask, center, axes, value, angle=0):
    cv2.ellipse(mask, center, axes, angle, 0, 360, float(value), -1, lineType=cv2.LINE_AA)


def soft(mask, sigma):
    out = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), sigma)
    return out


def grabcut_piece(img, box, pad=6):
    x, y, w, h = box
    X0, Y0, X1, Y1 = x - pad, y - pad, x + w + pad, y + h + pad
    sub = img[Y0:Y1, X0:X1].copy()
    hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
    hh = hsv[:, :, 0].astype(np.int32)
    ss = hsv[:, :, 1].astype(np.float32) / 255
    vv = hsv[:, :, 2].astype(np.float32) / 255
    warm = ((hh >= 7) & (hh <= 48) & (ss > 0.12) & (vv > 0.30)).astype(np.uint8)
    m = np.full(sub.shape[:2], cv2.GC_BGD, np.uint8)
    inner = np.zeros_like(m)
    inner[pad : pad + h, pad : pad + w] = 1
    m[(warm > 0) & (inner > 0)] = cv2.GC_PR_FGD
    m[(cv2.erode(warm, np.ones((5, 5), np.uint8)) > 0) & (inner > 0)] = cv2.GC_FGD
    cv2.grabCut(
        sub, m, None, np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64), 8, cv2.GC_INIT_WITH_MASK
    )
    a = np.where((m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(a, 8)
    if n > 1:
        a = (lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    a = cv2.morphologyEx(a, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    alpha = cv2.GaussianBlur(a.astype(np.float32), (3, 3), 0.6)
    return sub, np.clip(alpha, 0, 1), (X0, Y0)


# ---------------------------------------------------------------- main


def main():
    img = cv2.imread(SRC)
    H, W = img.shape[:2]
    print("source", W, H)

    # ---------------------------------------------------------- rook sprite
    rook_box = (987, 1886, 57, 108)  # x,y,w,h in source pixels
    sub, alpha, (RX, RY) = grabcut_piece(img, rook_box, pad=8)
    rgba = cv2.cvtColor(sub, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = (alpha * 255).astype(np.uint8)
    cv2.imwrite(os.path.join(ASSETS, "rook.png"), rgba)
    ys, xs = np.nonzero(alpha > 0.5)
    rook_anchor = [float(RX + xs.mean()), float(RY + ys.max())]  # bottom-center contact point
    rook_size = [int(rgba.shape[1]), int(rgba.shape[0])]
    print("rook", rook_size, "anchor", rook_anchor)

    # ---------------------------------------------------------- plate (rook removed)
    plate = img.copy()
    hole = np.zeros((H, W), np.uint8)
    hole[RY : RY + rgba.shape[0], RX : RX + rgba.shape[1]] = (alpha > 0.35).astype(np.uint8) * 255
    hole = cv2.dilate(hole, np.ones((7, 7), np.uint8))
    # horizontal column fill: the background behind the rook is a nearly flat
    # red table + pale board edge, so per-row interpolation reads far better
    # than the smeary Telea inpainting.
    fill = plate.copy()
    ys, xs = np.nonzero(hole)
    y0h, y1h = int(ys.min()), int(ys.max())
    for yy in range(y0h, y1h + 1):
        row = np.nonzero(hole[yy])[0]
        if len(row) == 0:
            continue
        xl = max(0, row[0] - 3)
        xr = min(W - 1, row[-1] + 3)
        cL = plate[yy, max(0, xl - 1)].astype(np.float32)
        cR = plate[yy, min(W - 1, xr + 1)].astype(np.float32)
        n = xr - xl + 1
        k = np.linspace(0, 1, n, dtype=np.float32)[:, None]
        fill[yy, xl : xr + 1] = (cL * (1 - k) + cR * k).astype(np.uint8)
    fill = cv2.medianBlur(fill, 5)
    m3 = cv2.GaussianBlur(hole.astype(np.float32) / 255.0, (0, 0), 3)[..., None]
    plate = (fill.astype(np.float32) * m3 + plate.astype(np.float32) * (1 - m3)).astype(np.uint8)
    cv2.imwrite(os.path.join(ASSETS, "plate.png"), plate)

    # ---------------------------------------------------------- eyes
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    V = hsv[:, :, 2].astype(np.float32) / 255
    S = hsv[:, :, 1].astype(np.float32) / 255
    HH = hsv[:, :, 0].astype(np.int32)
    eye_roi = np.zeros((H, W), np.uint8)
    eye_roi[1000:1130, 820:1010] = 1
    m = ((V > 0.78) & (S < 0.22) & (eye_roi > 0)).astype(np.uint8)
    n, lab, st, ce = cv2.connectedComponentsWithStats(m, 8)
    eyes = []
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] < 250:
            continue
        eyes.append(
            dict(
                x=float(ce[i][0]),
                y=float(ce[i][1]),
                r=float(max(st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]) / 2),
            )
        )
    eyes.sort(key=lambda e: e["x"])
    print("eyes", eyes)

    # ---------------------------------------------------------- crystals
    crystal = blank(H, W)
    shards = [
        # left cluster (behind the left shoulder)
        [(640, 1290), (620, 1180), (652, 1050), (700, 968), (724, 1010), (716, 1180), (700, 1292)],
        [(700, 1295), (706, 1120), (742, 985), (790, 1040), (796, 1180), (760, 1300)],
        [(772, 1290), (786, 1120), (812, 1060), (842, 1140), (830, 1280)],
        # right cluster (the big faceted crystals)
        [(1245, 1290), (1226, 1120), (1252, 952), (1300, 796), (1362, 908), (1338, 1080), (1310, 1295)],
        [(1188, 1295), (1190, 1150), (1230, 1000), (1270, 1040), (1268, 1200), (1240, 1300)],
        [(1330, 1290), (1348, 1080), (1392, 936), (1448, 1010), (1436, 1180), (1392, 1300)],
        [(1420, 1290), (1452, 1090), (1494, 1030), (1500, 1180), (1470, 1295)],
        [(1150, 1300), (1152, 1190), (1186, 1120), (1206, 1200), (1200, 1300)],
    ]
    for i, sh in enumerate(shards):
        poly(crystal, sh, 1.0)
    # innermost highlight follows the green rim light of the painting
    glow = ((HH >= 25) & (HH <= 60) & (S > 0.15) & (S < 0.65) & (V > 0.62)).astype(np.float32)
    glow = cv2.GaussianBlur(glow, (0, 0), 3)
    crystal = np.clip(crystal * (0.55 + 0.75 * glow), 0, 1)
    crystal = np.clip(cv2.GaussianBlur(crystal, (0, 0), 2.2), 0, 1)
    print("crystal px", int((crystal > 0.5).sum()))

    # ---------------------------------------------------------- window / light
    win = ((V > 0.80) & (S < 0.20)).astype(np.uint8)
    win[560:, :] = 0
    n2, l2, s2, _ = cv2.connectedComponentsWithStats(win, 8)
    wi = 1 + int(np.argmax(s2[1:, cv2.CC_STAT_AREA]))
    window = (l2 == wi).astype(np.float32)
    window = cv2.GaussianBlur(window, (0, 0), 6)
    wx, wy, ww, wh = s2[wi, 0], s2[wi, 1], s2[wi, 2], s2[wi, 3]
    print("window", wx, wy, ww, wh)

    # volumetric shafts: soft wedges from the window down onto the table
    beams = blank(H, W)
    top_y = wy + wh * 0.55
    for (bx0, bx1, tx0, tx1, amp) in [
        (wx + 0.08 * ww, wx + 0.42 * ww, -120, 620, 0.75),
        (wx + 0.50 * ww, wx + 0.92 * ww, 760, 1500, 0.85),
        (wx + 0.25 * ww, wx + 0.60 * ww, 300, 1050, 0.55),
    ]:
        pts = [(bx0, top_y), (bx1, top_y), (tx1, 2150), (tx0, 2150)]
        poly(beams, pts, amp)
    beams = cv2.GaussianBlur(beams, (0, 0), 55)
    # fade the shafts in with distance from the window
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    beams *= np.clip(1.15 - 0.55 * yy, 0, 1)
    beams *= np.clip((yy - 0.02) * 6, 0, 1)

    # ---------------------------------------------------------- robot body / hero piece
    body = blank(H, W)
    ellipse(body, (925, 1065), (170, 215), 1.0)  # head
    ellipse(body, (985, 1480), (330, 330), 1.0)  # chest
    ellipse(body, (640, 1620), (150, 300), 1.0, angle=18)  # left arm
    ellipse(body, (1245, 1615), (175, 300), 1.0, angle=-12)  # right arm
    ellipse(body, (1035, 1745), (280, 190), 1.0)  # planted hand / forearm
    body = np.clip(cv2.GaussianBlur(body, (0, 0), 26) * 1.4, 0, 1)

    hero = blank(H, W)
    poly(hero, [(752, 1975), (752, 1810), (770, 1775), (808, 1770), (830, 1800), (832, 1990)], 1.0)
    hero = np.clip(cv2.GaussianBlur(hero, (0, 0), 9) * 1.6, 0, 1)
    hero_tip = [790.0, 1778.0]

    # foreground foliage (parallax layer)
    fg = blank(H, W)
    poly(fg, [(0, 380), (210, 480), (350, 830), (300, 1250), (340, 1700), (250, 2100), (0, 2250)], 1.0)
    poly(fg, [(1706, 300), (1480, 470), (1390, 880), (1440, 1360), (1500, 1830), (1706, 1980)], 1.0)
    poly(fg, [(0, 2180), (380, 2110), (760, 2210), (1150, 2150), (1706, 2100), (1706, 2560), (0, 2560)], 1.0)
    fg = np.clip(cv2.GaussianBlur(fg, (0, 0), 22) * 1.5, 0, 1)

    # ---------------------------------------------------------- articulation rig
    # Weight masks for the mesh-warp rig. Each part gets a feathered mask and a
    # pivot; the renderer rotates the part about its pivot and blends the
    # displacement by weight, so neighbouring parts stretch instead of tearing.
    def capsule(p0, p1, r0, r1=None, blur=18):
        m = blank(H, W)
        n = 40
        for i in range(n + 1):
            k = i / n
            x = p0[0] + (p1[0] - p0[0]) * k
            y = p0[1] + (p1[1] - p0[1]) * k
            r = r0 + ((r0 if r1 is None else r1) - r0) * k
            ellipse(m, (int(x), int(y)), (int(r), int(r)), 1.0)
        m = cv2.GaussianBlur(m, (0, 0), blur)
        return np.clip(m * 1.6, 0, 1)

    def blob(sp, blur=22):
        m = blank(H, W)
        poly(m, sp, 1.0)
        m = cv2.GaussianBlur(m, (0, 0), blur)
        return np.clip(m * 1.7, 0, 1)

    w_head = blob([(792, 1238), (778, 1150), (800, 1005), (828, 938), (882, 888),
                   (962, 878), (1032, 903), (1066, 980), (1072, 1120), (1048, 1218),
                   (998, 1272), (930, 1292), (858, 1268)], blur=16)
    w_torso = np.clip(cv2.GaussianBlur(
        (lambda m: (ellipse(m, (985, 1520), (330, 300), 1.0), m)[1])(blank(H, W)), (0, 0), 60) * 1.5, 0, 1)
    w_larm = capsule((706, 1332), (486, 1512), 74, 64)
    w_lfore = capsule((486, 1512), (462, 1795), 62, 54)
    w_lhand = blob([(352, 1830), (372, 1800), (430, 1782), (500, 1798), (530, 1848),
                    (520, 1900), (430, 1912), (368, 1888)], blur=16)
    w_rarm = capsule((1332, 1716), (1052, 1614), 86, 70)
    w_rhand = blob([(770, 1780), (800, 1700), (860, 1620), (960, 1560), (1060, 1566),
                    (1100, 1620), (1070, 1700), (980, 1760), (900, 1812), (830, 1812)], blur=16)

    # normalise: overlapping weights must not displace a pixel twice
    stack = np.stack([w_head, w_torso, w_larm, w_lfore, w_lhand, w_rarm, w_rhand])
    tot = np.maximum(1.0, stack.sum(0, keepdims=True))
    stack = np.clip(stack / tot, 0, 1)

    # ---------------------------------------------------------- slime
    # 1) the yellow-green goo already painted on the robot -> gentle liquid drift
    slime = ((HH >= 25) & (HH <= 75) & (S > 0.34) & (S < 1.0) & (V > 0.28) & (V < 0.95)).astype(np.float32)
    slime[1850:, :] = 0
    region = blank(H, W)
    ellipse(region, (1010, 1560), (520, 430), 1.0)
    slime *= region
    slime = cv2.GaussianBlur(slime, (0, 0), 3)
    slime = np.clip(slime * 1.4, 0, 1)
    print("painted slime px", int((slime > 0.5).sum()))

    # 2) procedural drips: beads hanging off the chest rim, the shoulder and the
    #    forearm, each with a head, a thin neck and a running tail
    dr = blank(H, W)
    drips = [
        (1068, 1442, 15, 120), (1102, 1470, 11, 86), (1002, 1402, 9, 70),
        (1206, 1512, 13, 104), (930, 1378, 8, 58), (1150, 1608, 10, 78),
        (686, 1524, 9, 66), (742, 1610, 7, 48), (1352, 1660, 11, 84),
        (1030, 1652, 7, 52), (806, 1452, 7, 44),
    ]
    for (cx_, cy_, r_, length) in drips:
        poly(dr, [(cx_ - r_ * 0.62, cy_), (cx_ - r_ * 0.34, cy_ + length * 0.55),
                  (cx_ - r_ * 0.20, cy_ + length), (cx_ + r_ * 0.20, cy_ + length),
                  (cx_ + r_ * 0.34, cy_ + length * 0.55), (cx_ + r_ * 0.62, cy_)], 0.85)
        ellipse(dr, (cx_, cy_), (int(r_), int(r_ * 1.15)), 1.0)
        ellipse(dr, (cx_, cy_ + length), (max(2, int(r_ * 0.55)), max(2, int(r_ * 0.55))), 1.0)
    dr = cv2.GaussianBlur(dr, (0, 0), 1.4)
    # keep drips only where the painting has a surface to run down
    surf = ((V < 0.86) & (HH > 90) | (HH < 30)).astype(np.float32)
    surf = cv2.GaussianBlur(surf, (0, 0), 3)
    dr *= np.clip(surf, 0, 1)
    droop = np.maximum(slime, dr)
    print("drips px", int((dr > 0.5).sum()))

    # ---------------------------------------------------------- depth
    depth = np.full((H, W), 0.18, np.float32)
    # distant architecture
    poly(depth, [(0, 0), (600, 0), (560, 900), (0, 1100)], 0.30)
    poly(depth, [(1500, 0), (1706, 0), (1706, 900), (1480, 800)], 0.30)
    # robot sits in the middle plane
    depth = np.maximum(depth, body * 0.58)
    depth = np.maximum(depth, crystal * 0.56)
    # table / board closer
    poly(depth, [(0, 1790), (1200, 1860), (1430, 1990), (1330, 2240), (0, 2300)], 0.76)
    # window is the backdrop
    depth = np.minimum(depth + 0.0, 1.0)
    depth[0:560, :] = np.where(window[0:560, :] > 0.1, depth[0:560, :] * 0.6, depth[0:560, :] * 0.85)[0:560, :]
    # foreground foliage on top of everything
    depth = np.maximum(depth, fg * 1.0)
    depth = cv2.GaussianBlur(depth, (0, 0), 26)
    depth = np.clip((depth - 0.05) / 0.95, 0, 1)
    depth8 = (depth * 255).astype(np.uint8)
    cv2.imwrite(os.path.join(ASSETS, "depth.png"), depth8)

    np.savez_compressed(
        os.path.join(ASSETS, "masks.npz"),
        crystal=crystal.astype(np.float16),
        window=window.astype(np.float16),
        beams=beams.astype(np.float16),
        body=body.astype(np.float16),
        hero=hero.astype(np.float16),
        foliage=fg.astype(np.float16),
        parts=(stack * 255).astype(np.uint8),
        slime=(droop * 255).astype(np.uint8),
        drips=(dr * 255).astype(np.uint8),
    )

    meta = dict(
        width=W,
        height=H,
        eyes=eyes,
        rook=dict(anchor=rook_anchor, size=rook_size, sprite_origin=[RX, RY], box=list(rook_box)),
        window=dict(x=int(wx), y=int(wy), w=int(ww), h=int(wh)),
        hero_tip=hero_tip,
        focal=dict(head=[925, 1080], torso=[985, 1500]),
    )
    json.dump(meta, open(os.path.join(ASSETS, "meta.json"), "w"), indent=1)
    print("meta written")

    # quick visual check of the masks
    vis = img.copy()
    overlay = vis.copy()
    overlay[crystal > 0.4] = (120, 255, 120)
    overlay[beams > 0.3] = (255, 210, 160)
    vis = cv2.addWeighted(overlay, 0.35, vis, 0.65, 0)
    dm = cv2.applyColorMap(depth8, cv2.COLORMAP_INFERNO)
    dep_vis = cv2.addWeighted(img, 0.45, dm, 0.55, 0)
    sheet = np.hstack([cv2.resize(vis, (W // 3, H // 3)), cv2.resize(dep_vis, (W // 3, H // 3))])
    cv2.imwrite(os.path.join(HERE, "tmp", "masks_check.png"), sheet)

    rig_vis = img.copy().astype(np.float32)
    colours = [(255, 90, 90), (90, 200, 255), (120, 255, 120), (255, 200, 90),
               (200, 120, 255), (90, 255, 220), (255, 120, 200)]
    for i, c in enumerate(colours):
        m = (stack[i] * 0.55)[..., None]
        rig_vis = rig_vis * (1 - m * 0.55) + np.array(c, np.float32) * m * 0.55
    rig_vis = np.clip(rig_vis, 0, 255).astype(np.uint8)
    cv2.imwrite(os.path.join(HERE, "tmp", "rig_check.png"),
                cv2.resize(rig_vis, (W // 2, H // 2), interpolation=cv2.INTER_AREA))
    cv2.imwrite(os.path.join(HERE, "tmp", "slime_check.png"),
                cv2.resize((droop * 255).astype(np.uint8), (W // 2, H // 2)))
    print("check image -> anim/tmp/masks_check.png")


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "tmp"), exist_ok=True)
    main()
