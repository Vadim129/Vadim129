#!/usr/bin/env python3
"""Сборка клипа «Фонтанчик с чёрным дельфином».

50 кадров 16:9 + движение камеры (только план, персонаж не анимируется) +
титры шрифтом Ruslan Display + оригинальный трек.
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = "/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
SONG = os.path.join(ROOT, "google_drive", "Гио_Пика_Фонтанчик_с_черным_дельфином_zaycev_net.mp3")
FRAMES = os.path.join(ROOT, "frames_h", "prison")
OUT = os.path.join(ROOT, "clip")
WORK = "/tmp/clipwork"
FONT_R = os.path.join(OUT, "fonts", "ruslan.ttf")
FONT_S = os.path.join(OUT, "fonts", "oswald.ttf")
W, H, FPS = 1920, 1080, 25
TOTAL = 208.744

IVORY = (245, 234, 211, 255)
DIM = (158, 147, 131, 255)


def run(cmd, **kw):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kw)
    if p.returncode:
        sys.stderr.write(p.stdout.decode("utf-8", "replace")[-4000:])
        raise SystemExit(f"ffmpeg упал: {' '.join(cmd[:6])}…")
    return p.stdout


# ---------------------------------------------------------------- текст

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


def gradient_plate():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = img.load()
    for y in range(H):
        if y < 400:
            continue
        t = (y - 400) / (H - 400)
        a = int(215 * (t ** 1.8))
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
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text(((W - tw) / 2, 378), tt, font=f_song, fill=(0, 0, 0, 210))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(9)))
    d.text(((W - tw) / 2, 378), tt, font=f_song, fill=IVORY)
    return img


def wrap(d, text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_block(lines, active):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.alpha_composite(gradient_plate())
    d = ImageDraw.Draw(img)
    size = 52 if len(lines) <= 3 else (48 if len(lines) == 4 else 44)
    font = ImageFont.truetype(FONT_R, size)
    wrapped, acts = [], []
    for i, ln in enumerate(lines):
        for p in wrap(d, ln, font, W - 460):
            wrapped.append(p)
            acts.append(i)
    lh = int(size * 1.5)
    total_h = lh * len(wrapped)
    y0 = 1006 - total_h

    # мягкая подложка под текстовый блок
    plate = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle(
        (W / 2 - 830, y0 - 46, W / 2 + 830, y0 + total_h + 26),
        radius=34, fill=(6, 6, 7, 118))
    img.alpha_composite(plate.filter(ImageFilter.GaussianBlur(26)))

    for i, (txt, a) in enumerate(zip(wrapped, acts)):
        on = a == active
        col = IVORY if on else (150, 139, 123, 255)
        y = y0 + i * lh
        tw = d.textlength(txt, font=font)
        x = (W - tw) / 2
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((x, y), txt, font=font, fill=(0, 0, 0, 210),
                                stroke_width=5, stroke_fill=(0, 0, 0, 210))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(4 if on else 3)))
        if on:
            d.text((x, y), txt, font=font, fill=col, stroke_width=2,
                   stroke_fill=(20, 16, 12, 235))
        else:
            d.text((x, y), txt, font=font, fill=col)
    return img


def make_cues():
    """[(start, end, png, fade_in, fade_out)] — подсветка строки внутри блока."""
    os.makedirs(WORK, exist_ok=True)
    title, blocks = load_lyrics()
    cues = []
    p = os.path.join(WORK, "cue_title.png")
    render_title(title).save(p)
    cues.append((0.6, 7.6, p, True, True))

    t0, t1 = 8.2, 203.4
    total_lines = sum(len(b) for b in blocks)
    per_line = (t1 - t0) / total_lines
    t = t0
    for bi, block in enumerate(blocks):
        for li in range(len(block)):
            path = os.path.join(WORK, f"cue_{bi}_{li}.png")
            render_block(block, li).save(path)
            cues.append((t, t + per_line, path, li == 0, li == len(block) - 1))
            t += per_line
    return cues


# ---------------------------------------------------------------- видео

def shots():
    files = sorted(f for f in os.listdir(FRAMES) if f.lower().endswith(".jpg"))
    assert len(files) == 50, len(files)
    total_frames = round(TOTAL * FPS)
    base = total_frames // len(files)
    rest = total_frames - base * len(files)
    out = []
    os.makedirs(os.path.join(WORK, "shots"), exist_ok=True)
    for i, name in enumerate(files):
        n = base + (1 if i < rest else 0)
        d = n / FPS
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
        print(f"план {i+1:02d}: {name}  {d:.2f} c", flush=True)
    return out


def concat(paths):
    lst = os.path.join(WORK, "list.txt")
    with open(lst, "w") as f:
        for p in paths:
            f.write(f"file '{p}'\n")
    dst = os.path.join(WORK, "base.mp4")
    run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
         "-c", "copy", dst])
    return dst


def build_caps(cues):
    """Дорожка титров с альфой: qtrle-клипы + прозрачные паузы, конкат."""
    from PIL import Image as _I
    blank = os.path.join(WORK, "blank.png")
    _I.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
    parts, t = [], 0.0
    for i, (s, e, png, fin, fout) in enumerate(cues):
        if s > t + 0.02:
            gap = os.path.join(WORK, f"gap_{i}.mov")
            if not os.path.exists(gap):
                run([FF, "-y", "-v", "error", "-loop", "1", "-framerate", "25",
                     "-t", f"{s - t:.3f}", "-i", blank, "-c:v", "qtrle", gap])
            parts.append(gap)
        dur = e - s
        clip = os.path.join(WORK, f"cap_{i:02d}.mov")
        if not os.path.exists(clip):
            vf = "format=rgba"
            if fin:
                vf += ",fade=t=in:st=0:d=0.45:alpha=1"
            if fout:
                vf += f",fade=t=out:st={max(0.0, dur-0.5):.3f}:d=0.5:alpha=1"
            run([FF, "-y", "-v", "error", "-loop", "1", "-framerate", "25",
                 "-t", f"{dur:.3f}", "-i", png, "-vf", vf,
                 "-c:v", "qtrle", clip])
        parts.append(clip)
        t = e
        print(f"  титр {i+1}/{len(cues)}: {s:.2f}–{e:.2f}", flush=True)
    if t < TOTAL:
        tail = os.path.join(WORK, "gap_tail.mov")
        if not os.path.exists(tail):
            run([FF, "-y", "-v", "error", "-loop", "1", "-framerate", "25",
                 "-t", f"{TOTAL - t:.3f}", "-i", blank, "-c:v", "qtrle", tail])
        parts.append(tail)
    lst = os.path.join(WORK, "caps_list.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    dst = os.path.join(WORK, "caps.mov")
    run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
         "-c", "copy", dst])
    return dst


def final(base, cues, dst):
    caps = build_caps(cues)
    fc = ["[1:a]afade=t=in:st=0:d=0.4,afade=t=out:st=203.6:d=5.0[a]",
          "[0:v][2:v]overlay=0:0:format=auto,"
          "fade=t=in:st=0:d=0.8,fade=t=out:st=203.9:d=4.8,format=yuv420p[v]"]
    cmd = [FF, "-y", "-v", "error", "-i", base, "-i", SONG, "-i", caps,
           "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", f"{TOTAL:.3f}", dst]
    run(cmd)


def main():
    os.makedirs(WORK, exist_ok=True)
    cues = make_cues()
    print(f"титров: {len(cues)}")
    if "--cues-only" in sys.argv:
        return
    base = concat(shots())
    dst = os.path.join(OUT, "fontanchik_s_chernym_delfinom_1080p.mp4")
    final(base, cues, dst)
    print("готово:", dst, os.path.getsize(dst) / 1e6, "МБ")


if __name__ == "__main__":
    main()
