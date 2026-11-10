#!/usr/bin/env python3
"""Рендер клипа Мэта по конфигу mat-*.json.

Использование: python3 render.py mat-bot/mat-<тема>.json --out outNN

Соблюдает правила проекта:
  * аватар — всегда из поля "robot" конфига (mat-bot/assets/robot.jpg);
  * одна реплика = одна сцена, облако с полным текстом реплики;
  * голос ставится на свою сцену (start + voice_at) с усилением gain;
  * музыка — chiptune из конфига (bpm/volume), а не случайный синус.
"""
import json
import math
import os
import struct
import subprocess
import sys
import wave

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 24

FFMPEG = "/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v9.0.2"
if not os.path.exists(FFMPEG):
    try:
        import imageio_ffmpeg
        FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG = "ffmpeg"

BG_TOP = (26, 12, 36)
BG_BOTTOM = (58, 10, 18)
ACCENT = (255, 92, 64)


def load_font(sz, bold=True):
    names = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
         "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"] if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
    )
    for p in names:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def gradient():
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        c = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)
    return img


def rays(img, speed=0.0, alpha_max=18):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx, cy = W // 2, int(H * 0.38)
    maxr = int(math.hypot(W, H))
    for i in range(24):
        ang = (i / 24) * 2 * math.pi + speed
        for r in range(0, maxr, 14):
            x = int(cx + math.cos(ang) * r)
            y = int(cy + math.sin(ang) * r)
            if 0 <= x < W and 0 <= y < H:
                a = int(alpha_max * (1 - r / maxr))
                if a > 0:
                    draw.point((x, y), fill=(255, 180, 140, a))
    return Image.alpha_composite(img.convert("RGBA"), overlay.filter(ImageFilter.GaussianBlur(2)))


def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        probe = (cur + " " + w).strip()
        if draw.textlength(probe, font=font) <= max_w or not cur:
            cur = probe
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def rounded(img, radius):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1], radius=radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def make_scene_frame(scene, idx, t_local, cfg):
    img = gradient()
    img = rays(img, speed=idx * 0.35 + t_local * 0.15)

    # лёгкое «дыхание» камеры — наезд внутри сцены
    if scene.get("dur"):
        zoom = 1.0 + 0.04 * min(1.0, t_local / max(scene["dur"], 0.001))
        if zoom > 1.001:
            cw, ch = int(W / zoom), int(H / zoom)
            img = img.crop(((W - cw) // 2, (H - ch) // 2, (W + cw) // 2, (H + ch) // 2)).resize((W, H), Image.LANCZOS)

    draw = ImageDraw.Draw(img)

    # шапка
    title = cfg.get("title", "Мэт")
    f_title = load_font(96)
    tw = draw.textlength(title, font=f_title)
    draw.text(((W - tw) / 2, 96), title, font=f_title, fill=(255, 255, 255))
    subtitle = scene.get("subtitle") or cfg.get("subtitle", "")
    if subtitle:
        f_sub = load_font(38, bold=False)
        tw = draw.textlength(subtitle, font=f_sub)
        draw.text(((W - tw) / 2, 212), subtitle, font=f_sub, fill=(255, 190, 170))

    # аватар Мэта — настоящая фотография из конфига
    robot_path = scene.get("robot") or cfg.get("robot") or "mat-bot/assets/robot.jpg"
    if os.path.exists(robot_path):
        robot = Image.open(robot_path).convert("RGB")
        side = 640
        rw, rh = robot.size
        scale = side / min(rw, rh)
        robot = robot.resize((max(1, int(rw * scale)), max(1, int(rh * scale))), Image.LANCZOS)
        rw, rh = robot.size
        if rw > side or rh > side:
            left = (rw - side) // 2
            top = (rh - side) // 2
            robot = robot.crop((left, top, left + side, top + side))
        rw, rh = robot.size

        card = rounded(robot, 44)
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        rx, ry = (W - rw) // 2, 470
        sd.rounded_rectangle([rx - 12, ry - 12, rx + rw + 12, ry + rh + 12], radius=52, fill=(0, 0, 0, 150))
        img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(18)))
        img.paste(card, (rx, ry), card)
        draw = ImageDraw.Draw(img)

    # стикеры tag-стиля под портретом
    tags = scene.get("tags") or []
    if tags:
        f_tag = load_font(34)
        x = 90
        y = 1180
        for tag in tags[:3]:
            label = f"#{tag}"
            tw_ = draw.textlength(label, font=f_tag)
            bw = int(tw_ + 44)
            draw.rounded_rectangle([x, y, x + bw, y + 62], radius=31, fill=(255, 255, 255, 235))
            draw.text((x + 22, y + 12), label, font=f_tag, fill=(120, 20, 30))
            x += bw + 18

    # облако с полным текстом реплики
    text = (scene.get("text") or "").replace("\u0301", "")
    f_body = load_font(48)
    max_text_w = 880
    lines = wrap(draw, text, f_body, max_text_w) if text else []
    line_h = 64
    pad_x, pad_y = 44, 40
    bw = max_text_w + pad_x * 2 if lines else 0
    bh = len(lines) * line_h + pad_y * 2
    max_w = max((draw.textlength(l, font=f_body) for l in lines), default=0)
    bw = int(min(bw, max_w + pad_x * 2))
    bx = (W - bw) // 2
    by = H - bh - 120

    cloud = Image.new("RGBA", (bw, bh), (255, 255, 255, 246))
    cloud = rounded(cloud, 40)
    img.paste(cloud, (bx, by), cloud)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=40, outline=(255, 120, 90), width=4)
    y = by + pad_y
    for line in lines:
        lw = draw.textlength(line, font=f_body)
        draw.text((bx + (bw - lw) / 2, y), line, font=f_body, fill=(28, 20, 24))
        y += line_h

    return img.convert("RGB")


def chiptune(path, duration, bpm=132, volume=0.35):
    """Простой chiptune-луп: квадратные волны, бас + арпеджио, 132 BPM."""
    rate = 48000
    frames = int(duration * rate)
    step = 60.0 / bpm / 4.0  # шестнадцатая
    # ля-минор: тоника, терция, квинта, октава
    notes = [220.00, 261.63, 329.63, 440.00, 329.63, 261.63]
    bass = [110.00, 110.00, 87.31, 98.00]
    buf = [0.0] * frames
    i = 0
    t = 0.0
    while i < frames:
        n = int(step * rate)
        f = notes[(int(t / step)) % len(notes)]
        fb = bass[int(t / (step * 4)) % len(bass)]
        for k in range(n):
            if i + k >= frames:
                break
            tt = k / rate
            env = min(1.0, (n - k) / (rate * 0.012)) if n - k < rate * 0.012 else 1.0
            sq = 1.0 if math.sin(2 * math.pi * f * tt) >= 0 else -1.0
            sb = 1.0 if math.sin(2 * math.pi * fb * tt) >= 0 else -1.0
            buf[i + k] = (0.55 * sq * env + 0.45 * sb * env)
        i += n
        t += step
    # музыка — фон: держим её заметно тише голоса Мэта
    amp = 0.115 * volume / 0.35
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        data = bytearray()
        for s in buf:
            v = int(max(-1.0, min(1.0, s * amp)) * 32767)
            data += struct.pack("<hh", v, v)
        wf.writeframes(bytes(data))


def audio_duration(path):
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            hms = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = hms.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 render.py <конфиг.json> --out <папка>")
        sys.exit(1)

    cfg_path = sys.argv[1]
    out_dir = "out"
    if "--out" in sys.argv:
        out_dir = sys.argv[sys.argv.index("--out") + 1]

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs("frames", exist_ok=True)

    cfg = json.load(open(cfg_path, encoding="utf-8"))
    scenes = cfg["scenes"]
    base = os.path.dirname(os.path.abspath(cfg_path))
    voice_dir = cfg.get("voice_dir", "voice01")
    if not os.path.isabs(voice_dir):
        voice_dir = os.path.join(base, voice_dir)

    robot_path = cfg.get("robot", "assets/robot.jpg")
    if not os.path.isabs(robot_path):
        cfg["robot"] = os.path.join(base, robot_path)

    print(f"Конфиг: {cfg_path}")
    print(f"Сцен: {len(scenes)}")
    print(f"Аватар: {cfg['robot']}")
    print(f"Выход: {out_dir}")

    # тайминги: сцена = 0.45 + голос + 0.6 (правило 4)
    t = 0.0
    timeline = []
    for si, scene in enumerate(scenes, 1):
        voice = scene.get("voice")
        vpath = os.path.join(voice_dir, voice) if voice else None
        vdur = audio_duration(vpath) if vpath and os.path.exists(vpath) else 0.0
        if not scene.get("dur") or vdur:
            scene["dur"] = round(0.45 + vdur + 0.6, 2) if vdur else float(scene.get("dur", 1.5))
        scene["start"] = round(t, 2)
        scene["voice_at"] = 0.45 if vdur else None
        timeline.append((scene, vpath, vdur))
        t += scene["dur"]
    total = round(t, 2)
    print(f"Длительность: {total} сек")

    frame_list = []
    for si, (scene, _, _) in enumerate(timeline, 1):
        img = make_scene_frame(scene, si, 0, cfg)
        fn = f"frames/scene_{si:02d}.png"
        img.save(fn)
        frame_list.append((fn, scene["dur"]))
        print(f"  Сцена {si}: {fn} ({scene['dur']} сек)")

    with open("frames/list.txt", "w") as f:
        for fn, dur in frame_list:
            f.write(f"file '{os.path.abspath(fn)}'\n")
            f.write(f"duration {dur}\n")
        f.write(f"file '{os.path.abspath(frame_list[-1][0])}'\n")

    tmp_video = os.path.join(out_dir, "tmp_video.mp4")
    subprocess.run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", "frames/list.txt",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-r", str(FPS), tmp_video
    ], check=True)

    music_cfg = cfg.get("music") or {}
    music_path = os.path.join(out_dir, "music.wav")
    chiptune(music_path,
             total,
             bpm=music_cfg.get("bpm", 132),
             volume=music_cfg.get("volume", 0.35))

    inputs = ["-i", os.path.abspath(tmp_video), "-i", os.path.abspath(music_path)]
    filters = []
    labels = []
    idx = 2
    for scene, vpath, vdur in timeline:
        if vpath and os.path.exists(vpath):
            inputs.extend(["-i", os.path.abspath(vpath)])
            start_ms = int(round((scene["start"] + (scene.get("voice_at") or 0)) * 1000))
            gain = scene.get("gain", 1.45)
            filters.append(
                f"[{idx}:a]adelay={start_ms}|{start_ms},volume={gain},aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[v{idx}]"
            )
            labels.append(f"[v{idx}]")
            idx += 1

    filters.append("[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[mus]")
    labels.append("[mus]")
    filters.append("".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0,alimiter=limit=0.95[aout]")

    out_mp4 = os.path.join(out_dir, "клип.mp4")
    subprocess.run([
        FFMPEG, "-y", *inputs,
        "-filter_complex", ";".join(filters),
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-t", str(total), "-movflags", "+faststart", os.path.abspath(out_mp4)
    ], check=True)

    os.remove(tmp_video)
    os.remove(music_path)
    print(f"\nГотово: {out_mp4}")
    print(f"Размер: {os.path.getsize(out_mp4) / 1024 / 1024:.1f} МБ")


if __name__ == "__main__":
    main()
