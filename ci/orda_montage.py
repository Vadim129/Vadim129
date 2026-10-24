#!/usr/bin/env python3
"""Финальная сборка клипа «Орда»: карандашный рендер + бегущая строка с эквалайзером.

1. Берём готовый клип от render_pencil.py (рисунки проявляются карандашом).
2. Считаем спектр трека: 44 полосы эквалайзера, сетка битов, атаки.
3. На каждый кадр рисуем полосу «заяц на коне гонится за мужчиной» (orda_ticker.py)
   и приклеиваем её в низ кадра 720x1280.
4. Пишем финальный MP4 с исходной дорожкой.

Запуск: python3 ci/orda_montage.py <папка проекта> <выход.mp4>
"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from orda_ticker import Ticker, W as TW, H as TH   # noqa: E402

ROOT = sys.argv[1]
OUT = sys.argv[2]
W, H, FPS = 720, 1280, 12
BARS = 44
SR = 22050
FF = os.environ.get('FFMPEG')
if not FF:
    import imageio_ffmpeg
    FF = imageio_ffmpeg.get_ffmpeg_exe()

audio = json.load(open(os.path.join(ROOT, 'analysis', 'audio.json'), encoding='utf-8'))
DUR = float(audio['duration'])
N_FRAMES = int(math.ceil(DUR * FPS))
print(f'длительность {DUR:.2f} c, кадров {N_FRAMES}, BPM {audio["bpm"]}')


def spectrum_matrix():
    """[N_FRAMES, BARS] — энергия по логарифмическим полосам, нормированная."""
    raw = subprocess.run([FF, '-v', 'error', '-i', os.path.join(ROOT, 'song.mp3'),
                          '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    win = 2048
    hop = SR // FPS
    freqs = np.fft.rfftfreq(win, 1.0 / SR)
    edges = np.geomspace(55, 11000, BARS + 1)
    band_bins = []
    for i in range(BARS):
        lo, hi = edges[i], edges[i + 1]
        idx = np.where((freqs >= lo) & (freqs < hi))[0]
        band_bins.append(idx if len(idx) else np.array([np.argmin(np.abs(freqs - lo))]))
    pad = np.concatenate([np.zeros(win // 2), x, np.zeros(win)])
    window = np.hanning(win).astype(np.float32)
    out = np.zeros((N_FRAMES, BARS), dtype=np.float32)
    for fi in range(N_FRAMES):
        c = win // 2 + fi * hop
        seg = pad[c - win // 2:c + win // 2]
        if len(seg) < win:
            seg = np.pad(seg, (0, win - len(seg)))
        mag = np.abs(np.fft.rfft(seg * window))
        for b, idx in enumerate(band_bins):
            out[fi, b] = mag[idx].mean()
    # сглаживание по времени + нормировка по перцентилю
    out = out.reshape(N_FRAMES, BARS)
    smooth = out.copy()
    for k in (1, 2):
        smooth[k:] = 0.6 * out[k:] + 0.4 * out[:-k]
    ref = np.percentile(smooth, 93, axis=0) + 1e-9
    norm = np.clip(smooth / ref, 0, 1.35)
    # «под бит»: лёгкая подсветка на ударах
    beats = np.asarray(audio['beats'], dtype=np.float32)
    pulse = np.zeros(N_FRAMES, dtype=np.float32)
    for bi in beats:
        fi = int(round(bi * FPS))
        for d in range(0, 4):
            if fi + d < N_FRAMES:
                pulse[fi + d] = max(pulse[fi + d], 1.0 - d * 0.28)
    return norm.astype(np.float32), pulse


bands, pulse = spectrum_matrix()
print('спектр посчитан', bands.shape)

ticker = Ticker(bars=BARS, seed=5, beat=float(audio['beat_period']))
clip = os.path.join(ROOT, 'final-clip.mp4')
dec = subprocess.Popen([FF, '-v', 'error', '-i', clip, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                       stdout=subprocess.PIPE)
enc = subprocess.Popen([FF, '-y', '-v', 'error',
                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                        '-i', os.path.join(ROOT, 'song.mp3'),
                        '-map', '0:v:0', '-map', '1:a:0',
                        '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
                        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
                        '-shortest', '-movflags', '+faststart', OUT],
                       stdin=subprocess.PIPE)
frame_bytes = W * H * 3
last = None
for fi in range(N_FRAMES):
    raw = dec.stdout.read(frame_bytes)
    if len(raw) < frame_bytes:
        if last is None:
            raise SystemExit('пустой карандашный клип')
        raw = last
    last = raw
    t = fi / FPS
    canvas = np.frombuffer(raw, dtype=np.uint8).reshape(H, W, 3).copy()
    strip = np.asarray(ticker.layer(t, bands[fi].tolist(), float(pulse[fi])).convert('RGB'))
    canvas[H - TH:] = strip
    enc.stdin.write(canvas.tobytes())
    if fi % 300 == 0:
        print(f'  кадр {fi}/{N_FRAMES} ({t:5.1f} c)')
enc.stdin.close()
dec.stdout.close()
dec.wait()
code = enc.wait()
if code:
    raise SystemExit(f'кодировщик вышел с кодом {code}')
print('готово:', OUT, os.path.getsize(OUT), 'байт')
