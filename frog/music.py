"""Club track for the dancing frog — 128 BPM, 2:00 exactly (64 bars).

Written from scratch with numpy/scipy:
  kick, clap, hats, rolling bass, chord stabs, arp lead, pad, risers,
  impacts, vinyl noise, sidechain pumping, ping-pong delay, reverb.

Output: frog/media/track.wav  (44.1 kHz, 16-bit stereo)

The renderer reads the same BPM/grid, so every hit lands on a visible move.
"""
from __future__ import annotations

import os
import wave

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "media")

SR = 44100
BPM = 128.0
BEAT = 60.0 / BPM            # 0.46875 s
BAR = BEAT * 4               # 1.875 s
BARS = 64
DURATION = BAR * BARS        # 120.0 s
N = int(round(DURATION * SR))

rng = np.random.default_rng(2024)
L = np.zeros(N, np.float32)
R = np.zeros(N, np.float32)


# ------------------------------------------------------------------ utils
def add(buf_l, buf_r, start, clip, gain=1.0, pan=0.0):
    i = int(round(start * SR))
    if i >= N or i + len(clip) <= 0:
        return
    if i < 0:
        clip = clip[-i:]
        i = 0
    n = min(len(clip), N - i)
    gl = gain * np.sqrt((1 - pan) / 2)
    gr = gain * np.sqrt((1 + pan) / 2)
    buf_l[i : i + n] += (clip[:n] * gl).astype(np.float32)
    buf_r[i : i + n] += (clip[:n] * gr).astype(np.float32)


def env(n, a=0.002, d=0.2, s=0.0, r=0.05, sus=0.0):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    e = np.zeros(n, np.float32)
    a = min(a, n)
    e[:a] = np.linspace(0, 1, a) if a else 1.0
    d_end = min(n, a + d)
    if d_end > a:
        e[a:d_end] = np.linspace(1, sus, d_end - a)
    if sus > 0:
        e[d_end : max(d_end, n - r)] = sus
    if r > 0 and n > r:
        e[-r:] = np.linspace(e[-r], 0, r)
    return e


def lp(x, fc, order=2):
    fc = min(fc, SR * 0.45)
    b, a = signal.butter(order, fc / (SR / 2), "low")
    return signal.lfilter(b, a, x).astype(np.float32)


def hp(x, fc, order=2):
    b, a = signal.butter(order, max(20, fc) / (SR / 2), "high")
    return signal.lfilter(b, a, x).astype(np.float32)


def bp(x, f1, f2, order=2):
    f1 = max(20, f1); f2 = min(SR * 0.45, f2)
    b, a = signal.butter(order, [f1 / (SR / 2), f2 / (SR / 2)], "band")
    return signal.lfilter(b, a, x).astype(np.float32)


def saw(freq, n, phase=0.0):
    t = np.arange(n, dtype=np.float32) / SR
    return signal.sawtooth(2 * np.pi * freq * t + phase).astype(np.float32)


def sq(freq, n, duty=0.5):
    t = np.arange(n, dtype=np.float32) / SR
    return signal.square(2 * np.pi * freq * t, duty).astype(np.float32)


def note(name):
    """'F#1' -> Hz"""
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6,
             "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    pitch, octave = name[:-1], int(name[-1])
    midi = 12 * (octave + 1) + names[pitch]
    return 440.0 * 2 ** ((midi - 69) / 12)


# ------------------------------------------------------------------ drums
def make_kick():
    n = int(0.42 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f = 46 + 120 * np.exp(-t / 0.028)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.16)
    click = rng.normal(0, 1, n).astype(np.float32) * np.exp(-t / 0.0035) * 0.55
    click = hp(click, 1800)
    x = body * 0.95 + click
    # soft saturation for punch
    x = np.tanh(x * 1.5) * 0.9
    return (x / np.max(np.abs(x))).astype(np.float32)


def make_clap():
    n = int(0.34 * SR)
    x = np.zeros(n, np.float32)
    for k, off in enumerate((0.0, 0.010, 0.021, 0.033)):
        i = int(off * SR)
        ln = int((0.20 - k * 0.03) * SR)
        burst = rng.normal(0, 1, ln).astype(np.float32)
        burst = bp(burst, 900, 5200)
        burst *= np.exp(-np.arange(ln) / (0.045 * SR))
        x[i : i + ln] += burst[: len(x[i : i + ln])] * (0.9 - 0.15 * k)
    x = np.tanh(x * 1.4)
    return (x / np.max(np.abs(x))).astype(np.float32)


def make_hat(open_=False):
    dur = 0.18 if open_ else 0.045
    n = int(dur * SR)
    x = rng.normal(0, 1, n).astype(np.float32)
    x = hp(x, 7800 if open_ else 8600, 3)
    x *= np.exp(-np.arange(n) / ((0.075 if open_ else 0.012) * SR))
    return (x / (np.max(np.abs(x)) + 1e-9)).astype(np.float32)


def make_snare():
    n = int(0.2 * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05) * 0.5
    noise = bp(rng.normal(0, 1, n).astype(np.float32), 1200, 7000) * np.exp(-t / 0.07)
    x = tone + noise
    return (x / np.max(np.abs(x))).astype(np.float32)


def make_riser(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    k = np.linspace(0, 1, n, dtype=np.float32)
    noise = rng.normal(0, 1, n).astype(np.float32)
    sweep = np.zeros(n, np.float32)
    seg = 2048
    for i in range(0, n, seg):
        p = i / max(1, n - 1)
        fc = 300 + 7500 * p ** 2
        chunk = noise[i : i + seg]
        sweep[i : i + len(chunk)] = bp(chunk, fc * 0.55, min(fc * 1.9, SR * 0.45))
    tone = np.sin(2 * np.pi * np.cumsum(180 + 900 * k ** 2) / SR) * 0.25
    x = sweep * 0.9 + tone
    x *= np.linspace(0.02, 1.0, n) ** 2
    return (x / (np.max(np.abs(x)) + 1e-9)).astype(np.float32)


def make_impact():
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * np.cumsum(30 + 70 * np.exp(-t / 0.08)) / SR) * np.exp(-t / 0.45)
    noise = lp(rng.normal(0, 1, n).astype(np.float32), 900) * np.exp(-t / 0.22) * 0.5
    x = np.tanh((sub + noise) * 1.6)
    return (x / np.max(np.abs(x))).astype(np.float32)


KICK = make_kick()
CLAP = make_clap()
HAT_C = make_hat(False)
HAT_O = make_hat(True)
SNARE = make_snare()
risk_global = None

# ------------------------------------------------------------------ harmony
# F# minor: i - VI - III - VII  (F#m, D, A, E)
PROG = [["F#1", "A1", "C#2"], ["D1", "F#1", "A1"], ["A1", "C#2", "E2"], ["E1", "G#1", "B1"]]
CHORD_HI = [["F#3", "A3", "C#4"], ["D3", "F#3", "A3"], ["A3", "C#4", "E4"], ["E3", "G#3", "B3"]]
ARP = [["F#4", "A4", "C#5", "E5"], ["D4", "F#4", "A4", "C#5"],
       ["A3", "C#4", "E4", "A4"], ["E4", "G#4", "B4", "D5"]]


def stab(freqs, dur=0.22, detune=0.004, cut=2600):
    n = int(dur * SR)
    x = np.zeros(n, np.float32)
    for f in freqs:
        for dt in (-detune, 0.0, detune):
            x += saw(f * (1 + dt), n, rng.uniform(0, 6.28)) * 0.33
    x = lp(x, cut)
    x *= env(n, 0.004, dur * 0.5, 0.25, dur * 0.4)
    return (x / (np.max(np.abs(x)) + 1e-9)).astype(np.float32)


def pluck(f, dur=0.18, bright=3800):
    n = int(dur * SR)
    x = saw(f, n) * 0.6 + sq(f * 2, n, 0.35) * 0.25
    x = lp(x, bright)
    x *= np.exp(-np.arange(n) / (dur * 0.35 * SR))
    return (x / (np.max(np.abs(x)) + 1e-9)).astype(np.float32)


def pad(freqs, dur):
    n = int(dur * SR)
    x = np.zeros(n, np.float32)
    for f in freqs:
        for dt in (-0.006, -0.002, 0.002, 0.006):
            x += saw(f * (1 + dt), n, rng.uniform(0, 6.28)) * 0.25
    x = hp(lp(x, 2600), 180)
    x *= env(n, 0.5, 0.6, 1.0, 0.5, sus=1.0)
    return (x / (np.max(np.abs(x)) + 1e-9)).astype(np.float32)


def bass_note(f, dur):
    n = int(dur * SR)
    x = saw(f, n) * 0.75 + sq(f, n, 0.5) * 0.25
    # moving low-pass gives the "roll"
    out = np.zeros(n, np.float32)
    seg = 1024
    for i in range(0, n, seg):
        p = i / max(1, n - 1)
        fc = 140 + 420 * np.sin(np.pi * min(1.0, p * 1.6)) ** 0.8
        out[i : i + seg] = lp(x[i : i + seg], fc, 2)
    out *= env(n, 0.005, dur * 0.25, 0.7, dur * 0.25, sus=0.7)
    return (out / (np.max(np.abs(out)) + 1e-9)).astype(np.float32)


print("drums + bass")
# ------------------------------------------------------------------ arrangement
def bar_t(b):
    return b * BAR


# section map
SEC = {
    "intro": (0, 8),
    "build1": (8, 12),
    "grooveA": (12, 24),
    "break": (24, 32),
    "drop": (32, 56),
    "outro": (56, 64),
}


def section(b):
    for k, (a, z) in SEC.items():
        if a <= b < z:
            return k
    return "outro"


# ---- kicks
for b in range(BARS):
    s = section(b)
    if s == "intro" and b < 2:
        continue
    if s == "break" and 26 <= b < 30:
        # breakdown: kick out except a heartbeat
        if b not in (27,):
            continue
    for beat in range(4):
        t0 = bar_t(b) + beat * BEAT
        g = 1.0
        if s == "intro":
            g = 0.55 + 0.45 * (b - 2) / 6
        elif s == "break":
            g = 0.75
        elif s == "outro":
            g = max(0.0, 1.0 - (b - 56) / 8.0) * 0.95
        add(L, R, t0, KICK, gain=0.88 * g)

# ---- claps on 2 and 4
for b in range(BARS):
    s = section(b)
    if s in ("intro",) or (s == "break" and b < 30):
        continue
    if s == "outro" and b > 60:
        continue
    for beat in (1, 3):
        add(L, R, bar_t(b) + beat * BEAT, CLAP, gain=0.78, pan=0.05)
    # snare build in the last bar of the build
    if s == "build1" and b == 11:
        for k in range(8):
            add(L, R, bar_t(b) + k * BEAT / 2, SNARE, gain=0.18 + 0.05 * k, pan=-0.1)

# ---- hats
for b in range(BARS):
    s = section(b)
    if s == "intro" and b < 1:
        continue
    density = 4 if s in ("grooveA", "drop", "build1") else 2
    for k in range(density * 4):
        t0 = bar_t(b) + k * (BEAT / density)
        if density == 4 and k % 4 == 0:
            continue  # leave the downbeat to the kick
        g = 0.25 if s != "drop" else 0.31
        if s == "outro":
            g *= max(0.0, 1.0 - (b - 56) / 8.0)
        add(L, R, t0, HAT_C, gain=g, pan=(-0.28 if k % 2 else 0.28))
    # open hat on the offbeat in the drop
    if s == "drop":
        for beat in range(4):
            add(L, R, bar_t(b) + beat * BEAT + BEAT / 2, HAT_O, gain=0.16, pan=0.15)

# ---- snare rolls entering the drop
for b in [30, 31, 54, 55]:
    for k in range(16):
        add(L, R, bar_t(b) + k * BEAT / 4, SNARE, gain=0.10 + 0.16 * (k / 15) ** 1.5, pan=-0.12 + 0.24 * (k % 2))

print("bass")
# ---- rolling bass (offbeat 8ths + 16th push), sidechained later
for b in range(BARS):
    s = section(b)
    if s == "intro" and b < 4:
        continue
    if s == "break" and 26 <= b < 30:
        continue
    if s == "outro" and b > 60:
        continue
    chord = PROG[b % 4]
    root = note(chord[0])
    for k in range(8):
        t0 = bar_t(b) + (k * BEAT / 2) + BEAT / 4
        octave = 1.0 if k % 2 == 0 else 2.0
        d = BEAT / 2 * 0.82
        g = 0.22
        if s == "break":
            g = 0.22
        if s == "outro":
            g *= max(0.0, 1.0 - (b - 56) / 8.0)
        add(L, R, t0, bass_note(root * octave, d), gain=g, pan=0.0)

print("chords + lead")
# ---- chord stabs
for b in range(BARS):
    s = section(b)
    if s in ("intro",):
        continue
    chord = [note(x) for x in CHORD_HI[b % 4]]
    if s == "break":
        for beat in (0,):
            add(L, R, bar_t(b) + beat * BEAT, stab(chord, 0.5, cut=1200), gain=0.32, pan=0.0)
    elif s == "outro":
        g = max(0.0, 1.0 - (b - 56) / 9.0) * 0.34
        add(L, R, bar_t(b), stab(chord, 0.35, cut=1800), gain=g)
    else:
        for beat in (1, 3):
            add(L, R, bar_t(b) + beat * BEAT + BEAT / 2, stab(chord, 0.22, cut=4200), gain=0.50, pan=0.08)

# ---- arp lead (drop only), 16ths
def arp_line():
    for b in range(*SEC["drop"]):
        seq = ARP[b % 4]
        for k in range(16):
            t0 = bar_t(b) + k * BEAT / 4
            f = note(seq[k % 4]) * (2.0 if (k // 4) % 2 else 1.0)
            g = 0.22 if k % 2 == 0 else 0.15
            if b >= 52:
                g *= max(0.0, 1 - (b - 52) / 4)
            p = pitch = pluck(f, 0.14, 5200)
            add(L, R, t0, pitch, gain=g, pan=(-0.35 if k % 2 else 0.35))


arp_line()

# ---- pad through the breakdown and under the drop
for b in range(*SEC["break"]):
    chord = [note(x) for x in CHORD_HI[b % 4]]
    add(L, R, bar_t(b), pad(chord, BAR * 1.05), gain=0.30, pan=0.0)
for b in range(*SEC["drop"]):
    chord = [note(x) for x in CHORD_HI[b % 4]]
    add(L, R, bar_t(b), pad(chord, BAR * 1.05), gain=0.12, pan=0.0)

print("fx")
# ---- risers + impacts
for b, dur in [(6, 4.0), (22, 3.75), (30, 3.75)]:
    add(L, R, bar_t(b), make_riser(dur), gain=0.34, pan=0.0)
for b in (8, 24, 32, 56):
    add(L, R, bar_t(b), make_impact(), gain=0.55 if b != 32 else 0.85, pan=0.0)
# reverse cymbal into the drop
rev = make_hat(True)[::-1]
add(L, R, bar_t(31) + BEAT * 3, rev, gain=0.5, pan=0.0)

# vinyl/room noise
noise = rng.normal(0, 1, N).astype(np.float32)
noise = bp(noise, 400, 9000) * 0.010
fade = np.ones(N, np.float32)
fade[: int(1.0 * SR)] = np.linspace(0, 1, int(1.0 * SR))
fade[-int(2.5 * SR) :] = np.linspace(1, 0, int(2.5 * SR))
L += noise * fade
R += np.roll(noise, 311) * fade

print("sidechain")
# ---- sidechain the whole music bus to the kick
sc = np.ones(N, np.float32)
for b in range(BARS):
    s = section(b)
    if s == "break" and 26 <= b < 30:
        continue
    for beat in range(4):
        i = int(round((bar_t(b) + beat * BEAT) * SR))
        if i >= N:
            continue
        ln = int(0.24 * SR)
        ln = min(ln, N - i)
        curve = 1.0 - 0.55 * np.exp(-np.arange(ln) / (0.065 * SR))
        sc[i : i + ln] = np.minimum(sc[i : i + ln], curve)
L *= sc
R *= sc

print("fx bus: delay + reverb")
# ---- ping-pong delay on a send copy
send_l = L.copy()
send_r = R.copy()
for taps, g in [((3 * BEAT / 4, 2 * BEAT / 2), 0.20)]:
    pass
d1 = int(3 * BEAT / 4 * SR)
d2 = int(6 * BEAT / 4 * SR)
dl = np.zeros_like(L)
dr = np.zeros_like(R)
dl[d1:] += send_r[: N - d1] * 0.18
dr[d2:] += send_l[: N - d2] * 0.12
dl = lp(dl, 4500)
dr = lp(dr, 4500)
L += dl
R += dr

# ---- cheap but spacious reverb: four combs + two allpasses per channel
def reverb(x, seed, wet=0.26):
    rng_ = np.random.default_rng(seed)
    combs = [1557, 1617, 1491, 1422]
    acc = np.zeros_like(x)
    for c in combs:
        buf = np.zeros_like(x)
        # feedback comb via IIR: y[n] = x[n] + 0.72*y[n-c]
        b = np.zeros(c + 1, np.float32)
        b[0] = 1.0
        a = np.zeros(c + 1, np.float32)
        a[0] = 1.0
        a[c] = -0.72
        y = signal.lfilter(b, a, x).astype(np.float32)
        acc += y
    acc /= len(combs)
    for d, g in [(225, 0.5), (556, 0.5)]:
        acc = acc + g * np.roll(acc, d)
    acc = lp(acc, 6500)
    return x * (1 - wet) + acc * wet


L = reverb(L, 1, 0.22)
R = reverb(R, 2, 0.22)

print("master")
# presence: lift the top so the beat cuts through on small speakers
sos = signal.butter(2, 2200 / (SR / 2), "high", output="sos")
hi_l = signal.sosfilt(sos, L)
hi_r = signal.sosfilt(sos, R)
L = L + hi_l * 0.55
R = R + hi_r * 0.55
# clean the subsonic rumble
sos_hp = signal.butter(2, 30 / (SR / 2), "high", output="sos")
L = signal.sosfilt(sos_hp, L)
R = signal.sosfilt(sos_hp, R)

# ---- gentle bus compression + soft clip + normalise
peak = max(np.max(np.abs(L)), np.max(np.abs(R)))
L /= peak
R /= peak
drive = 1.6
L = np.tanh(L * drive) / np.tanh(drive)
R = np.tanh(R * drive) / np.tanh(drive)
peak = max(np.max(np.abs(L)), np.max(np.abs(R)))
L = L / peak * 0.92
R = R / peak * 0.92
# short fade at both ends
fi = int(0.4 * SR)
L[:fi] *= np.linspace(0, 1, fi)
R[:fi] *= np.linspace(0, 1, fi)

os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, "track.wav")
pcm = (np.stack([L, R], 1) * 32767).astype(np.int16)
with wave.open(path, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("wrote", path, f"{os.path.getsize(path)/1e6:.1f} MB", f"{N/SR:.2f}s")
