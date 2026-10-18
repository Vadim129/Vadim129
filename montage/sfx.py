#!/usr/bin/env python3
"""Поиск звуковых событий: атаки, тембр, громкость, «музыкальность».

На выходе sfx.csv — все заметные атаки с признаками; events.txt — прореженный
список кандидатов в звуковые эффекты (фоли), отсортированный по «эффектности».
"""
import sys, os, json
import numpy as np
import librosa

wav, outdir = sys.argv[1], sys.argv[2]
t0 = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
t1 = float(sys.argv[4]) if len(sys.argv) > 4 else 1e9
tag = f"-{int(t0)}" if t0 or t1 < 1e8 else ""
y, sr = librosa.load(wav, sr=44100, mono=True, offset=t0, duration=min(t1, 1e9) - t0)
dur = len(y) / sr
print("dur", dur)

n_fft, hop = 2048, 256
S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop))
freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
mel = librosa.feature.melspectrogram(S=S, sr=sr, n_mels=96)
mel_db = librosa.power_to_db(mel, ref=np.max)
rms = librosa.feature.rms(S=S, frame_length=n_fft, hop_length=hop)[0]
db = 20 * np.log10(rms + 1e-9)

# гармоническая/перкуссионная части
H, P = librosa.effects.hpss(S)
perc_env = np.sum(np.abs(P), axis=0)
harm_env = np.sum(np.abs(H), axis=0)
onset_env = librosa.onset.onset_strength(S=librosa.power_to_db(mel), sr=sr, hop_length=hop)

# музыкальный темп (для отсева долей)
tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, hop_length=hop, units="time")
print("tempo", float(tempo), "beats", len(beats))

onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=hop,
                                    units="time", backtrack=True, delta=0.12, wait=5)
# прореживание
times = []
for t in onsets:
    if not times or t - times[-1] > 0.10:
        times.append(float(t))

rows = []
cent = librosa.feature.spectral_centroid(S=S, sr=sr)[0]
flat = librosa.feature.spectral_flatness(S=S)[0]
zcr = librosa.feature.zero_crossing_rate(y, frame_length=n_fft, hop_length=hop)[0]
band_hi = np.sum(S[(freqs >= 6000)], axis=0)
band_lo = np.sum(S[(freqs >= 40) & (freqs <= 250)], axis=0)
band_mid = np.sum(S[(freqs > 250) & (freqs < 4000)], axis=0)
total = np.sum(S, axis=0) + 1e-9

for t in times:
    i = int(t * sr / hop)
    a, b = max(0, i - 2), min(len(db), i + 3)
    lvl = float(np.max(db[a:b]))
    pre = float(np.mean(db[max(0, i - 45):max(1, i - 5)])) if i > 10 else lvl
    post = float(np.mean(db[min(len(db) - 1, i + 8):min(len(db), i + 40)])) if i + 8 < len(db) else lvl
    attack = lvl - pre
    c = float(np.mean(cent[a:b + 12]))
    fl = float(np.mean(flat[a:b + 12]))
    hi = float(np.mean(band_hi[a:b + 12] / total[a:b + 12]))
    lo = float(np.mean(band_lo[a:b + 12] / total[a:b + 12]))
    mid = float(np.mean(band_mid[a:b + 12] / total[a:b + 12]))
    z = float(np.mean(zcr[a:b + 12]))
    decay = lvl - post
    # длительность «хвоста»: сколько после атаки держится выше pre+6дБ
    j = i
    while j < len(db) and db[j] > pre + 6 and j - i < 220:
        j += 1
    tail = (j - i) * hop / sr
    # близость к доле
    dbeat = float(np.min(np.abs(beats - t))) if len(beats) else 9
    rows.append(dict(t=round(t + t0, 3), lvl=round(lvl, 1), pre=round(pre, 1), attack=round(attack, 1),
                     decay=round(decay, 1), tail=round(tail, 2), cent=round(c, 0),
                     flat=round(fl, 3), hi=round(hi, 3), mid=round(mid, 3), lo=round(lo, 3),
                     zcr=round(z, 3), dbeat=round(dbeat, 3)))

rows.sort(key=lambda r: r["t"])
with open(os.path.join(outdir, f"sfx{tag}.csv"), "w") as f:
    cols = list(rows[0].keys()) if rows else []
    f.write(",".join(cols) + "\n")
    for r in rows:
        f.write(",".join(str(r[c]) for c in cols) + "\n")

# кандидаты: не на доле, громкая атака, заметный хвост или яркий тембр
cand = []
for r in rows:
    if r["attack"] < 8:
        continue
    score = 0.0
    score += min(20, r["attack"]) * 0.5
    score += min(2.0, r["tail"]) * 4
    if r["dbeat"] > 0.12:
        score += 5
    if r["hi"] > 0.25:
        score += 6
    if r["flat"] > 0.02:
        score += 3
    if r["lvl"] > -18:
        score += 3
    cand.append((score, r))

cand.sort(key=lambda x: (-x[0], x[1]["t"]))
with open(os.path.join(outdir, f"events{tag}.txt"), "w") as f:
    f.write(f"{'t':>9} {'mm:ss':>7} {'score':>6} {'lvl':>6} {'attack':>6} {'tail':>5} {'cent':>6} {'hi':>5} {'lo':>5} {'dbeat':>5}\n")
    for s, r in cand[:160]:
        mm = f"{int(r['t']//60)}:{r['t']%60:05.2f}"
        f.write(f"{r['t']:9.2f} {mm:>7} {s:6.1f} {r['lvl']:6.1f} {r['attack']:6.1f} {r['tail']:5.2f} {r['cent']:6.0f} {r['hi']:5.2f} {r['lo']:5.2f} {r['dbeat']:5.2f}\n")

# карта громкости по секундам
with open(os.path.join(outdir, f"loudness{tag}.txt"), "w") as f:
    for s in range(int(dur) + 1):
        a = int(s * sr); b = int(min(dur, s + 1) * sr)
        seg = y[a:b]
        f.write(f"{s:4d} {20*np.log10(np.sqrt(np.mean(seg**2))+1e-9):7.1f}\n")

json.dump({"dur": dur, "t0": t0, "tempo": float(tempo), "beats": len(beats), "onsets": len(rows)}, open(os.path.join(outdir, f"sfx{tag}.json"), "w"))
print("onsets", len(rows), "cands", len(cand))
