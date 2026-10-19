#!/usr/bin/env python3
"""Раскладка строк песни по времени.

В треке два вокальных прохода: ~8.6–99 c и ~110.8–186.6 c (между ними
инструментальный пробел). Внутри прохода строки распределяются по числу
слогов и притягиваются к найденным в вокале паузам.
"""
import json
import os
import subprocess
import sys
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = "/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
SONG = os.path.join(ROOT, "google_drive", "Гио_Пика_Фонтанчик_с_черным_дельфином_zaycev_net.mp3")
OUT = os.path.join(ROOT, "clip", "timing.json")
VOWELS = "аеёиоуыэюяАЕЁИОУЫЭЮЯ"

SECTIONS = [(8.6, 99.0), (110.8, 186.6)]
OUTRO_END = 202.6


def load_blocks():
    blocks, cur = [], []
    for raw in open(os.path.join(ROOT, "clip", "lyrics.txt"), encoding="utf-8"):
        line = raw.strip()
        if not line:
            if cur:
                blocks.append(cur)
                cur = []
            continue
        if line.startswith("#TITLE|"):
            continue
        cur.append(line)
    if cur:
        blocks.append(cur)
    return blocks


def syl(text):
    return sum(1 for ch in text if ch in VOWELS) or 1


def vocal_envelope():
    """Остаток после вычитания инструментальной петли — где звучит голос."""
    wav = "/tmp/song_timing.wav"
    if not os.path.exists(wav):
        subprocess.run([FF, "-y", "-v", "error", "-i", SONG, "-ac", "1", "-ar", "22050", wav],
                       check=True)
    w = wave.open(wav)
    sr, n = w.getframerate(), w.getnframes()
    x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    win, hop = 2048, 256
    fb = np.fft.rfftfreq(win, 1 / sr)
    band = (fb >= 180) & (fb <= 4200)
    wnd = np.hanning(win).astype(np.float32)
    frames = (len(x) - win) // hop
    S = np.empty((frames, int(band.sum())), dtype=np.float32)
    for i in range(frames):
        sp = np.abs(np.fft.rfft(x[i * hop:i * hop + win] * wnd))
        S[i] = sp[band]
    fps = sr / hop
    P = 6.25                      # музыкальная петля
    nb = 200
    bps = nb / P
    t = np.arange(frames) / fps
    grid = np.arange(0, len(x) / sr, 1 / bps)
    G = S[np.clip(np.searchsorted(t, grid), 0, frames - 1)]
    ncyc = int(np.ceil(len(G) / nb))
    pad = np.zeros((ncyc * nb, G.shape[1]), dtype=np.float32)
    pad[:len(G)] = G
    instr = np.median(pad.reshape(ncyc, nb, G.shape[1]), axis=0)
    res = G - instr[np.arange(len(G)) % nb]
    v = np.sqrt((np.clip(res, 0, None) ** 2).mean(1) + 1e-12)
    vdb = 20 * np.log10(v + 1e-9)
    k = max(1, int(0.35 * bps))
    vdb = np.convolve(vdb, np.ones(k) / k, "same")
    return grid, vdb


def snap(bounds, grid, env, lo, hi):
    """Притягиваем границы строк к локальным минимумам вокала."""
    k = int(0.3 / (grid[1] - grid[0]))
    sm = np.convolve(env, np.ones(k) / k, "same")
    mins = []
    step = int(0.25 / (grid[1] - grid[0]))
    for i in range(step, len(sm) - step, max(1, step // 5)):
        seg = sm[i - step:i + step]
        if sm[i] == seg.min():
            if not mins or grid[i] - mins[-1] > 1.5:
                mins.append(grid[i])
    out = [bounds[0]]
    for b in bounds[1:-1]:
        cand = [m for m in mins if abs(m - b) <= 0.9 and m - out[-1] > 2.0]
        out.append(min(cand, key=lambda m: abs(m - b)) if cand else b)
    out.append(bounds[-1])
    return out


def main():
    blocks = load_blocks()
    lines = [t for b in blocks for t in b]
    grid, env = vocal_envelope()
    cues = []
    for si, (a, b) in enumerate(SECTIONS):
        used = lines
        w = np.array([syl(t) for t in used], dtype=float)
        cum = np.concatenate([[0], np.cumsum(w)]) / w.sum()
        bounds = a + cum * (b - a)
        bounds = snap(bounds, grid, env, a, b)
        for i, text in enumerate(used):
            cues.append({"t0": round(float(bounds[i]), 3),
                         "t1": round(float(bounds[i + 1]), 3),
                         "text": text})
    last = lines[-1]
    cues.append({"t0": round(SECTIONS[-1][1], 3), "t1": OUTRO_END, "text": last})
    json.dump({"cues": cues}, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for c in cues[:4] + cues[-2:]:
        print(f'{c["t0"]:7.2f}–{c["t1"]:7.2f}  {c["text"][:52]}')
    print(f"строк: {len(cues)}, файл: {OUT}")


if __name__ == "__main__":
    main()
