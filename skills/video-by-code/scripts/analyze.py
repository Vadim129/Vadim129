#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Разбор видео-примера для скилла video-by-code.

    python3 analyze.py ВИДЕО.mp4 [--out АНАЛИЗ]

Создаёт в папке анализа:
  probe.json          — длительность, размер, fps, кодеки (из ffmpeg)
  frames/f01.jpg ...  — кадры 1 кадр/сек (360 px шириной)
  contact_1fps.jpg    — раскадровка плиткой
  spectrogram.png     — спектрограмма звука (если звук есть)
  cuts.json           — кандидаты на склейки сцен (по разнице кадров)
  АНАЛИЗ-черновик.md  — сводка + пустая таблица сцен для заполнения агентом

Зависимости: pip install Pillow numpy imageio-ffmpeg
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def get_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("Нужен imageio-ffmpeg: pip install Pillow numpy imageio-ffmpeg")


def probe(ffmpeg, video):
    p = subprocess.run([ffmpeg, "-hide_banner", "-i", str(video)],
                       capture_output=True, text=True)
    err = p.stderr
    info = {"файл": str(video)}
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    if m:
        info["длительность_с"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5}).*?([\d.]+) fps", err)
    if m:
        info["ширина"], info["высота"] = int(m.group(1)), int(m.group(2))
        info["fps"] = float(m.group(3))
    info["видео"] = "есть" if "Video:" in err else "нет"
    info["аудио"] = "есть" if "Audio:" in err else "нет"
    m = re.search(r"bitrate: (\d+) kb/s", err)
    if m:
        info["битрейт_kbps"] = int(m.group(1))
    v = subprocess.run([ffmpeg, "-hide_banner", "-i", str(video), "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True)
    mm = re.search(r"mean_volume: ([-\d.]+) dB", v.stderr)
    mx = re.search(r"max_volume: ([-\d.]+) dB", v.stderr)
    if mm:
        info["громкость_mean_db"] = float(mm.group(1))
    if mx:
        info["громкость_max_db"] = float(mx.group(1))
    return info


def run(ffmpeg, args):
    subprocess.run([ffmpeg, "-y", "-loglevel", "error"] + args, check=True)


def main():
    ap = argparse.ArgumentParser(description="Разбор видео-примера по кадрам")
    ap.add_argument("video")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    ffmpeg = get_ffmpeg()
    video = Path(args.video)
    if not video.exists():
        sys.exit(f"Файл не найден: {video}")
    out = Path(args.out) if args.out else Path("анализ-" + video.stem)
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    info = probe(ffmpeg, video)
    (out / "probe.json").write_text(json.dumps(info, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    run(ffmpeg, ["-i", str(video), "-vf", "fps=1,scale=360:-1",
                 str(frames_dir / "f%02d.jpg")])
    run(ffmpeg, ["-i", str(video), "-vf", "fps=1,scale=270:480,tile=5x4:padding=4:margin=4",
                 "-frames:v", "1", str(out / "contact_1fps.jpg")])
    has_audio = info.get("аудио") == "есть"
    if has_audio:
        run(ffmpeg, ["-i", str(video), "-lavfi", "showspectrumpic=s=1024x512:legend=0",
                     "-frames:v", "1", str(out / "spectrogram.png")])

    # кандидаты на склейки: маленькие серые кадры 6 fps, средняя разница соседних
    tmp = out / "_cuts"
    tmp.mkdir(exist_ok=True)
    run(ffmpeg, ["-i", str(video), "-vf", "fps=6,scale=96:170,format=gray",
                 str(tmp / "c%04d.png")])
    files = sorted(tmp.glob("c*.png"))
    cuts, prev = [], None
    diffs = []
    for i, f in enumerate(files):
        arr = np.asarray(Image.open(f), dtype=float)
        if prev is not None:
            diffs.append((i / 6, float(np.abs(arr - prev).mean())))
        prev = arr
    if diffs:
        vals = np.array([d for _, d in diffs])
        thr = max(vals.mean() + vals.std() * 1.6, np.percentile(vals, 92))
        last = -1.0
        for t, d in diffs:
            if d >= thr and t - last > 0.4:
                cuts.append({"время_с": round(t, 2), "сила": round(d, 1)})
                last = t
    (out / "cuts.json").write_text(json.dumps(
        {"порог": round(float(thr), 2) if diffs else None, "склейки_кандидаты": cuts},
        ensure_ascii=False, indent=2), encoding="utf-8")
    for f in tmp.glob("*"):
        f.unlink()
    tmp.rmdir()

    lines = [
        f"# Анализ примера: {video.name}", "",
        f"- Длительность: {info.get('длительность_с', '?')} с, "
        f"размер: {info.get('ширина', '?')}×{info.get('высота', '?')}, "
        f"fps: {info.get('fps', '?')}, аудио: {info.get('аудио', '?')}",
        f"- Кандидаты на склейки (с): {[c['время_с'] for c in cuts]}",
        "- Кадры: frames/, сводная: contact_1fps.jpg"
        + (", звук: spectrogram.png" if has_audio else ""), "",
        "## Сцены (заполняет агент, глядя на кадры)", "",
        "| № | Время | Что на экране (текст дословно) | Эффект / движение | Фон |",
        "|---|---|---|---|---|",
        "| 1 | 0.0–? |  |  |  |", "",
        "## Сквозные элементы", "",
        "- Оверлей (REC/таймкод/подпись/прогресс): ",
        "- Палитра (фон/текст/акцент, hex примерно): ",
        "- Шрифт (характер): ", "- Звук (ритм, удары на склейках): ", "",
        "## Что меняем в аналоге", "",
        "- Подпись/автор: ", "- Тексты: ", "- Длительность/размер: ",
    ]
    (out / "АНАЛИЗ-черновик.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"анализ": str(out), **info,
                      "склеек_кандидатов": len(cuts)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
