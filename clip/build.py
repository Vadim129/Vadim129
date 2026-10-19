#!/usr/bin/env python3
"""Сборка клипа «Фонтанчик с чёрным дельфином».

50 кадров 16:9 + движение камеры (только план, персонаж не анимируется),
караоке-строка внизу (шрифт Ruslan Display), эквалайзер из пик и червей
по бокам, оригинальный трек.
"""
import json
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = "/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
SONG = os.path.join(ROOT, "google_drive", "Гио_Пика_Фонтанчик_с_черным_дельфином_zaycev_net.mp3")
FRAMES = os.path.join(ROOT, "frames_h", "prison")
OUT = os.path.join(ROOT, "clip")
WORK = "/tmp/clipwork"
FONT_R = os.path.join(OUT, "fonts", "ruslan.ttf")
FONT_S = os.path.join(OUT, "fonts", "oswald.ttf")
FONT_SUIT = os.path.join(OUT, "fonts", "DejaVuSans.ttf")
W, H, FPS = 1920, 1080, 25
TOTAL = 208.744
NFRAMES = round(TOTAL * FPS)

CAP_H = 220                      # полоса титров
CAP_Y = 790
CAP_MAXW = 1120

EQ_W, EQ_H = 270, 330            # полоса эквалайзера
EQ_Y = 720
EQ_XL, EQ_XR = 70, W - 70 - EQ_W

IVORY = (250, 241, 220, 255)
DIM = (233, 222, 201, 132)
SPADE = (238, 228, 207, 240)
HEART = (198, 54, 50, 240)


def run(cmd, **kw):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kw)
    if p.returncode:
        sys.stderr.write(p.stdout.decode("utf-8", "replace")[-4000:])
        raise SystemExit("ffmpeg упал")
    return p.stdout


# ------------------------------------------------------------------ текст

def load_lyrics():
    title = ("ГИО ПИКА", "Фонтанчик с чёрным дельфином")
    blocks, cur = [], []
    for raw in open(os.path.join(OUT, "lyrics.txt"), encoding="utf-8"):
        line = raw.strip()
        if not line:
            if cur:
                blocks.append(cur)
                cur = []
            continue
        if line.startswith("#TITLE|"):
            parts = line.split("|")
            title = (parts[1], parts[2])
            continue
        cur.append(line)
    if cur:
        blocks.append(cur)
    return title, blocks


def load_cues():
    d = json.load(open(os.path.join(OUT, "timing.json"), encoding="utf-8"))
    cues = []
    for p in d["passes"]:
        cues += p
    return cues


def gradient_plate():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = img.load()
    for y in range(H):
        if y < 400:
            continue
        t = (y - 400) / (H - 400)
        a = int(150 * (t ** 1.8))
        for x in range(W):
            px[x, y] = (4, 4, 5, a)
    return img


def render_title(title):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.alpha_composite(gradient_plate())
    d = ImageDraw.Draw(img)
    f_art = ImageFont.truetype(FONT_S, 46)
    f_song = ImageFont.truetype(FONT_R, 96)
    sub = " ".join(title[0])
    wt = d.textlength(sub, font=f_art)
    d.text(((W - wt) / 2, 300), sub, font=f_art, fill=(214, 200, 176, 235))
    tt = title[1]
    while d.textlength(tt, font=f_song) > W - 320:
        f_song = ImageFont.truetype(FONT_R, f_song.size - 4)
    tw = d.textlength(tt, font=f_song)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text(((W - tw) / 2, 378), tt, font=f_song, fill=(0, 0, 0, 210))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    d.text(((W - tw) / 2, 378), tt, font=f_song, fill=IVORY)
    return img


def caption_layers(text):
    """(тусклый слой, яркий слой, x0, границы слов в пикселях)."""
    strip = Image.new("RGBA", (W, CAP_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    size = 78
    words = text.split()
    while True:
        font = ImageFont.truetype(FONT_R, size)
        if d.textlength(text, font=font) <= CAP_MAXW or size <= 46:
            break
        size -= 2
    tw = d.textlength(text, font=font)
    x = (W - tw) / 2
    y = (CAP_H - size * 1.25) / 2
    # границы слов — по префиксам строки, так точнее чем по отдельным словам
    xs = []
    for i in range(len(words) + 1):
        xs.append(d.textlength(" ".join(words[:i]), font=font))
    xs[-1] = tw

    plate = Image.new("RGBA", (W, CAP_H), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle(
        (x - 46, 8, x + tw + 46, CAP_H - 8), radius=26, fill=(5, 5, 6, 96))
    strip.alpha_composite(plate.filter(ImageFilter.GaussianBlur(18)))

    dim = strip.copy()
    ImageDraw.Draw(dim).text((x, y), text, font=font, fill=DIM,
                             stroke_width=2, stroke_fill=(0, 0, 0, 60))

    bright = Image.new("RGBA", (W, CAP_H), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (W, CAP_H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((x, y + 3), text, font=font, fill=(0, 0, 0, 200),
                                stroke_width=5, stroke_fill=(0, 0, 0, 200))
    bright.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(4)))
    ImageDraw.Draw(bright).text((x, y), text, font=font, fill=IVORY,
                                stroke_width=2, stroke_fill=(26, 20, 14, 230))
    return dim, bright, int(round(x)), [int(round(v)) for v in xs], font


class RawVideo:
    """Поток кадров RGBA в ffmpeg (qtrle с альфой)."""

    def __init__(self, path, w, h):
        self.p = subprocess.Popen(
            [FF, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
             "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
             "-c:v", "qtrle", path],
            stdin=subprocess.PIPE)

    def write(self, img):
        self.p.stdin.write(img.tobytes())

    def close(self):
        self.p.stdin.close()
        if self.p.wait():
            raise SystemExit("кодировщик титров упал")


def build_caption_video(cues):
    path = os.path.join(WORK, "caps.mov")
    vid = RawVideo(path, W, CAP_H)
    blank = Image.new("RGBA", (W, CAP_H), (0, 0, 0, 0))
    cache = {}
    idx = 0
    for f in range(NFRAMES):
        t = f / FPS
        while idx + 1 < len(cues) and t >= cues[idx]["t1"]:
            idx += 1
        cue = cues[idx]
        if t < cue["t0"] or t > cue["t1"]:
            vid.write(blank)
            continue
        key = cue["text"]
        if key not in cache:
            cache[key] = caption_layers(cue["text"])
        dim, bright, x, xs, _ = cache[key]
        frame = Image.new("RGBA", (W, CAP_H), (0, 0, 0, 0))
        frame.alpha_composite(dim)
        ws = cue["words"]
        wv = 0.0
        for i, w in enumerate(ws):
            if t >= w["t1"]:
                wv = xs[i + 1]
            elif t >= w["t0"]:
                p = (t - w["t0"]) / max(0.01, w["t1"] - w["t0"])
                wv = xs[i] + (xs[i + 1] - xs[i]) * p
                break
            else:
                break
        wv = int(round(wv))
        if wv > 0:
            frame.alpha_composite(bright.crop((x, 0, x + wv, CAP_H)), (x, 0))
        vid.write(frame)
    vid.close()

    return path


# --------------------------------------------------------------- эквалайзер

def eq_levels(bands=10):
    wav = "/tmp/song_eq.wav"
    if not os.path.exists(wav):
        run([FF, "-y", "-v", "error", "-i", SONG, "-ac", "1", "-ar", "22050", wav])
    w = wave.open(wav)
    sr, n = w.getframerate(), w.getnframes()
    x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    win, hop = 1024, 512
    fb = np.fft.rfftfreq(win, 1 / sr)
    edges = np.geomspace(55, 9000, bands + 1)
    masks = [(fb >= edges[i]) & (fb < edges[i + 1]) for i in range(bands)]
    wnd = np.hanning(win).astype(np.float32)
    frames = (len(x) - win) // hop
    E = np.zeros((frames, bands), dtype=np.float32)
    for i in range(frames):
        sp = np.abs(np.fft.rfft(x[i * hop:i * hop + win] * wnd)) ** 2
        for b, m in enumerate(masks):
            E[i, b] = np.sqrt(sp[m].mean() + 1e-12)
    db = 20 * np.log10(E + 1e-9)
    # динамика относительно медленной средней: столбики «играют», а не стоят
    win = 86                                   # ~2 c при hop 512 / 22050
    ker = np.ones(win) / win
    base = np.stack([np.convolve(db[:, b], ker, "same") for b in range(bands)], 1)
    rel = db - base
    v = np.clip((rel + 5.5) / 11.0, 0, 1)
    sm = np.zeros_like(v)
    prev = v[0].astype(np.float32).copy()
    for i in range(len(v)):
        k = np.where(v[i] > prev, 0.65, 0.18)
        prev = prev + (v[i] - prev) * k
        sm[i] = prev
    tf = np.arange(frames) * hop / sr
    tt = np.arange(NFRAMES) / FPS
    out = np.stack([np.interp(tt, tf, sm[:, b]) for b in range(bands)], 1)
    lv = 1 + (out ** 1.25) * 7
    return np.clip(lv.round().astype(int), 1, 8)


def suit_patches(glyph=30):
    font = ImageFont.truetype(FONT_SUIT, glyph)
    patches = {}
    for suit, color in (("s", SPADE), ("h", HEART)):
        ch = "\u2660" if suit == "s" else "\u2665"
        for lvl in range(1, 9):
            im = Image.new("RGBA", (glyph + 6, lvl * (glyph + 4) + 8), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            for i in range(lvl):
                d.text((3, 4 + i * (glyph + 4)), ch, font=font, fill=color)
            patches[(suit, lvl)] = im
    return patches


def build_eq_video():
    cols, glyph, gap = 6, 30, 14
    levels = eq_levels(cols)
    patches = suit_patches()
    path = os.path.join(WORK, "eq.mov")
    vid = RawVideo(path, EQ_W, EQ_H)
    total_w = cols * (glyph + gap) - gap
    x0 = (EQ_W - total_w) // 2
    for f in range(NFRAMES):
        im = Image.new("RGBA", (EQ_W, EQ_H), (0, 0, 0, 0))
        for c in range(cols):
            lvl = int(levels[f, c])
            if lvl <= 0:
                continue
            suit = "s" if c % 2 == 0 else "h"
            patch = patches[(suit, lvl)]
            x = x0 + c * (glyph + gap)
            im.alpha_composite(patch, (x, EQ_H - 12 - patch.height))
        vid.write(im)
    vid.close()
    return path


# ------------------------------------------------------------------ видео

# Порядок по смыслу песни: суд -> автозак/поезд -> ворота колонии -> камера,
# коридор, «поза дельфинчика», прогулочный бокс -> фонтан.
# Прогулки по двору и футбол убраны: в ИК-6 двора нет, прогулки — в боксе.
SEQUENCE = [
    # --- суд
    "101-court-wide", "103-verdict-desk", "104-cuffs-folder", "102-cage-portrait",
    "105-led-out", "106-cuffed-escort-h", "107-court-corridor",
    # --- автозак
    "150-van-loading-clean-h", "109-van-inside", "110-van-road",
    # --- этап, поезд
    "111-railway-platform", "112-wagon-door", "113-wagon-interior", "114-wagon-window",
    # --- дорога к колонии
    "115-steppe-colony", "116-colony-approach", "117-gates-arrival",
    "151-gate-threshold-clean", "141-block-night",
    # --- приём
    "119-checkpoint", "120-undress-search",
    # --- внутри: конвой, поверка
    "121-dolphin-pose-h", "122-blindfold", "149-verification-line", "143-night-round",
    # --- камера
    "123-cell-cage", "124-cell-interior", "125-peephole", "126-food-hatch",
    "127-inspection", "129-cell-search", "145-punishment-cell",
    "142-cell-night", "147-hands-bars",
    # --- быт: работа, баня, часовня, свидание, письма, церковь, прогулка
    "130-sewing-workshop", "131-shower-cage", "132-chapel-cuffed",
    "134-letter-writing", "135-photo-wall",
    "136-prison-church", "128-walkbox", "144-walkbox-sky",
    # --- фонтан и финал (выхода нет)
    "152-dolphin-fountain", "138-dolphin-macro", "153-fountain-winter-clean",
    "140-finale-single-dolphin",
]


def shots():
    files = [f"{n}.jpg" for n in SEQUENCE
             if os.path.exists(os.path.join(FRAMES, f"{n}.jpg"))]
    assert len(files) >= 40, len(files)
    os.makedirs(os.path.join(WORK, "shots"), exist_ok=True)
    out = []
    base_n = NFRAMES // len(files)
    rest = NFRAMES - base_n * len(files)
    for i, name in enumerate(files):
        n = base_n + (1 if i < rest else 0)
        mode = i % 5
        if mode == 0:
            z = f"1+0.085*on/{n-1}"; x = "iw/2-(iw/zoom/2)"; y = "ih/2-(ih/zoom/2)"
        elif mode == 1:
            z = f"1.085-0.085*on/{n-1}"; x = "iw/2-(iw/zoom/2)"; y = "ih/2-(ih/zoom/2)"
        elif mode == 2:
            z = "1.06"; x = f"(iw-iw/zoom)*on/{n-1}"; y = "ih/2-(ih/zoom/2)"
        elif mode == 3:
            z = "1.06"; x = f"(iw-iw/zoom)*(1-on/{n-1})"; y = "ih/2-(ih/zoom/2)"
        else:
            z = "1.07"; x = "iw/2-(iw/zoom/2)"; y = f"(ih-ih/zoom)*(1-on/{n-1})"
        vf = (f"scale=3840:2160:force_original_aspect_ratio=increase,"
              f"crop=3840:2160,"
              f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={FPS},"
              f"setsar=1,format=yuv420p")
        dst = os.path.join(WORK, "shots", f"{i:02d}.mp4")
        if not os.path.exists(dst):
            run([FF, "-y", "-v", "error", "-loop", "1", "-i", os.path.join(FRAMES, name),
                 "-vf", vf, "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast",
                 "-crf", "16", "-pix_fmt", "yuv420p", dst])
        out.append(dst)
        print(f"план {i+1:02d}/{len(files)}: {name}", flush=True)
    return out


def concat(paths):
    lst = os.path.join(WORK, "list.txt")
    with open(lst, "w") as f:
        for p in paths:
            f.write(f"file '{p}'\n")
    dst = os.path.join(WORK, "base.mp4")
    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(lst):
        run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
             "-c", "copy", dst])
    return dst


def final(base, caps, eq, dst):
    fc = [
        "[1:a]afade=t=in:st=0:d=0.4,afade=t=out:st=203.6:d=5.0[a]",
        "[0:v][2:v]overlay=0:790:eof_action=pass:repeatlast=0[c2]",
        "[3:v]split[eq1][eq2]",
        "[c2][eq1]overlay=70:720:eof_action=pass:repeatlast=0[c3]",
        "[eq2]hflip[eq2f]",
        f"[c3][eq2f]overlay={EQ_XR}:720:eof_action=pass:repeatlast=0,"
        "fade=t=in:st=0:d=0.8,fade=t=out:st=203.9:d=4.8,format=yuv420p[v]",
    ]
    cmd = [FF, "-y", "-v", "error", "-i", base, "-i", SONG,
           "-i", caps, "-i", eq,
           "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", f"{TOTAL:.3f}", dst]
    run(cmd)


def main():
    os.makedirs(WORK, exist_ok=True)
    cues = load_cues()
    print(f"строк: {len(cues)}")
    if "--cues-only" in sys.argv:
        build_caption_video(cues)
        print("титры готовы")
        return
    caps = build_caption_video(cues)
    print("титры: готово", flush=True)
    eq = build_eq_video()
    print("эквалайзер: готово", flush=True)
    base = concat(shots())
    dst = os.path.join(OUT, "fontanchik_s_chernym_delfinom_1080p.mp4")
    final(base, caps, eq, dst)
    print("готово:", dst, round(os.path.getsize(dst) / 1e6, 1), "МБ")


if __name__ == "__main__":
    main()
