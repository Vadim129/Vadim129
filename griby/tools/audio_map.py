# -*- coding: utf-8 -*-
"""Карта песни: где звучит вокал, где чистый проигрыш, где смены частей.

Нужна, чтобы девушка появлялась в клипе ТОЛЬКО на проигрышах, а грибы — везде остальное.
Результат: ci/audio_map.txt (по секундам) + ci/audio_map.json (сводка участков).
"""
import json
import os
import subprocess
import sys

import librosa
import numpy as np

SONG_ID = "1yGs88oWAw6TP-EdskGqH41Sjc2m0M309"
WORK = "/tmp/audiomap"
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
    y, sr = librosa.load(mp3, sr=22050, mono=True)
    dur = len(y) / sr

    # 1. энергия по 50 мс
    hop = 512
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop)

    # 2. вокальная полоса 250–3500 Гц и «воздух» >6 кГц
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    band_v = (freqs >= 250) & (freqs <= 3500)
    band_h = (freqs >= 6000)
    e_v = S[band_v].sum(axis=0)
    e_h = S[band_h].sum(axis=0)
    e_all = S.sum(axis=0) + 1e-9
    vocal_share = e_v / e_all

    # 3. гармонико-перкуссивное разделение: у голоса высокая гармоническая доля
    y_h, y_p = librosa.effects.hpss(y)
    h_rms = librosa.feature.rms(y=y_h, frame_length=2048, hop_length=hop)[0]
    p_rms = librosa.feature.rms(y=y_p, frame_length=2048, hop_length=hop)[0]
    harm_share = h_rms / (h_rms + p_rms + 1e-9)

    # 4. «вокал есть» — энергия в вокальной полосе выше адаптивного порога и звук не тихий
    e_v_db = librosa.power_to_db(e_v + 1e-12)
    thr = np.percentile(e_v_db, 55)          # порог по самому треку
    voiced = (e_v_db > thr) & (rms > np.percentile(rms, 25))

    # 5. сглаживание и поиск участков БЕЗ вокала длиннее 4 с
    win = 21                                  # ~0.5 с
    vs = np.convolve(voiced.astype(float), np.ones(win) / win, mode="same") > 0.35
    runs, start = [], None
    for t, v in zip(times, vs):
        if not v and start is None:
            start = t
        elif v and start is not None:
            if t - start >= 4.0:
                runs.append((round(float(start), 2), round(float(t), 2)))
            start = None
    if start is not None and times[-1] - start >= 4.0:
        runs.append((round(float(start), 2), round(float(times[-1]), 2)))

    # 6. сводка по секундам
    lines = []
    step = 1.0
    for i in range(int(dur)):
        a, b = i / step, (i + 1) / step
        m = (times >= a) & (times < b)
        if not m.any():
            continue
        lines.append(
            f"{i:3d} c  rms={20*np.log10(rms[m].mean()+1e-9):6.1f} дБ  "
            f"вокал-полоса={100*vocal_share[m].mean():4.0f}%  "
            f"гармоника={100*harm_share[m].mean():3.0f}%  "
            f"голос={'да ' if vs[m].mean() > 0.4 else 'НЕТ'}"
        )

    ws = os.environ.get("GITHUB_WORKSPACE", ".")
    os.makedirs(f"{ws}/ci", exist_ok=True)
    with open(f"{ws}/ci/audio_map.txt", "w") as f:
        f.write(f"# Песня: {dur:.2f} с\n")
        f.write("# участки БЕЗ вокала (проигрыши) >= 4 с:\n")
        for a, b in runs:
            f.write(f"#   {a:6.2f} – {b:6.2f}  ({b-a:.2f} с)\n")
        f.write("\n".join(lines) + "\n")

    # 7. ещё и границы частей по спектральным сменам (для разметки листов)
    chroma = librosa.feature.chroma_cqt(y=y_h, sr=sr, hop_length=hop)
    novelty = np.linalg.norm(np.diff(chroma, axis=1), axis=0)
    novelty = np.convolve(novelty, np.ones(31) / 31, mode="same")
    peaks = librosa.util.peak_pick(novelty, pre_max=20, post_max=20,
                                   pre_avg=40, post_avg=40, delta=np.percentile(novelty, 92),
                                   wait=60)
    cuts = [round(float(t), 2) for t in librosa.frames_to_time(peaks, sr=sr, hop_length=hop)]

    with open(f"{ws}/ci/audio_map.json", "w") as f:
        json.dump({"duration": round(float(dur), 2),
                   "instrumental_runs": runs,
                   "section_cuts": cuts}, f, ensure_ascii=False, indent=1)

    print("длительность", round(dur, 2))
    print("проигрыши:", runs)
    print("смены частей:", cuts)


if __name__ == "__main__":
    main()
