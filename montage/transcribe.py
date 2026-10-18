#!/usr/bin/env python3
"""Расшифровка речи с точными таймингами (faster-whisper, CPU)."""
import sys, os, json, wave
import numpy as np
from faster_whisper import WhisperModel

def load_wav(path):
    with wave.open(path, "rb") as w:
        sr = w.getframerate(); n = w.getnframes(); ch = w.getnchannels()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x

src, outdir = sys.argv[1], sys.argv[2]
model = WhisperModel("base", device="cpu", compute_type="int8", download_root="/home/runner/.cache/huggingface/whisper")
segments, info = model.transcribe(load_wav(src), language="ru", vad_filter=True, word_timestamps=True,
                                  beam_size=5, condition_on_previous_text=False)
print("lang", info.language, info.language_probability)
rows = []
words = []
with open(os.path.join(outdir, "transcript.txt"), "w") as f:
    for s in segments:
        rows.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text})
        f.write(f"{int(s.start//60)}:{s.start%60:05.2f} - {int(s.end//60)}:{s.end%60:05.2f}  {s.text}\n")
        for w in (s.words or []):
            words.append({"start": round(w.start, 2), "end": round(w.end, 2), "w": w.word})
json.dump({"segments": rows, "words": words}, open(os.path.join(outdir, "transcript.json"), "w"), ensure_ascii=False, indent=1)
print("segments", len(rows), "words", len(words))
