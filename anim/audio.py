"""Procedural score for the living painting.

Everything is synthesised with numpy: a low organ-like drone, wind, glassy
crystal chimes, the whoosh + clack of the rook, and a soft closing swell.
Written as a 44.1 kHz stereo WAV that gets muxed into the final MP4.

    python3 anim/audio.py  ->  anim/media/score.wav
"""
from __future__ import annotations

import os
import wave

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 44100
DURATION = 33.0
N = int(SR * DURATION)
t = np.arange(N, dtype=np.float64) / SR
rng = np.random.default_rng(11)

LEFT = np.zeros(N, np.float64)
RIGHT = np.zeros(N, np.float64)


def env_adsr(n, a, d, s, r, sus=0.7):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    sus_n = max(0, n - a - d)
    e = np.concatenate([
        np.linspace(0, 1, max(1, a)),
        np.linspace(1, sus, max(1, d)),
        np.full(sus_n, sus),
        np.linspace(sus, 0, max(1, r)),
    ])
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))


def fade(x, fin=1.0, fout=2.0):
    n = x.shape[-1]
    e = np.ones(n)
    a, b = int(fin * SR), int(fout * SR)
    if a > 0:
        e[:a] = np.linspace(0, 1, a) ** 1.5
    if b > 0:
        e[-b:] = np.linspace(1, 0, b) ** 1.5
    return x * (e if x.ndim == 1 else e[None, :])


def place(buf, start, clip, gain=1.0, pan=0.0):
    i = int(start * SR)
    if i >= N:
        return
    n = min(len(clip), N - i)
    gl = gain * np.sqrt((1 - pan) / 2)
    gr = gain * np.sqrt((1 + pan) / 2)
    buf[0][i : i + n] += clip[:n] * gl
    buf[1][i : i + n] += clip[:n] * gr


def lowpass(x, fc, order=2):
    b, a = signal.butter(order, fc / (SR / 2), "low")
    return signal.lfilter(b, a, x)


def bandpass(x, f1, f2, order=2):
    b, a = signal.butter(order, [f1 / (SR / 2), f2 / (SR / 2)], "band")
    return signal.lfilter(b, a, x)


def bell(freq, dur=3.2, bright=0.5):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    partials = [(1.0, 1.0, 1.6), (2.01, 0.42 * bright, 1.1), (3.02, 0.22 * bright, 0.8),
                (4.98, 0.10 * bright, 0.5), (6.9, 0.05 * bright, 0.35)]
    x = np.zeros(n)
    for k, amp, dk in partials:
        x += amp * np.sin(2 * np.pi * freq * k * tt + rng.uniform(0, 6.28)) * np.exp(-tt / dk)
    x *= 1.0 - np.exp(-tt / 0.006)
    return x / (np.max(np.abs(x)) + 1e-9)


def whoosh(dur, f_lo=180, f_hi=1800, rise=0.8):
    n = int(dur * SR)
    noise = rng.normal(0, 1, n)
    # moving band-pass: sweep the centre frequency
    out = np.zeros(n)
    env = np.sin(np.linspace(0, np.pi, n)) ** rise
    seg = 512
    for i in range(0, n, seg):
        k = i / n
        fc = f_lo + (f_hi - f_lo) * k ** 1.6
        chunk = noise[i : i + seg]
        b, a = signal.butter(2, [fc * 0.5 / (SR / 2), min(0.99, fc * 1.8 / (SR / 2))], "band")
        out[i : i + len(chunk)] = signal.lfilter(b, a, chunk)
    return out * env / (np.max(np.abs(out)) + 1e-9)


# ------------------------------------------------------------------ drone
print("drone")
for f, amp, det in [(55.0, 0.22, 0.0), (82.5, 0.12, 0.3), (110.0, 0.08, -0.4), (164.81, 0.04, 0.7)]:
    lfo = 0.75 + 0.25 * np.sin(2 * np.pi * (0.031 + abs(det) * 0.02) * t + det)
    v = np.sin(2 * np.pi * (f + det * 0.4) * t) + 0.35 * np.sin(2 * np.pi * 2 * (f + det * 0.4) * t + 1.1)
    v *= lfo * amp
    LEFT += v
    RIGHT += v * (0.96 + 0.04 * np.sin(2 * np.pi * 0.017 * t + 2.0))

# wind: slowly breathing filtered noise, wide stereo
noise = rng.normal(0, 1, N)
wind = lowpass(noise, 900, 2) * 0.5 + bandpass(noise, 900, 3200, 2) * 0.18
wind *= 0.55 + 0.45 * np.sin(2 * np.pi * 0.043 * t + 0.7) ** 2
wind *= 0.038
LEFT += wind * (1 + 0.12 * np.sin(2 * np.pi * 0.021 * t))
RIGHT += wind * (1 - 0.12 * np.sin(2 * np.pi * 0.021 * t + 1.3))

# ------------------------------------------------------------------ chimes
print("chimes")
chime_times = [1.9, 2.55, 3.15, 5.4, 7.9, 10.6, 12.2, 14.0, 16.2, 18.55, 20.9, 22.4, 24.6, 26.2, 28.6]
notes = [440.0, 523.25, 587.33, 659.25, 783.99, 880.0, 1046.5]
events = []
for i, ts in enumerate(chime_times):
    f = notes[(i * 3) % len(notes)]
    g = 0.085 if i not in (1, 9, 13) else 0.125
    events.append((ts, f, g))
    if i % 3 == 0:  # soft octave shadow
        events.append((ts + 0.08, f * 2, g * 0.28))

for ts, f, g in events:
    b = bell(f, dur=3.4, bright=0.45)
    pan = np.clip((rng.uniform(-1, 1)), -0.8, 0.8)
    place((LEFT, RIGHT), ts, b, gain=g, pan=pan)

# wake-up swell: rising fifth under the eye switch-on
n = int(2.4 * SR)
tt = np.arange(n) / SR
sw = (np.sin(2 * np.pi * 220 * tt) + 0.6 * np.sin(2 * np.pi * 330 * tt)) * np.linspace(0, 1, n) ** 2
sw *= np.exp(-tt / 1.1)
place((LEFT, RIGHT), 2.35, sw, gain=0.065, pan=0.1)

# ------------------------------------------------------------------ the move
print("move")
place((LEFT, RIGHT), 15.05, whoosh(1.0, 300, 2400, 0.7), gain=0.115, pan=-0.15)
lift = whoosh(1.4, 450, 1500, 1.2)
place((LEFT, RIGHT), 15.55, lift, gain=0.10, pan=0.1)

# stone/wood clack on touchdown
n = int(0.7 * SR)
tt = np.arange(n) / SR
click = rng.normal(0, 1, n) * np.exp(-tt / 0.012)
clack = bandpass(click, 900, 6000, 2) * 0.9
thud = np.sin(2 * np.pi * 78 * tt) * np.exp(-tt / 0.07) * 0.7
thud += np.sin(2 * np.pi * 132 * tt) * np.exp(-tt / 0.045) * 0.35
land = (clack + thud)
land /= np.max(np.abs(land))
place((LEFT, RIGHT), 18.19, land, gain=0.48, pan=0.28)
place((LEFT, RIGHT), 18.28, bell(1046.5, 2.6, 0.5), gain=0.10, pan=0.35)
place((LEFT, RIGHT), 18.42, bell(1567.98, 2.4, 0.4), gain=0.055, pan=0.2)

# ------------------------------------------------------------------ ending
print("ending")
n = int(6.0 * SR)
tt = np.arange(n) / SR
swell = np.sin(2 * np.pi * 130.81 * tt) * (1 - np.exp(-tt / 1.2)) * np.exp(-tt / 3.4)
swell += 0.5 * np.sin(2 * np.pi * 196.0 * tt) * (1 - np.exp(-tt / 1.6)) * np.exp(-tt / 3.0)
swell += 0.25 * np.sin(2 * np.pi * 261.63 * tt) * (1 - np.exp(-tt / 2.0)) * np.exp(-tt / 2.6)
swell /= np.max(np.abs(swell))
place((LEFT, RIGHT), 27.2, swell, gain=0.16)

# ------------------------------------------------------------------ servos & goo
print("servos")
# quiet mechanical whirr whenever a limb makes a deliberate move
def servo(dur, f0, f1, grit=0.35):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    ph = 2 * np.pi * (f0 * tt + 0.5 * (f1 - f0) / max(dur, 1e-6) * tt ** 2)
    hum = np.sin(ph) * 0.6 + np.sin(2.03 * ph) * 0.22 + np.sin(3.11 * ph) * 0.1
    hum *= (1 - np.exp(-tt / 0.05)) * np.exp(-tt / (dur * 0.7))
    nz = bandpass(rng.normal(0, 1, n), 700, 4200, 1) * np.exp(-tt / (dur * 0.45))
    return (hum + nz * grit) / (np.max(np.abs(hum + nz * grit)) + 1e-9)


for ts, dur, f0, f1, g, pan in [
    (8.15, 0.9, 160, 240, 0.050, -0.25),   # head cocks
    (12.10, 0.85, 220, 150, 0.045, 0.10),  # head straightens
    (15.00, 0.75, 150, 260, 0.040, 0.25),  # right arm lifts off the table
    (17.45, 1.1, 240, 130, 0.038, 0.20),   # and settles back
    (23.60, 1.3, 130, 175, 0.034, -0.15),  # turns back to the viewer
]:
    place((LEFT, RIGHT), ts, servo(dur, f0, f1), gain=g, pan=pan)

# wet, sticky blips for the dripping goo
def goo(dur, f, drop=True):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    body = np.sin(2 * np.pi * f * tt * (1.0 - 0.35 * tt / dur)) * np.exp(-tt / (dur * 0.35))
    wet = bandpass(rng.normal(0, 1, n), 350, 2200, 1) * np.exp(-tt / (dur * 0.22)) * 0.5
    x = body * 0.7 + wet
    if drop:
        x *= (1 - np.exp(-tt / 0.01))
    return x / (np.max(np.abs(x)) + 1e-9)


for ts, f, g in [(6.2, 190, 0.055), (11.1, 150, 0.045), (13.7, 230, 0.040),
                 (19.6, 170, 0.048), (24.3, 210, 0.038), (28.0, 145, 0.042)]:
    place((LEFT, RIGHT), ts, goo(0.34, f), gain=g, pan=float(rng.uniform(-0.4, 0.5)))

# ------------------------------------------------------------------ space + mix
print("reverb + mix")
ir_n = int(2.4 * SR)
ir = rng.normal(0, 1, ir_n) * np.exp(-np.arange(ir_n) / SR / 0.55)
ir[: int(0.012 * SR)] = 0
ir = lowpass(ir, 5200, 1)
ir /= np.sqrt(np.sum(ir**2))

wet_l = signal.fftconvolve(LEFT, ir)[:N]
wet_r = signal.fftconvolve(RIGHT, ir)[:N]
mixL = LEFT * 0.78 + wet_l * 0.42
mixR = RIGHT * 0.78 + wet_r * 0.42

# gentle master shaping: soft-clip, normalise, fades
mix = np.stack([mixL, mixR])
mix = np.tanh(mix * 0.85)
mix = fade(mix, fin=1.6, fout=2.6)
peak = np.max(np.abs(mix))
mix = mix / peak * 0.80

path = os.path.join(HERE, "media", "score.wav")
os.makedirs(os.path.dirname(path), exist_ok=True)
pcm = (mix.T * 32767).astype(np.int16)
with wave.open(path, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("wrote", path, f"{os.path.getsize(path)/1e6:.2f} MB")
