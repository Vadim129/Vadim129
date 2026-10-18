#!/usr/bin/env python3
"""Проверка готового файла: видео-поток скопирован без перекодирования,
длительность сохранена, звуковые удары стоят там, где нужно, плюс нарезка
коротких «до/после» фрагментов для быстрого прослушивания.
"""
import json
import os
import subprocess
import sys
import wave

import numpy as np

SFX = {
    "половник": (312.25, 313.75),
    "дверь": (544.35, 545.75),
}


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def stream_md5(path, kind="v:0"):
    return run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path,
                "-map", f"0:{kind}", "-c", "copy", "-f", "md5", "-"]).stdout.strip()


def probe(path):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", path], capture_output=True, text=True)
    return p.stderr


def load_wav(path):
    w = wave.open(path, "rb")
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    return x.reshape(-1, w.getnchannels()), w.getframerate()


def hits(x, sr, t0, t1, prom=8.0):
    s = x[int(t0 * sr):int(t1 * sr)].mean(axis=1)
    h = int(0.005 * sr)
    n = len(s) // h
    e = np.sqrt((s[:n * h].reshape(n, h) ** 2).mean(axis=1))
    db = 20 * np.log10(e + 1e-9)
    out, prev = [], None
    for i in range(1, n - 1):
        if db[i] > db[i - 1] and db[i] >= db[i + 1] and db[i] > -30:
            if prev is None or (i - prev) * 0.005 > 0.06:
                out.append((t0 + i * 0.005, float(db[i])))
                prev = i
    return [f"{t:.3f}({v:.0f}dB)" for t, v in out]


def main(src, fixed, out_txt, art_dir):
    lines = []
    lines.append("== видео-поток ==")
    m_src = stream_md5(src)
    m_out = stream_md5(fixed)
    lines.append(f"md5 источника : {m_src}")
    lines.append(f"md5 результата: {m_out}")
    lines.append("видео скопировано байт-в-байт: " + ("ДА" if m_src == m_out else "НЕТ"))
    lines.append("")
    lines.append("== контейнер ==")
    for tag, p in (("источник", src), ("результат", fixed)):
        info = probe(p)
        keep = [l.strip() for l in info.splitlines()
                if "Duration" in l or "Stream #" in l]
        lines.append(f"{tag}: " + " | ".join(keep))
    lines.append("")
    wav = "/tmp/verify_audio.wav"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", fixed,
         "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", wav])
    x, sr = load_wav(wav)
    lines.append(f"== удары в готовом файле (длина {len(x)/sr:.3f} с) ==")
    for name, (a, b) in SFX.items():
        lines.append(f"{name} {a}-{b}: " + ", ".join(hits(x, sr, a, b)))
    # «до/после» для прослушивания
    os.makedirs(art_dir, exist_ok=True)
    xa, _ = load_wav("/tmp/aud_src.wav")
    for name, (a, b) in SFX.items():
        for tag, arr in (("before", xa), ("after", x)):
            seg = arr[int((a - 0.01) * sr):int((b + 0.01) * sr)].mean(axis=1)
            pcm = (np.clip(seg, -1, 1) * 32767).astype(np.int16)
            w = wave.open("/tmp/_seg.wav", "wb")
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes()); w.close()
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", "/tmp/_seg.wav",
                 "-b:a", "96k", f"{art_dir}/{name}_{tag}.mp3"])
    lines.append("")
    lines.append("== loudness ==")
    for tag, p in (("источник", src), ("результат", fixed)):
        try:
            r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", p,
                                "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
                               capture_output=True, text=True)
            tail = [l.strip() for l in r.stderr.splitlines() if "I:" in l or "Peak:" in l]
            lines.append(f"{tag}: " + " ".join(tail[-2:]))
        except Exception as e:  # noqa: BLE001
            lines.append(f"{tag}: {e}")
    txt = "\n".join(lines)
    with open(out_txt, "w") as f:
        f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "fix/artifacts")
