#!/usr/bin/env python3
"""Рендер клипа Мэта по конфигу mat-*.json.
Использование: python3 render.py mat-bot/mat-побитый.json --out outNN
"""
import json, math, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920
FPS = 24
FFMPEG = None

FFMPEG = "/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v9.0.2"

def load_font(sz):
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ]:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()

def rays(img, color, speed=0.0):
    draw = ImageDraw.Draw(img, "RGBA")
    cx, cy = W // 2, H // 2
    for i in range(30):
        ang = (i / 30) * 2 * math.pi + speed
        for r in range(0, int(math.hypot(W, H)), 10):
            x = int(cx + math.cos(ang) * r)
            y = int(cy + math.sin(ang) * r)
            if 0 <= x < W and 0 <= y < H:
                alpha = int(20 * (1 - r / math.hypot(W, H)))
                if alpha > 0:
                    draw.point((x, y), fill=(*color, alpha))
    return img.filter(ImageFilter.GaussianBlur(1))

def make_scene_frame(scene, idx, t_local):
    """Один кадр сцены в момент t_local (от начала сцены)."""
    bg = scene.get("bg", "#ff6b6b")
    img = Image.new("RGB", (W, H), bg)
    col = tuple(int(bg.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    img = rays(img, col, speed=idx * 0.3 + t_local * 0.2)

    draw = ImageDraw.Draw(img)
    f_big = load_font(70)
    f_mid = load_font(40)

    # "СЦЕНА N" вверху
    scene_txt = f"СЦЕНА {idx}"
    tw = draw.textlength(scene_txt, font=f_big)
    draw.text(((W - tw) / 2, 80), scene_txt, font=f_big, fill="white")

    # Белая карточка-заголовка
    card_w, card_h = 860, 220
    card_x = (W - card_w) // 2
    card_y = 220
    card = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 230))
    card = card.filter(ImageFilter.GaussianBlur(3))
    img.paste(card, (card_x, card_y), card)
    draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=24, outline=(200, 200, 200), width=3)

    title = "Мэт побитый"
    tw = draw.textlength(title, font=f_big)
    draw.text((card_x + (card_w - tw) // 2, card_y + 40), title, font=f_big, fill=(60, 60, 60))
    sub = scene.get("subtitle", "")
    tw = draw.textlength(sub, font=f_mid)
    draw.text((card_x + (card_w - tw) // 2, card_y + 110), sub, font=f_mid, fill=(100, 100, 100))

    # Облако с репликой
    text = scene["text"]
    tw = draw.textlength(text, font=f_mid)
    bubble_w = min(int(tw + 120), W - 120)
    bubble_h = 140
    bubble_x = (W - bubble_w) // 2
    bubble_y = H - 420
    bubble = Image.new("RGBA", (bubble_w, bubble_h), (255, 255, 255, 240))
    bubble = bubble.filter(ImageFilter.GaussianBlur(4))
    img.paste(bubble, (bubble_x, bubble_y), bubble)
    draw.rounded_rectangle([bubble_x, bubble_y, bubble_x + bubble_w, bubble_y + bubble_h], radius=30, outline=(180, 180, 180), width=3)
    tw = draw.textlength(text, font=f_mid)
    draw.text((bubble_x + (bubble_w - tw) // 2, bubble_y + 45), text, font=f_mid, fill=(40, 40, 40))

    # Робот снизу
    robot_path = scene.get("robot", "mat-bot/assets/robot.jpg")
    if os.path.exists(robot_path):
        robot = Image.open(robot_path).convert("RGB")
        rw, rh = robot.size
        scale = min(500 / rw, 500 / rh)
        robot = robot.resize((int(rw * scale), int(rh * scale)), Image.LANCZOS)
        rw, rh = robot.size
        robot_x = (W - rw) // 2
        robot_y = H - rh - 60
        img.paste(robot, (robot_x, robot_y))

    # Стикеры
    sticker_colors = ["#ff6b6b", "#4ecdc4", "#45b7d1", "#f9ca24", "#ff9ff3", "#54a0ff"]
    for i, scolor in enumerate(sticker_colors):
        sx = 40 + i * 150
        sy = 300 + (i % 2) * 60
        st = Image.new("RGBA", (90, 90), tuple(int(scolor.lstrip('#')[i2:i2+2], 16) for i2 in (0, 2, 4)) + (200,))
        st = st.filter(ImageFilter.GaussianBlur(2))
        img.paste(st, (sx, sy), st)

    return img

def main():
    global FFMPEG
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
    voice_dir = os.path.join(os.path.dirname(cfg_path), cfg.get("voice_dir", "voice01"))

    print(f"Конфиг: {cfg_path}")
    print(f"Сцен: {len(scenes)}")
    print(f"Выход: {out_dir}")
    print(f"FFmpeg: {FFMPEG}")

    # Генерируем по одному кадру на сцену
    frame_list = []
    for si, scene in enumerate(scenes, 1):
        img = make_scene_frame(scene, si, 0)
        fn = f"frames/scene_{si:02d}.png"
        img.save(fn)
        frame_list.append((fn, scene["dur"], scene.get("voice")))
        print(f"  Сцена {si}: {fn} ({scene['dur']} сек)")

    # Список для concat
    with open("frames/list.txt", "w") as f:
        for fn, dur, voice in frame_list:
            abspath = os.path.abspath(fn)
            f.write(f"file '{abspath}'\n")
            f.write(f"duration {dur}\n")
        # Последний кадр повторяем
        abspath = os.path.abspath(frame_list[-1][0])
        f.write(f"file '{abspath}'\n")

    # Собираем видео
    tmp_video = os.path.join(out_dir, "tmp_video.mp4")
    cmd = [
        FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", "frames/list.txt",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-r", str(FPS), tmp_video
    ]
    print("Собираю видео...")
    subprocess.run(cmd, check=True)

    # Аудио: голоса + музыка chiptune (bpm 132, volume 0.35)
    audio_inputs = []
    filter_parts = []
    for i, (fn, dur, voice) in enumerate(frame_list):
        if voice:
            voice_path = os.path.join(voice_dir, voice)
            if os.path.exists(voice_path):
                audio_inputs.extend(["-i", os.path.abspath(voice_path)])
                filter_parts.append(f"[{i+1}:a]")

    if not filter_parts:
        print("Нет аудио файлов!")
        sys.exit(1)

    # Музыка chiptune: синус 440 Гц, 60 сек, громкость 0.35
    music_path = os.path.join(out_dir, "music.mp3")
    cmd_music = [
        FFMPEG, "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=60",
        "-af", "volume=0.35",
        music_path
    ]
    subprocess.run(cmd_music, check=True)
    audio_inputs.extend(["-i", os.path.abspath(music_path)])
    music_idx = len(frame_list) + 1
    filter_parts.append(f"[{music_idx}:a]")

    # Объединяем аудио: голоса + музыка
    n_audio = len(filter_parts)
    filter_str = "".join(filter_parts) + f"amix=inputs={n_audio}:duration=longest:normalize=0[out]"

    out_mp4 = os.path.join(out_dir, "клип.mp4")
    cmd2 = [
        FFMPEG, "-y",
        "-i", os.path.abspath(tmp_video),
    ] + audio_inputs + [
        "-filter_complex", filter_str,
        "-map", "0:v", "-map", "[out]",
        "-c:v", "copy",
        "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-shortest", os.path.abspath(out_mp4)
    ]
    print("Добавляю аудио...")
    subprocess.run(cmd2, check=True)

    # Убираем временные
    os.remove(tmp_video)
    os.remove(music_path)

    # Информация
    print(f"\nГотово: {out_mp4}")
    print(f"Размер: {os.path.getsize(out_mp4) / 1024 / 1024:.1f} МБ")

if __name__ == "__main__":
    main()
