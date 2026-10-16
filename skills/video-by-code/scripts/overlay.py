#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Анимация ПОВЕРХ готового видео (скилл video-by-code).

    python3 overlay.py overlay.json [--out DIR]

overlay.json: базовое видео, текстовые плашки по времени (cues),
«плюсы»-списки с поочерёдным появлением, голосовые вставки, звуковые
эффекты и приглушение исходного звука под голосом. Кадры оверлея
рисуются Pillow (RGBA) и накладываются ffmpeg-ом; исходное видео
и его звук сохраняются.

Пример конфига — в проектах, использующих скилл (tesla-mamaika/).
Зависимости: pip install Pillow numpy imageio-ffmpeg
"""

import argparse
import json
import math
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SKILL_DIR = Path(__file__).resolve().parent.parent
FONT_DIR = SKILL_DIR / "assets" / "fonts"
SR = 48000

_cache = {}


def font(name, size):
    key = (name, int(size))
    if key not in _cache:
        _cache[key] = ImageFont.truetype(str(FONT_DIR / name), int(size))
    return _cache[key]


def display(size):
    return font("Montserrat_900Black.ttf", size)


def mono(size, bold=False):
    return font("JetBrainsMono_700Bold.ttf" if bold else "JetBrainsMono_400Regular.ttf", size)


def hex2rgb(s, default=(255, 255, 255)):
    if not isinstance(s, str):
        return default
    s = s.lstrip("#")
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return default


def clamp01(x):
    return min(1.0, max(0.0, x))


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def pop(x):
    x = clamp01(x)
    return 1 + 2.2 * ((x - 1) ** 3) + 1.2 * ((x - 1) ** 2) if x < 1 else 1.0


def get_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("Нужны зависимости: pip install Pillow numpy imageio-ffmpeg")


def probe(ffmpeg, video):
    err = subprocess.run([ffmpeg, "-hide_banner", "-i", str(video)],
                         capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5}).*?([\d.]+) fps", err)
    w, h, fps = (int(m.group(1)), int(m.group(2)), float(m.group(3))) if m else (1280, 720, 24)
    return dur, w, h, fps


# ------------------------------------------------------------------ рисование плашек
def draw_line(layer, cx, y, text, size, color, bg=None, scale=1.0, stroke=7):
    d = ImageDraw.Draw(layer)
    fnt = display(max(10, size * scale))
    box = d.textbbox((0, 0), text, font=fnt, stroke_width=stroke)
    tw, th = box[2] - box[0], box[3] - box[1]
    x = cx - tw / 2
    if bg:
        pad_x, pad_y = 30, 14
        d.rounded_rectangle([x - pad_x, y - pad_y, x + tw + pad_x, y + th + pad_y],
                            radius=22, fill=hex2rgb(bg) + (255,))
        d.text((x - box[0], y - box[1]), text, font=fnt, fill=color + (255,))
    else:
        d.text((x - box[0] + 4, y - box[1] + 5), text, font=fnt, fill=(0, 0, 0, 200),
               stroke_width=stroke, stroke_fill=(0, 0, 0, 200))
        d.text((x - box[0], y - box[1]), text, font=fnt, fill=color + (255,),
               stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    return th + 18


def draw_cue(size_wh, cue, t):
    """Один cue -> RGBA-слой на весь кадр (или None)."""
    start, end = float(cue.get("start", 0)), float(cue.get("end", 0))
    if not (start <= t <= end):
        return None
    w, h = size_wh
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    fade_in = ease_out((t - start) / 0.45)
    fade_out = clamp01((end - t) / 0.4)
    alpha = min(fade_in, fade_out)
    cx = int(cue.get("cx", w // 2))
    y = int(cue.get("y", 54))
    scale_in = pop((t - start) / 0.45) if cue.get("anim", "pop") == "pop" else 1.0
    slide = (1 - ease_out((t - start) / 0.45)) * 46 if cue.get("anim") == "slide" else 0
    for line in cue.get("lines") or []:
        delay = float(line.get("delay", 0))
        if t < start + delay:
            continue
        ls = pop((t - start - delay) / 0.4) if cue.get("anim", "pop") == "pop" else 1.0
        color = hex2rgb(line.get("color", "#FFFFFF"))
        y += draw_line(layer, cx, int(y + slide), line["text"], int(line.get("size", 64)),
                       color, line.get("bg"), scale=ls * (scale_in if delay == 0 else 1.0))
        y += int(line.get("gap", 6))
    items_x = int(cue.get("items_x", 84))
    for item in cue.get("items") or []:
        at = float(item.get("at", start))
        if t < at:
            continue
        ip = pop((t - at) / 0.35)
        r = int(27 * ip)
        iy = y + 16
        if r > 4:
            d.ellipse([items_x, iy, items_x + 2 * r, iy + 2 * r], fill=(55, 224, 90, 255),
                      outline=(0, 0, 0, 255), width=4)
            pf = mono(int(40 * ip), bold=True)
            d.text((items_x + r - 13 * ip, iy + r - 24 * ip), "+", font=pf,
                   fill=(255, 255, 255, 255))
        fnt = display(int(46 * ip))
        d.text((items_x + 76, iy + 2), item["text"], font=fnt, fill=(255, 255, 255, 255),
               stroke_width=6, stroke_fill=(0, 0, 0, 255))
        y += 72
    badge = cue.get("badge")
    if badge and t >= start + float(badge.get("delay", 0)):
        fnt = mono(26, bold=True)
        tw = d.textbbox((0, 0), badge["text"], font=fnt)[2]
        bx, by = int(badge.get("x", 44)), int(badge.get("y", 40))
        d.rounded_rectangle([bx, by, bx + tw + 40, by + 46], radius=23,
                            fill=hex2rgb(badge.get("bg", "#E82127")) + (235,))
        d.text((bx + 20, by + 8), badge["text"], font=fnt, fill=(255, 255, 255, 255))
    if alpha < 1.0:
        a = layer.getchannel("A").point(lambda v: int(v * alpha))
        layer.putalpha(a)
    return layer


# ------------------------------------------------------------------ звук-эффекты
def _add(track, sig, at_sec):
    at = int(at_sec * SR)
    end = min(len(track), at + len(sig))
    if end > at:
        track[at:end] += sig[:end - at]


def _event_sig(kind, noise):
    if kind == "pop":
        tt = np.arange(int(SR * 0.12)) / SR
        return np.sin(2 * np.pi * (480 - 2600 * tt) * tt) * np.exp(-tt * 30) * 0.45
    if kind == "whoosh":
        tt = np.arange(int(SR * 0.55)) / SR
        env = np.sin(np.pi * np.clip(tt / 0.55, 0, 1)) ** 2
        return noise[:len(tt)] * env * 0.20
    if kind == "boom":
        tt = np.arange(int(SR * 0.35)) / SR
        return np.sin(2 * np.pi * (140 * np.exp(-tt * 9) + 44) * tt) * np.exp(-tt * 9) * 0.6
    if kind == "ping":
        tt = np.arange(int(SR * 0.3)) / SR
        return np.sin(2 * np.pi * 1568 * tt) * np.exp(-tt * 16) * 0.35
    if kind == "chord":
        tt = np.arange(int(SR * 1.2)) / SR
        sig = sum(np.sin(2 * np.pi * f * tt) for f in (261.63, 329.63, 392.0)) / 3
        return sig * np.exp(-tt * 2.4) * 0.4
    return np.zeros(1)


def make_sfx(path, total_s, events):
    mix = np.zeros(int(SR * total_s))
    noise = np.random.default_rng(5).standard_normal(len(mix) + SR)
    for ev in events or []:
        _add(mix, _event_sig(ev.get("type", "pop"), noise) * float(ev.get("gain", 1.0)),
             float(ev.get("at", 0)))
    mix = np.tanh(mix)
    pcm = (mix * 0.8 * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(np.repeat(pcm[:, None], 2, axis=1).tobytes())


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="Анимация поверх готового видео")
    ap.add_argument("config")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    ffmpeg = get_ffmpeg()
    cfg_path = Path(args.config).resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    base_dir = cfg_path.parent
    src = Path(cfg["video"])
    if not src.is_absolute():
        src = base_dir / src
    dur, w, h, fps = probe(ffmpeg, src)
    total_frames = int(dur * fps) + 1
    out = Path(args.out) if args.out else base_dir / "out"
    out.mkdir(parents=True, exist_ok=True)
    print(f"источник: {w}x{h}, {fps:.3f} fps, {dur:.2f} c, кадров {total_frames}")

    inter = out / "_overlay.mp4"
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(src),
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-r", f"{fps:.5f}",
           "-i", "-", "-filter_complex", "[0:v][1:v]overlay=0:0,format=yuv420p",
           "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(inter)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    cues = cfg.get("cues") or []
    for frame in range(total_frames):
        t = frame / fps
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        for cue in cues:
            layer = draw_cue((w, h), cue, t)
            if layer is not None:
                canvas = Image.alpha_composite(canvas, layer)
        proc.stdin.write(canvas.tobytes())
        if frame % 240 == 0:
            print(f"кадр {frame}/{total_frames}", flush=True)
    proc.stdin.close()
    proc.wait()

    sfx = out / "_sfx.wav"
    make_sfx(sfx, dur, cfg.get("sfx"))
    final = out / cfg.get("output", "клип.mp4")
    voice = cfg.get("voice") or []
    inputs = ["-i", str(inter), "-i", str(src), "-i", str(sfx)]
    filters = [f"[1:a]volume={float(cfg.get('base_volume', 0.35))}[orig]",
               "[2:a]volume=0.6[sfx]"]
    labels = ["[orig]", "[sfx]"]
    for i, v in enumerate(voice):
        vp = Path(v["file"])
        if not vp.is_absolute():
            vp = base_dir / vp
        inputs += ["-i", str(vp)]
        delay = int(float(v.get("at", 0)) * 1000)
        filters.append(f"[{i + 3}:a]adelay={delay}|{delay},volume={float(v.get('gain', 1.2))}[v{i}]")
        labels.append(f"[v{i}]")
    filters.append("".join(labels) + f"amix=inputs={len(labels)}:duration=first:"
                     "normalize=0,alimiter=limit=0.95[a]")
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", *inputs,
                    "-filter_complex", ";".join(filters),
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                    str(final)], check=True)
    inter.unlink(missing_ok=True)
    sfx.unlink(missing_ok=True)
    print("готово:", final)


if __name__ == "__main__":
    main()
