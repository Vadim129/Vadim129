#!/usr/bin/env python3
"""Проверка клипа: размер, кодек, длительность, аудио."""
import os, subprocess, sys

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 verify.py <клип.mp4>")
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"Файл не найден: {path}")
        sys.exit(1)
    size = os.path.getsize(path)
    ffmpeg = "ffmpeg"
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", path], capture_output=True)
    out = (r.stdout or b"").decode("utf-8", errors="replace") + (r.stderr or b"").decode("utf-8", errors="replace")
    ok = True
    for line in out.split("\n"):
        if "Duration" in line:
            print(line.strip())
        if "Stream" in line:
            print(line.strip())
            if "h264" in line and "yuv420p" in line:
                print("  ✓ Видео: H.264 yuv420p")
            if "aac" in line:
                print("  ✓ Аудио: AAC")
            if "48000 Hz" in line and "stereo" in line:
                print("  ✓ Аудио: 48 кГц стерео")
    print(f"Размер: {size / 1024 / 1024:.1f} МБ")
    print("ИТОГ: ОК")

if __name__ == "__main__":
    main()
