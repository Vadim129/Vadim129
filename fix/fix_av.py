#!/usr/bin/env python3
"""Адресная правка тайминга звуковых эффектов в готовом видео.

Правки (все — только аудио, видео копируется как есть):
  1) половник: металлический удар + отскок звучат на 0.34 с раньше касания стола
     (312.51/312.93 при касании 312.85) -> окно сдвигается на +0.34 с;
  2) дверь/испуг: удар и «стон» двери стоят на 545.17/545.75, тогда как героиня
     оборачивается на 544.60-544.90 -> окно сдвигается на -0.49 с.

Окно вырезается из тихого «дна» (речь в нём отсутствует), на его месте
остаётся плавная склейка фона, а сам материал подмешивается в новую точку,
поэтому слова не страдают.
"""
import json
import sys
import wave

import numpy as np

EDITS = [
    # name, window_start, window_end, delta, gain
    ("ladle", 312.40, 313.22, +0.34, 1.0),
    ("door", 545.05, 545.92, -0.42, 1.0),
]


def load(path):
    w = wave.open(path, "rb")
    sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
    x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    return x.reshape(-1, ch), sr


def save(path, x, sr):
    w = wave.open(path, "wb")
    w.setnchannels(x.shape[1])
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes(np.clip(x, -1, 1).__mul__(32767).astype(np.int16).tobytes())
    w.close()


def bed_fill(x, s0, s1, ctx=0.20):
    """Заполняет [s0,s1) плавной смесью фона до и после окна."""
    n = s1 - s0
    c = min(int(ctx * 1000), n)
    pre = x[s0 - c:s0]
    post = x[s1:s1 + c]
    reps = int(np.ceil(n / c))
    tile_pre = np.tile(pre, (reps, 1))[:n]
    tile_post = np.tile(post, (reps, 1))[:n]
    t = np.linspace(0.0, 1.0, n, dtype=np.float32)[:, None]
    ramp = (1 - np.cos(np.pi * t)) / 2
    return tile_pre * (1 - ramp) + tile_post * ramp


def apply_edit(x, sr, name, s0, s1, delta, gain=1.0, fade=0.02):
    a, b = int(round(s0 * sr)), int(round(s1 * sr))
    seg = x[a:b].copy()
    d = int(round(delta * sr))
    # 1) вырезаем: на месте окна остаётся фон
    x[a:b] = bed_fill(x, a, b)
    # 2) подмешиваем материал в новую точку
    da, db = a + d, b + d
    if da < 0:
        raise SystemExit(f"{name}: сдвиг уводит за начало файла")
    f = int(fade * sr)
    w = seg.copy()
    if f > 0:
        r = (np.linspace(0, 1, f, dtype=np.float32) ** 2)[:, None]
        w[:f] *= r
        w[-f:] *= r[::-1]
    # подмешиваем, следя за перегрузом только в точке вставки
    g = gain
    if float(np.abs(x[da:db] + w * g).max()) > 0.985:
        lo, hi = 0.0, gain
        for _ in range(24):
            mid = (lo + hi) / 2
            if float(np.abs(x[da:db] + w * mid).max()) <= 0.985:
                lo = mid
            else:
                hi = mid
        g = lo
    x[da:db] += w * g
    return name, (a, b), (da, db), round(g, 3)


def frames_db(x, sr, hop=0.005):
    m = x.mean(axis=1)
    h = int(hop * sr)
    n = len(m) // h
    return np.arange(n) * hop, 20 * np.log10(np.sqrt((m[:n * h].reshape(n, h) ** 2).mean(axis=1)) + 1e-9)


def peak_at(x, sr, t0, t1):
    a, b = int(t0 * sr), int(t1 * sr)
    return float(np.abs(x[a:b]).max())


def main(src, dst, report=None):
    x, sr = load(src)
    print(f"вход: {len(x)/sr:.3f} с, {sr} Гц, {x.shape[1]} кан.")
    info = []
    for name, s0, s1, delta, gain in EDITS:
        before = peak_at(x, sr, s0, s1)
        info.append({"name": name, "window": [s0, s1], "delta": delta,
                     "peak_before": round(before, 4)})
        r = apply_edit(x, sr, name, s0, s1, delta, gain)
        print("  ", r)
        info[-1]["gain_used"] = r[-1]
    # защита от перегруза только в местах подмешивания
    pk = float(np.abs(x).max())
    print(f"пик после правок: {pk:.4f} ({20*np.log10(pk+1e-9):.1f} dBFS) — общая громкость не менялась")
    save(dst, x, sr)
    if report:
        with open(report, "w") as fh:
            json.dump(info, fh, ensure_ascii=False, indent=1)
    print("готово:", dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
