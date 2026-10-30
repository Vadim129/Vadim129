import numpy as np, subprocess, sys, os, math, random
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
W = H = 960
FPS = 24
DUR = 60.0
N = int(DUR * FPS)

SRC = np.load('work/src.npy', mmap_mode='r')
NS = SRC.shape[0]
ENV = np.load('work/env.npy').astype(np.float32)
ENV /= ENV.max() + 1e-9
RMS = np.load('work/rms.npy').astype(np.float32)

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'
FONTB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
_fc = {}
def font(sz, b=True):
    k = (sz, b)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FONTB if b else FONT, sz)
    return _fc[k]

# ---------- precomputed ----------
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
CX, CY = (W - 1) / 2.0, (H - 1) / 2.0
DXc, DYc = xx - CX, yy - CY
R = np.sqrt(DXc ** 2 + DYc ** 2) / math.hypot(CX, CY)
ANG = np.arctan2(DYc, DXc)
VIGN = (1.0 - 0.80 * np.clip(R - 0.30, 0, 1) ** 1.5)[..., None].astype(np.float32)
SCAN = (1.0 - 0.20 * (np.arange(H) % 3 == 0))[:, None, None].astype(np.float32)
SCAN4 = (1.0 - 0.30 * (np.arange(H) % 4 == 0))[:, None, None].astype(np.float32)

BAR = 4 * 60 / 90.0            # 2.6667 s
T0 = 1.2667                    # first downbeat inside the segment


def bars(n):
    return T0 + n * BAR


# ---------- source ----------
def sframe(t, rate=1.0, idx=None):
    if idx is None:
        idx = int(t * FPS * rate) % NS
    return SRC[idx % NS]


def aff(img, zoom=1.0, rot=0.0, sx=0.0, sy=0.0):
    """zoom >=1 crops in, rot degrees, sx/sy shift in px."""
    im = Image.fromarray(img)
    if rot == 0.0 and zoom == 1.0 and sx == 0 and sy == 0:
        return img
    a_ = math.radians(rot)
    c, s = math.cos(a_), math.sin(a_)
    a = c / zoom
    b = s / zoom
    d = -s / zoom
    e = c / zoom
    cc = CX - a * CX - b * CY + sx
    ff = CY - d * CX - e * CY + sy
    return np.asarray(im.transform((W, H), Image.AFFINE, (a, b, cc, d, e, ff), resample=Image.BILINEAR))


def hue(img, deg):
    a_ = math.radians(deg)
    c, s = math.cos(a_), math.sin(a_)
    m = np.array([
        [0.213 + 0.787 * c - 0.213 * s, 0.715 - 0.715 * c - 0.715 * s, 0.072 - 0.072 * c + 0.928 * s],
        [0.213 - 0.213 * c + 0.143 * s, 0.715 + 0.285 * c + 0.140 * s, 0.072 - 0.072 * c - 0.283 * s],
        [0.213 - 0.213 * c - 0.787 * s, 0.715 - 0.715 * c + 0.715 * s, 0.072 + 0.928 * c + 0.072 * s],
    ], dtype=np.float32)
    return img @ m.T


def grade(img, sat=1.15, con=1.06, bright=0.0, hue_deg=0.0):
    g = img.mean(2, keepdims=True)
    img = g + (img - g) * sat
    img = (img - 128.0) * con + 128.0 + bright
    if hue_deg:
        img = hue(img, hue_deg)
    return img


def split(img, px, py=0):
    """rgb split, img float"""
    if px == 0 and py == 0:
        return img
    out = img.copy()
    out[..., 0] = np.roll(img[..., 0], (int(py), int(px)), axis=(0, 1))
    out[..., 2] = np.roll(img[..., 2], (int(-py), int(-px)), axis=(0, 1))
    return out


def grain(img, amt, rng, mono=True):
    if amt <= 0:
        return img
    if mono:
        n = rng.normal(0, amt, (H, W, 1)).astype(np.float32)
    else:
        n = rng.normal(0, amt, (H, W, 3)).astype(np.float32)
    return img + n


def u8(img):
    return np.clip(img, 0, 255).astype(np.uint8)


def kaleido(img, rot=0.0, zoom=1.0, tiles=4):
    im = aff(img, zoom=zoom, rot=rot)
    h2, w2 = H // 2, W // 2
    q = im[:h2, :w2]
    top = np.concatenate([q, q[:, ::-1]], axis=1)
    out = np.concatenate([top, top[::-1]], axis=0)
    if tiles == 8:
        out = np.concatenate([out, out[:, ::-1]], axis=1)[:, :W]
        out = np.concatenate([out, out[::-1]], axis=0)[:H]
    return aff(out, rot=rot * 0.6, zoom=1.02)


def block_glitch(img, rng, strength=1.0, bands=14):
    out = img.copy()
    edges = np.linspace(0, H, bands + 1).astype(int)
    for k in range(bands):
        y0, y1 = edges[k], edges[k + 1]
        if rng.random() < 0.55:
            sh = int(rng.normal(0, 40 * strength))
            out[y0:y1] = np.roll(out[y0:y1], sh, axis=1)
        if rng.random() < 0.12:
            out[y0:y1] = out[y0:y1, ::-1]
    # random rectangles
    for _ in range(int(4 * strength)):
        w_ = int(rng.integers(20, 260)); h_ = int(rng.integers(6, 90))
        x_ = int(rng.integers(0, W - w_)); y_ = int(rng.integers(0, H - h_))
        if rng.random() < 0.5:
            out[y_:y_ + h_, x_:x_ + w_] = out[y_:y_ + h_, x_:x_ + w_][:, ::-1]
        else:
            out[y_:y_ + h_, x_:x_ + w_] = 255 - out[y_:y_ + h_, x_:x_ + w_]
    return out


def edges(img):
    g = Image.fromarray(u8(img).mean(2).astype(np.uint8) if img.ndim == 3 else u8(img))
    e = g.filter(ImageFilter.FIND_EDGES)
    return np.asarray(e).astype(np.float32)


_PAPER = None
def paper():
    global _PAPER
    if _PAPER is None:
        rng = np.random.default_rng(7)
        base = np.ones((H, W, 3), np.float32) * np.array([238, 231, 213], np.float32)
        base += rng.normal(0, 7, (H, W, 1)).astype(np.float32)
        rules = (np.arange(H) % 44 == 0)[:, None, None]
        base -= rules * 26
        v = (1 - 0.25 * np.clip(R - 0.5, 0, 1) ** 1.2)[..., None]
        _PAPER = base * v
    return _PAPER


PARTS = None
def particles():
    global PARTS
    if PARTS is None:
        rng = np.random.default_rng(11)
        PARTS = dict(
            x=rng.uniform(0, W, 220), y=rng.uniform(0, H, 220),
            vx=rng.normal(0, 26, 220), vy=rng.normal(-34, 26, 220),
            ph=rng.uniform(0, 6.28, 220), sz=rng.uniform(1.2, 4.2, 220),
        )
    return PARTS


# ---------- drawing helpers ----------
def hud(dr, t, mode='', e=0.0):
    col = (255, 255, 255)
    dim = (255, 255, 255, 120)
    # corner frame ticks
    m, ln, th = 34, 54, 3
    for (x0, y0, dx, dy) in [(m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)]:
        dr.line([x0, y0, x0 + dx * ln, y0], fill=(255, 255, 255, 200), width=th)
        dr.line([x0, y0, x0, y0 + dy * ln], fill=(255, 255, 255, 200), width=th)
    # timecode
    tc = f"{int(t)//60:02d}:{t%60:05.2f}"
    dr.text((m + 6, m + 12), tc, font=font(22), fill=(255, 255, 255, 210))
    dr.text((m + 6, m + 40), mode, font=font(18), fill=(255, 255, 255, 140))
    # progress
    dr.line([m, H - m + 14, W - m, H - m + 14], fill=(255, 255, 255, 70), width=2)
    dr.line([m, H - m + 14, m + (W - 2 * m) * min(1, t / DUR), H - m + 14], fill=(255, 255, 255, 220), width=4)
    # source credit covering the original watermark
    dr.rectangle([W - 232, H - 74, W - 26, H - 40], fill=(0, 0, 0, 150))
    dr.text((W - 224, H - 68), "src: dola.ai", font=font(20), fill=(255, 255, 255, 190))


def rings(dr, t, e, cx, cy, n=6, base=110, gap=52, col=(255, 255, 255), wob=1.0):
    for k in range(n):
        r = base + gap * k + 18 * e * math.sin(t * 3 + k)
        a = int(200 * (1 - k / (n + 1)))
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col + (a,), width=2)
        if wob:
            for j in range(0, 360, 45):
                aa = math.radians(j + t * 40 * (1 if k % 2 else -1))
                x1 = cx + math.cos(aa) * (r - 6); y1 = cy + math.sin(aa) * (r - 6)
                x2 = cx + math.cos(aa) * (r + 6); y2 = cy + math.sin(aa) * (r + 6)
                dr.line([x1, y1, x2, y2], fill=col + (a,), width=2)


def glitch_text(dr, txt, x, y, sz, col=(255, 255, 255), jitter=0, rng=None):
    f = font(sz)
    if jitter:
        for k, off in enumerate([(-3, 0), (3, 1), (0, 2)]):
            cc = [(255, 60, 60), (60, 255, 210), (255, 240, 60)][off[1]]
            dr.text((x + off[0], y), txt, font=f, fill=cc + (140,))
    dr.text((x, y), txt, font=f, fill=col + (245,))


def label(dr, txt, x, y, sz=30, col=(255, 255, 255), box=(0, 0, 0, 170), pad=10):
    f = font(sz)
    bb = dr.textbbox((0, 0), txt, font=f)
    w_ = bb[2] - bb[0]; h_ = bb[3] - bb[1]
    dr.rectangle([x - pad, y - pad, x + w_ + pad, y + h_ + pad * 2], fill=box)
    dr.text((x, y), txt, font=f, fill=col + (255,))


def stickers(dr, t, e, rng):
    # small weird glyphs
    for _ in range(5):
        x = rng.integers(60, W - 60); y = rng.integers(90, H - 110)
        s = rng.integers(8, 22)
        g = rng.choice(["x", "+", "o", "|", "/"])
        dr.line([x - s, y, x + s, y], fill=(255, 255, 255, 150), width=2)
        if g != "|":
            dr.line([x, y - s, x, y + s], fill=(255, 255, 255, 150), width=2)


def text_card(txt, sub=None, col=(255, 255, 255), jitter=1):
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    f = font(76)
    bb = dr.textbbox((0, 0), txt, font=f)
    glitch_text(dr, txt, (W - (bb[2] - bb[0])) / 2, H / 2 - 90, 76, col, jitter=jitter)
    if sub:
        f2 = font(26)
        bb2 = dr.textbbox((0, 0), sub, font=f2)
        dr.text(((W - (bb2[2] - bb2[0])) / 2, H / 2 + 30), sub, font=f2, fill=(255, 255, 255, 200))
    return img


def finish(arr_u8, dr_fn=None, t=0, mode='', e=0.0, hud_on=True, rng=None):
    im = Image.fromarray(arr_u8).convert('RGBA')
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    if dr_fn:
        dr_fn(dr, t, e)
    if hud_on:
        hud(dr, t, mode, e)
    im = Image.alpha_composite(im, layer)
    return np.asarray(im.convert('RGB'))


# ---------- shots ----------
PREV = None


def sh_intro(t, i, e):
    rng = np.random.default_rng(100 + i)
    img = np.zeros((H, W, 3), np.float32) + np.array([8, 10, 16], np.float32)
    img += rng.normal(0, 22, (H, W, 1)).astype(np.float32)
    for _ in range(9):
        y = int(rng.integers(0, H)); h = int(rng.integers(2, 14))
        img[y:y + h] = img[y:y + h] * 0.3 + rng.uniform(30, 160) * rng.random((1, 1, 3))
    grow = np.clip(t / 3.2, 0, 1)
    rr = grow * 0.55
    ring = np.exp(-((R - rr) / 0.012) ** 2)
    ring2 = np.exp(-((R - rr * 0.62) / 0.006) ** 2)
    img += ring[..., None] * np.array([255, 190, 90], np.float32) * 0.9
    img += ring2[..., None] * np.array([255, 70, 160], np.float32) * 0.7
    img *= VIGN
    img = grade(img, sat=1.3, con=1.1)
    img += rng.normal(0, 10, (H, W, 1)).astype(np.float32)
    out = u8(img)

    def dr_(dr, tt, ee):
        if 0.4 < tt < 3.4:
            txt = ["СИГНАЛ", "ИДЁТ", "ЧТО ЭТО"][min(2, int((tt - 0.4) / 1.0))]
            glitch_text(dr, txt, 150, 760, 54, jitter=1)
        stickers(dr, tt, ee, rng)
    return finish(out, dr_, t, 'NO SIGNAL', e)


def sh_A(t, i, e):
    lt = t - bars(1)
    sp = 1.0 + 0.05 * lt / 8 + 0.06 * e
    f = sframe(t, rate=0.9)
    img = aff(f, zoom=sp, rot=1.2 * math.sin(lt * 0.7), sx=6 * math.sin(lt * 1.7), sy=4 * math.cos(lt * 1.3)).astype(np.float32)
    img = grade(img, sat=1.35, con=1.12, bright=6 * e, hue_deg=8 * math.sin(lt * 0.6))
    img = split(img, 6 + 16 * e, 3 + 5 * e)
    img = img * SCAN * VIGN
    rng = np.random.default_rng(200 + i)
    img = grain(img, 8, rng)
    # thin drifting horizontal band
    yb = int((lt * 130) % H)
    img[yb:yb + 26] = img[yb:yb + 26] * 1.6 + 40
    out = u8(img)

    def dr_(dr, tt, ee):
        p = (tt - bars(1)) / 8.0
        dr.rectangle([60, 300, 60 + 260 * p, 308], fill=(255, 255, 255, 160))
        label(dr, "ФАЗА 01 / ОНО ДЫШИТ", 60, 250, 26, (255, 255, 255))
        rings(dr, tt, ee, W * 0.5, H * 0.52, n=3, base=300, gap=46)
    return finish(out, dr_, t, '01 BLOOM', e)


def sh_B(t, i, e):
    lt = t - bars(3)
    f = sframe(t, rate=1.25)
    k = kaleido(f, rot=lt * 26, zoom=1.25 + 0.05 * e, tiles=4)
    img = k.astype(np.float32)
    img = grade(img, sat=1.5, con=1.18, hue_deg=lt * 40 + 30 * e)
    img = split(img, 20 * e, 0)
    img *= SCAN4
    img = grain(img, 7, np.random.default_rng(300 + i))
    img = img * VIGN
    out = u8(img)

    def dr_(dr, tt, ee):
        rings(dr, tt, ee, W / 2, H / 2, n=5, base=90, gap=70, col=(255, 255, 255))
        if int(tt * 6) % 2 == 0:
            label(dr, "СИММЕТРИЯ", 120, 700, 40, (210, 255, 200))
    return finish(out, dr_, t, '02 KALEIDO', e)


def sh_C(t, i, e):
    rng = np.random.default_rng(400 + i)
    st = int((t - bars(5)) / (BAR / 8))
    f = sframe(t, rate=2.2)
    img = f.astype(np.float32)
    variant = st % 5
    if variant == 0:
        img = grade(img, sat=0.0, con=1.9, bright=20)
        img = np.round(img / 64) * 64
    elif variant == 1:
        img = 255 - grade(img, sat=1.8, con=1.3)
        img = hue(img, 140)
    elif variant == 2:
        img = split(grade(img, sat=1.6, con=1.5), 40)
        img = block_glitch(img, rng, 1.4, 20)
    elif variant == 3:
        e_ = edges(img)
        img = np.stack([e_ * 2.2, e_ * 0.4, e_ * 1.6], -1)
    else:
        img = grade(img, sat=2.0, con=1.4, hue_deg=180)
        img = np.repeat(img.mean(2, keepdims=True), 3, 2) * np.array([1.4, 0.5, 1.1], np.float32)
    img = block_glitch(img, rng, 0.7, 10)
    img = img * SCAN + grain(img, 12, rng) * 0 + 0
    img += rng.normal(0, 12, (H, W, 1)).astype(np.float32)
    out = u8(img * VIGN)

    def dr_(dr, tt, ee):
        glitch_text(dr, "ОШИБКА", 90 + 20 * math.sin(tt * 20), 90, 40, (255, 90, 90), jitter=1)
        dr.text((700, 800), f"{st:03d}", font=font(34), fill=(255, 255, 255, 200))
        for _ in range(3):
            x = rng.integers(0, W); y = rng.integers(0, H)
            dr.line([x, y, x + rng.integers(-200, 200), y + rng.integers(-30, 30)], fill=(255, 255, 255, 120), width=2)
    return finish(out, dr_, t, '03 ERROR', e)


CHARS = " .:-=+*#%@"


def ascii_plate(t, col, cols=48):
    f = sframe(t, rate=1.1)
    g = np.asarray(Image.fromarray(f).convert('L').resize((cols, cols), Image.BILINEAR))
    g = g.astype(np.float32) / 255.0
    img = np.zeros((H, W, 3), np.float32) + np.array([6, 14, 8], np.float32)
    im = Image.fromarray(u8(img))
    dr = ImageDraw.Draw(im)
    cell = W / cols
    fnt = font(int(cell * 1.05))
    for r in range(cols):
        for c in range(cols):
            v = g[r, c]
            ch = CHARS[min(len(CHARS) - 1, int(v * len(CHARS)))]
            if ch == ' ':
                continue
            br = 0.45 + 0.85 * v
            cc = tuple(int(min(255, col[k] * br)) for k in range(3))
            dr.text((c * cell, r * cell - cell * 0.15), ch, font=fnt, fill=cc)
    return np.asarray(im).astype(np.float32)


def sh_D(t, i, e):
    lt = t - bars(7)
    if lt >= BAR:      # second bar: ascii scan
        st = int(lt * 4)
        img = ascii_plate(t, (120 + 60 * math.sin(lt * 2), 255, 170), cols=48)
        img = img * SCAN4
        img += np.random.default_rng(555 + i).normal(0, 7, (H, W, 1)).astype(np.float32)
        out = u8(img)
        def dr_(dr, tt, ee):
            label(dr, "СКАН / ASCII", 60, 690, 26, (150, 255, 190))
            dr.rectangle([40, 40, W - 40, H - 40], outline=(120, 255, 180, 90), width=2)
            p = (tt - bars(8)) / BAR
            dr.line([60, H - 120, 60 + (W - 120) * max(0, min(1, p)), H - 120], fill=(120, 255, 180, 200), width=4)
        return finish(out, dr_, t, '04 SCAN', e)

    f0 = sframe(t, rate=0.8)
    f1 = sframe(t + 3.0, rate=1.1)
    f2 = sframe(t + 6.0, rate=1.5)
    strips = []
    xs = [0, 320, 640, W]
    for k, (a, b) in enumerate(zip(xs[:-1], xs[1:])):
        src_ = [f0, f1, f2][k % 3]
        off = int(70 * math.sin(lt * 1.4 + k * 2.1) + 40 * e * math.sin(k + lt * 5))
        col = np.roll(src_[:, a:b], off, axis=0)
        strips.append(col)
    img = np.concatenate(strips, axis=1).astype(np.float32)
    for x in (320, 640):
        img[:, x - 2:x + 2] = 0
    img = grade(img, sat=1.2, con=1.15, hue_deg=10 * math.sin(lt))
    img = split(img, 10 + 10 * e)
    img = img * SCAN * VIGN
    out = u8(grain(img, 8, np.random.default_rng(500 + i)))

    def dr_(dr, tt, ee):
        for x in (320, 640):
            dr.line([x, 0, x, H], fill=(255, 255, 255, 60), width=2)
        label(dr, "ТРИ ВЕРСИИ ОДНОГО", 60, 660, 28)
        dr.ellipse([W / 2 - 10, 120, W / 2 + 10, 140], outline=(255, 255, 255, 180), width=3)
    return finish(out, dr_, t, '04 SPLIT', e)


def sh_E(t, i, e):
    global PREV
    lt = t - bars(9)
    f = sframe(t, rate=1.0)
    img = aff(f, zoom=1.06 + 0.02 * math.sin(lt * 2), rot=3 * math.sin(lt * 0.9)).astype(np.float32)
    img = grade(img, sat=1.4, con=1.1, hue_deg=20 * math.sin(lt * 0.8))
    if PREV is None:
        PREV = img.copy()
    z = 1.035 + 0.02 * e
    pz = aff(u8(PREV), zoom=z, rot=1.2)
    trail = pz.astype(np.float32) * 0.86 + 6
    img = np.maximum(img * 0.88, trail)
    PREV = img.copy()
    ed = edges(img)
    img = img + np.stack([ed * 0.9, ed * 0.2, ed * 0.8], -1) * (0.5 + e)
    img *= SCAN * VIGN
    img = split(img, 12 + 30 * e, 0)
    out = u8(grain(img, 9, np.random.default_rng(600 + i)))

    def dr_(dr, tt, ee):
        rings(dr, tt, ee, W / 2, H / 2, n=7, base=60, gap=62, col=(255, 200, 120))
        label(dr, "ОСТАТОЧНЫЙ СЛЕД", 90, 800, 30, (255, 220, 150))
    return finish(out, dr_, t, '05 TRAIL', e)


def sh_F(t, i, e):
    lt = t - bars(13)
    f = sframe(t, rate=0.85)
    ed = edges(f.astype(np.float32))
    ed = np.clip(ed * 1.5, 0, 255)
    base = paper()
    ink = 255 - np.repeat(ed[..., None], 3, 2) * np.array([0.95, 0.9, 0.82], np.float32) * 1.6
    img = np.minimum(base, ink)
    # hatch shading in darks
    hatch = ((xx + yy) % 13 < 2) & (ed > 20)
    img[hatch] *= 0.75
    out = u8(img)

    def dr_(dr, tt, ee):
        f_ = font(46)
        dr.text((70, 90), "карандаш / 0.5", font=f_, fill=(40, 36, 30, 230))
        dr.line([70, 150, 420, 150], fill=(40, 36, 30, 200), width=3)
        for k in range(4):
            dr.line([70, 200 + k * 8, 300 + 40 * math.sin(tt + k), 200 + k * 8], fill=(40, 36, 30, 120), width=2)
        dr.ellipse([W - 220, H - 240, W - 100, H - 120], outline=(180, 60, 40, 200), width=4)
        dr.text((W - 200, H - 100), "ОНО", font=font(34), fill=(180, 60, 40, 230))
    return finish(out, dr_, t, '06 INK', e, hud_on=True, rng=None)


def sh_G(t, i, e):
    lt = t - bars(15)
    bg = kaleido(sframe(t, rate=0.7), rot=lt * 12, zoom=1.5).astype(np.float32)
    bg = grade(bg, sat=0.9, con=1.2, hue_deg=210) * 0.55
    small = sframe(t + 1.0, rate=1.0)
    sz = 380 + int(30 * e)
    sm = np.asarray(Image.fromarray(small).resize((sz, sz), Image.BILINEAR)).astype(np.float32)
    sm = grade(sm, sat=1.4, con=1.15)
    x0 = int(W / 2 - sz / 2 + 40 * math.sin(lt * 1.1)); y0 = int(H / 2 - sz / 2 + 30 * math.cos(lt * 0.9))
    bg[y0:y0 + sz, x0:x0 + sz] = sm
    img = bg * SCAN * VIGN
    img = split(img, 8 + 14 * e)
    img = grain(img, 8, np.random.default_rng(700 + i))
    out = u8(img)

    def dr_(dr, tt, ee):
        dr.rectangle([x0 - 6, y0 - 6, x0 + sz + 6, y0 + sz + 6], outline=(255, 255, 255, 200), width=3)
        label(dr, "СМОТРИ ВНУТРЬ", x0 + 4, y0 + sz + 18, 24)
        rings(dr, tt, ee, W / 2, H / 2, n=4, base=sz / 2 + 60, gap=44, col=(120, 240, 255))
    return finish(out, dr_, t, '07 RECURSE', e)


def sh_H(t, i, e):
    lt = t - bars(17)
    f = sframe(t, rate=1.6)
    img = aff(f, zoom=1.1 + 0.12 * e, rot=8 * math.sin(lt * 3)).astype(np.float32)
    img = grade(img, sat=1.8, con=1.35, hue_deg=lt * 120)
    beat_phase = (lt * 90 / 60) % 1.0
    if beat_phase < 0.18 or e > 0.55:
        img = 255 - img
    img = split(img, 30 * e)
    img = img * SCAN + grain(img, 14, np.random.default_rng(800 + i))
    out = u8(img * VIGN + 12 * e)

    def dr_(dr, tt, ee):
        if ee > 0.4:
            dim = Image.new('RGBA', (W, H), (255, 255, 255, 40))
        dr.rectangle([100, 400, 700, 530], fill=(0, 0, 0, 150))
        glitch_text(dr, "НЕ СМОТРИ", 120, 420, 84, jitter=1)
        stickers(dr, tt, ee, np.random.default_rng(int(tt * 8)))
    return finish(out, dr_, t, '08 STROBE', e)


def sh_I(t, i, e):
    global PREV
    lt = t - bars(19)
    f = sframe(t, rate=1.4)
    img = aff(f, zoom=1.15, rot=lt * 10).astype(np.float32)
    # swirl hue by angle
    hshift = (ANG * 60 + lt * 90) % 360
    img = hue(img, 40)
    img = grade(img, sat=1.9, con=1.25)
    swirl = np.sin(ANG * 6 + R * 18 - lt * 3) * 0.5 + 0.5
    img = img * (0.72 + 0.55 * swirl[..., None])
    img = np.maximum(img, 0.82 * (PREV * 0.9 if PREV is not None else 0))
    PREV = img.copy()
    img *= VIGN
    img = split(img, 24 * e, 8 * e)
    out = u8(grain(img, 10, np.random.default_rng(900 + i)))

    def dr_(dr, tt, ee):
        p = particles()
        for k in range(len(p['x'])):
            x = (p['x'][k] + p['vx'][k] * tt) % W
            y = (p['y'][k] + p['vy'][k] * tt) % H
            s = p['sz'][k] * (1 + ee)
            dr.ellipse([x - s, y - s, x + s, y + s], fill=(255, 255, 255, 170))
        rings(dr, tt, ee, W / 2, H / 2, n=6, base=80, gap=56, col=(255, 160, 255))
    return finish(out, dr_, t, '09 SWIRL', e)


def sh_J(t, i, e):
    lt = t - bars(21)
    end_black = 59.15
    if t >= end_black:
        img = np.zeros((H, W, 3), np.float32)
        rng = np.random.default_rng(1200 + i)
        img += rng.normal(0, 14, (H, W, 1)).astype(np.float32)
        out = u8(img)
        def dr_(dr, tt, ee):
            glitch_text(dr, "КОНЕЦ", 350, 430, 66, jitter=1)
            dr.text((350, 520), "музыка: beautiful far distance", font=font(20), fill=(255, 255, 255, 140))
        return finish(out, dr_, t, '', e, hud_on=False)

    f = sframe(t, rate=2.4)
    st = int(lt / (BAR / 8))
    img = f.astype(np.float32)
    if st % 2 == 0:
        img = grade(img, sat=1.9, con=1.3, hue_deg=lt * 200)
    else:
        img = 255 - grade(img, sat=1.6, con=1.4, hue_deg=90)
    img = aff(u8(img), zoom=1.05 + 0.25 * e, rot=st * 11).astype(np.float32)
    img = block_glitch(img, np.random.default_rng(1000 + i), 0.9, 12)
    img = split(img, 26 * e)
    img = img * SCAN4 * VIGN
    out = u8(grain(img, 12, np.random.default_rng(1100 + i)))

    def dr_(dr, tt, ee):
        dr.rectangle([230, 400, 690, 510], fill=(0, 0, 0, 160))
        glitch_text(dr, "ОНО ЖИВОЕ", 250, 420, 62, jitter=1)
        rings(dr, tt, ee, W / 2, H / 2, n=8, base=40, gap=58, col=(255, 255, 255))
    return finish(out, dr_, t, '10 END', e)


SHOTS = [
    (0.0, bars(1), sh_intro),
    (bars(1), bars(3), sh_A),
    (bars(3), bars(5), sh_B),
    (bars(5), bars(7), sh_C),
    (bars(7), bars(9), sh_D),
    (bars(9), bars(13), sh_E),
    (bars(13), bars(15), sh_F),
    (bars(15), bars(17), sh_G),
    (bars(17), bars(19), sh_H),
    (bars(19), bars(21), sh_I),
    (bars(21), 60.0, sh_J),
]


STARTS = [b for (a, b, fn) in SHOTS[1:]]


def render_frame(i):
    t = i / FPS
    e = float(ENV[i])
    out = None
    for (a, b, fn) in SHOTS:
        if a <= t < b:
            out = fn(t, i, e)
            break
    if out is None:
        out = SHOTS[-1][2](t, i, e)
    # punch-in flash right after each cut
    for st in STARTS:
        dt = t - st
        if 0 <= dt < 2.0 / FPS:
            out = u8(np.asarray(out, np.float32) + (255 - np.asarray(out, np.float32)) * (0.55 if dt < 1 / FPS else 0.3))
        elif 0 <= dt < 4.0 / FPS:
            sh = int(6 * (1 - dt * FPS / 4.0))
            out = np.roll(out, sh, axis=1)
    return out


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'work/video.mp4'
    samples = sys.argv[2] if len(sys.argv) > 2 else None
    if samples:
        os.makedirs('work/frames', exist_ok=True)
        for s in samples.split(','):
            i = int(s)
            Image.fromarray(render_frame(i)).save(f'work/frames/f{i:04d}.jpg', quality=90)
        print('frames', samples)
    else:
        p = subprocess.Popen([FF, '-hide_banner', '-loglevel', 'error', '-y',
                              '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                              '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                              '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
        for i in range(N):
            p.stdin.write(render_frame(i).tobytes())
            if i % 120 == 0:
                print(i, flush=True)
        p.stdin.close()
        p.wait()
        print('done', out)
