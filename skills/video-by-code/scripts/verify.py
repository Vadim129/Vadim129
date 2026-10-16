#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка готового клипа для скилла video-by-code.

    python3 verify.py КЛИП.mp4 [--expect config.json] [--out DIR]

Проверяет: длительность, размер, fps, наличие и громкость звука;
делает раскадровку и обложку; пишет отчёт.json. Код выхода 1, если
есть проваленные проверки (длительность/размер/fps сверяются с --expect,
если задан; иначе просто сообщаются).

Зависимости: pip install Pillow numpy imageio-ffmpeg
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


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
    info = {}
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    if m:
        info["длительность_с"] = round(int(m.group(1)) * 3600 + int(m.group(2)) * 60
                                       + float(m.group(3)), 2)
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5}).*?([\d.]+) fps", err)
    if m:
        info.update({"ширина": int(m.group(1)), "высота": int(m.group(2)),
                     "fps": float(m.group(3))})
    info["аудио"] = "есть" if "Audio:" in err else "нет"
    info["размер_байт"] = Path(video).stat().st_size
    if info["аудио"] == "есть":
        v = subprocess.run([ffmpeg, "-hide_banner", "-i", str(video), "-af", "volumedetect",
                            "-f", "null", "-"], capture_output=True, text=True)
        mm = re.search(r"mean_volume: ([-\d.]+) dB", v.stderr)
        mx = re.search(r"max_volume: ([-\d.]+) dB", v.stderr)
        if mm:
            info["громкость_mean_db"] = float(mm.group(1))
        if mx:
            info["громкость_max_db"] = float(mx.group(1))
    return info


def main():
    ap = argparse.ArgumentParser(description="Проверка клипа + раскадровка")
    ap.add_argument("video")
    ap.add_argument("--expect", default=None, help="JSON-конфиг сценария (эталон)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    ffmpeg = get_ffmpeg()
    video = Path(args.video)
    out = Path(args.out) if args.out else video.parent
    out.mkdir(parents=True, exist_ok=True)
    info = probe(ffmpeg, video)

    checks = []

    def check(name, ok, detail=""):
        checks.append({"проверка": name, "ок": bool(ok), "детали": detail})

    check("файл открывается ffmpeg", "длительность_с" in info)
    expect = None
    if args.expect:
        expect = json.loads(Path(args.expect).read_text(encoding="utf-8"))
        want_s = sum(float(s.get("duration", 1.8)) for s in expect["scenes"])
        check("длительность ≈ сценарию",
              abs(info.get("длительность_с", 0) - want_s) <= 0.15,
              f"{info.get('длительность_с')} vs {want_s:.2f}")
        check("размер кадра",
              (info.get("ширина"), info.get("высота"))
              == (int(expect.get("width", 1080)), int(expect.get("height", 1920))),
              f"{info.get('ширина')}x{info.get('высота')}")
        check("fps", abs(info.get("fps", 0) - int(expect.get("fps", 30))) < 0.6,
              str(info.get("fps")))
    check("звук есть", info.get("аудио") == "есть")
    if info.get("аудио") == "есть":
        check("звук не тихий и без клиппинга",
              -30 <= info.get("громкость_mean_db", -99) and info.get("громкость_max_db", 0) <= 0.0,
              f"mean {info.get('громкость_mean_db')} dB, max {info.get('громкость_max_db')} dB")

    dur = info.get("длительность_с", 1)
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-ss", str(max(0, dur * 0.88)),
                    "-i", str(video), "-frames:v", "1", str(out / "обложка.png")], check=True)
    cols = 5
    rows = max(1, round(dur / cols))
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(video),
                    "-vf", f"fps=1,scale=270:480,tile={cols}x{rows}:padding=4:margin=4",
                    "-frames:v", "1", str(out / "раскадровка.png")], check=True)

    ok_all = all(c["ок"] for c in checks)
    report = {"видео": str(video), **info, "проверки": checks, "всё_ок": ok_all}
    (out / "отчёт.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    for c in checks:
        print(("✔ " if c["ок"] else "✘ ") + c["проверка"] + (f" ({c['детали']})" if c["детали"] else ""))
    print("ИТОГ:", "ОК" if ok_all else "ЕСТЬ ЗАМЕЧАНИЯ", "->", out / "отчёт.json")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
