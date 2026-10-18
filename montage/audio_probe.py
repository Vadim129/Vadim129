#!/usr/bin/env python3
"""Анализ звуковой дорожки: огибающая, спектрограмма, транзиенты, речь/тишина."""
import sys, os, json, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

wav_path, outdir = sys.argv[1], sys.argv[2]

with wave.open(wav_path, "rb") as w:
    sr = w.getframerate()
    n = w.getnframes()
    raw = w.readframes(n)
x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
dur = len(x) / sr
print(f"sr={sr} dur={dur:.2f}")

hop = int(0.02 * sr)          # 20 мс
frames = len(x) // hop
env = np.sqrt(np.mean(x[:frames * hop].reshape(frames, hop) ** 2, axis=1) + 1e-12)
env_db = 20 * np.log10(env + 1e-9)
t_env = np.arange(frames) * 0.02


def draw_envelope(path, bw=2400, bh=500):
    img = Image.new("RGB", (bw, bh), (16, 16, 20))
    d = ImageDraw.Draw(img)
    lo, hi = -70, 0
    def ty(v):
        v = max(lo, min(hi, v))
        return int((hi - v) / (hi - lo) * (bh - 30)) + 20
    step = max(1, frames // bw)
    for i in range(bw):
        a, b = i * step, min(frames, (i + 1) * step)
        if a >= b:
            break
        v = env_db[a:b].max()
        d.line([(i, ty(v)), (i, bh - 10)], fill=(70, 210, 140))
    for s in range(0, int(dur) + 1, 30):
        px = int(s / dur * bw)
        d.line([(px, 20), (px, bh - 10)], fill=(60, 60, 80))
        d.text((px + 3, 4), f"{s//60}:{s%60:02d}", fill=(200, 200, 220))
    img.save(path)


draw_envelope(os.path.join(outdir, "envelope.png"))


def draw_spectrogram(path, sec0, sec1, bw=2400, bh=520):
    a, b = int(sec0 * sr), int(min(dur, sec1) * sr)
    seg = x[a:b]
    nperseg, noverlap = 2048, 1536
    if len(seg) < nperseg:
        return False
    from scipy.signal import spectrogram
    f, t, S = spectrogram(seg, fs=sr, nperseg=nperseg, noverlap=noverlap, mode="magnitude")
    S = 20 * np.log10(S + 1e-9)
    fmax = 8000
    S = S[f <= fmax]
    S = S[::-1]
    lo, hi = np.percentile(S, 20), np.percentile(S, 99.5)
    S = np.clip((S - lo) / (hi - lo + 1e-9), 0, 1)
    img = np.zeros((S.shape[0], S.shape[1], 3), dtype=np.uint8)
    img[..., 0] = (S * 255).astype(np.uint8)
    img[..., 1] = (S ** 1.6 * 230).astype(np.uint8)
    img[..., 2] = (S ** 3 * 160).astype(np.uint8)
    im = Image.fromarray(img).resize((bw, bh - 24))
    canvas = Image.new("RGB", (bw, bh), (0, 0, 0))
    canvas.paste(im, (0, 20))
    d = ImageDraw.Draw(canvas)
    for s in range(int(sec0), int(sec1) + 1, 10):
        px = int((s - sec0) / (sec1 - sec0) * bw)
        d.line([(px, 20), (px, bh)], fill=(90, 90, 110))
        d.text((px + 2, 3), f"{s//60}:{s%60:02d}", fill=(220, 220, 240))
    canvas.save(path)
    return True


# спектрограммы кусками по 60 с (видно каждый звук)
os.makedirs(os.path.join(outdir, "spectro"), exist_ok=True)
t = 0.0
idx = 0
while t < dur:
    p = os.path.join(outdir, "spectro", f"spec-{int(t//60):03d}.png")
    if draw_spectrogram(p, t, min(dur, t + 60)):
        idx += 1
    t += 60

# транзиенты: резкий рост энергии
jump = np.diff(env_db)
cand = []
for i in range(2, len(jump) - 2):
    if jump[i] > 9 and env_db[i + 1] > -42:
        if jump[i] == jump[max(0, i - 6):i + 7].max():
            cand.append((round(float(t_env[i]), 2), round(float(jump[i]), 1), round(float(env_db[i + 1]), 1)))
# прореживание: не чаще 120 мс
peaks = []
for c in cand:
    if not peaks or c[0] - peaks[-1][0] > 0.12:
        peaks.append(c)
with open(os.path.join(outdir, "peaks.csv"), "w") as f:
    f.write("time,db_jump,level_db\n")
    for p in peaks:
        f.write(f"{p[0]},{p[1]},{p[2]}\n")
with open(os.path.join(outdir, "peaks.txt"), "w") as f:
    for p in peaks:
        f.write(f"{p[0]:8.2f}  +{p[1]:5.1f}дБ  {p[2]:6.1f}дБ\n")

# речь/тишина: 0.25 с окна по порогу адаптивной громкости
win = int(0.25 * sr)
nf = len(x) // win
lvl = np.array([20 * np.log10(np.sqrt(np.mean(x[i * win:(i + 1) * win] ** 2)) + 1e-9) for i in range(nf)])
thr = max(-45.0, float(np.percentile(lvl, 75)) - 18.0)
seg = []
state = None
for i, v in enumerate(lvl):
    s = "звук" if v > thr else "тихо"
    if s != state:
        seg.append([round(i * 0.25, 2), s])
        state = s
with open(os.path.join(outdir, "segments.txt"), "w") as f:
    f.write(f"порог {thr:.1f} дБ\n")
    for i, (st, s) in enumerate(seg):
        en = seg[i + 1][0] if i + 1 < len(seg) else round(dur, 2)
        f.write(f"{st:8.2f} - {en:8.2f}  {s}  ({en-st:.2f}с)\n")

json.dump({"sr": sr, "dur": dur, "peaks": len(peaks), "threshold": thr}, open(os.path.join(outdir, "audio.json"), "w"))
print("ok")
