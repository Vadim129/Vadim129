# -*- coding: utf-8 -*-
"""Точная карта вокала: Demucs отделяет голос, по нему считаем, где девушка может быть в кадре.

Выход: ci/vocal_map.txt (по 0,5 с), ci/vocal_map.json (участки без вокала = проигрыши),
ci/instrumental.mp3 (минус — пригодится для монтажа).
"""
import json
import os
import subprocess

import numpy as np
import soundfile as sf

SONG_ID = "1yGs88oWAw6TP-EdskGqH41Sjc2m0M309"
WORK = "/tmp/vocalmap"
MP3 = f"{WORK}/song.mp3"


def get_song():
    os.makedirs(WORK, exist_ok=True)
    if os.path.exists(MP3) and os.path.getsize(MP3) > 1_000_000:
        return MP3
    for cmd in (["gdown", SONG_ID, "-O", MP3],
                ["curl", "-sL", "-o", MP3,
                 f"https://drive.usercontent.google.com/download?id={SONG_ID}&export=download&confirm=t"]):
        subprocess.run(cmd, capture_output=True)
        if os.path.exists(MP3) and os.path.getsize(MP3) > 1_000_000:
            return MP3
    raise SystemExit("песня не скачалась")


def main():
    mp3 = get_song()
    subprocess.run(["python3", "-m", "demucs.separate", "-n", "htdemucs",
                    "--two-stems", "vocals", "-o", f"{WORK}/stems", mp3], check=True)
    vocal = f"{WORK}/stems/htdemucs/song/vocals.wav"
    inst = f"{WORK}/stems/htdemucs/song/no_vocals.wav"
    y, sr = sf.read(vocal)
    if y.ndim > 1:
        y = y.mean(axis=1)
    dur = len(y) / sr

    step = 0.25
    n = int(dur / step)
    rms = np.array([np.sqrt(np.mean(y[int(i * step * sr):int((i + 1) * step * sr)] ** 2) + 1e-12)
                    for i in range(n)])
    db = 20 * np.log10(rms + 1e-12)

    # порог: голос считается звучащим, если он выше -45 дБ и выше 30-го процентиля трека
    floor = max(-45.0, float(np.percentile(db, 30)) - 6)
    active = db > floor

    # сглаживание 0,5 с
    k = 2
    act = np.convolve(active.astype(float), np.ones(k) / k, mode="same") > 0.5

    runs, start = [], None
    for i, a in enumerate(act):
        t = i * step
        if not a and start is None:
            start = t
        elif a and start is not None:
            if t - start >= 3.0:
                runs.append((round(start, 2), round(t, 2)))
            start = None
    if start is not None and dur - start >= 3.0:
        runs.append((round(start, 2), round(dur, 2)))

    ws = os.environ.get("GITHUB_WORKSPACE", ".")
    os.makedirs(f"{ws}/ci", exist_ok=True)
    with open(f"{ws}/ci/vocal_map.txt", "w") as f:
        f.write(f"# порог {floor:.1f} дБ, шаг {step} с, длительность {dur:.2f} с\n")
        f.write("# ПРОИГРЫШИ (вокала нет) >= 3 с — только здесь в кадре девушка:\n")
        for a, b in runs:
            f.write(f"#   {a:7.2f} – {b:7.2f}  ({b - a:5.2f} с)\n")
        f.write("\n")
        for i in range(0, n, 2):
            t = i * step
            f.write(f"{t:7.2f}  {db[i]:6.1f} дБ  {'ГОЛОС' if act[i] else '  -  '}\n")

    # 10-секундная сетка: какой лист попадает в проигрыш
    grid = []
    for s in range(0, int(dur / 10) + 1):
        a, b = s * 10.0, min(dur, s * 10.0 + 10.0)
        seg = [(i * step, act[i]) for i in range(n) if a <= i * step < b]
        vocal_part = sum(step for _, v in seg if v)
        grid.append({"sheet": s + 1, "from": round(a, 2), "to": round(b, 2),
                     "vocal_sec": round(vocal_part, 2),
                     "girl": vocal_part < 3.0})

    with open(f"{ws}/ci/vocal_map.json", "w") as f:
        json.dump({"duration": round(dur, 2), "threshold_db": round(floor, 1),
                   "instrumental_runs": runs, "grid": grid}, f, ensure_ascii=False, indent=1)

    # минус целиком — потом можно подложить инструментал под сцены без голоса
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", inst, "-b:a", "192k",
                    f"{ws}/ci/instrumental.mp3"], check=True)

    print("длительность", round(dur, 2))
    print("проигрыши:", runs)
    for g in grid:
        print(f"лист {g['sheet']:02d} ({g['from']:.0f}–{g['to']:.0f} с): "
              f"вокал {g['vocal_sec']:.1f} с -> {'ДЕВУШКА' if g['girl'] else 'грибы'}")


if __name__ == "__main__":
    main()
