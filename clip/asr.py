#!/usr/bin/env python3
"""Распознавание вокала с таймкодами (Vosk) — основа для синхронизации титров.

Модель vosk-model-small-ru-0.22 в репозиторий не кладётся (88 МБ);
её надо положить в /tmp/voskru перед запуском (см. README в clip/).
Результат: /tmp/asr_words.json
"""
import json
import os
import subprocess
import wave

from vosk import KaldiRecognizer, Model, SetLogLevel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SONG = os.path.join(ROOT, "google_drive", "Гио_Пика_Фонтанчик_с_черным_дельфином_zaycev_net.mp3")
MODEL = "/tmp/voskru/vosk-model-small-ru-0.22"
FF = subprocess.run(["python3", "-c",
                     "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
                    capture_output=True, text=True).stdout.strip()

SetLogLevel(-1)
wav = "/tmp/song16k.wav"
if not os.path.exists(wav):
    subprocess.run([FF, "-v", "error", "-y", "-i", SONG, "-ac", "1", "-ar", "16000",
                    "-af", "highpass=f=90,lowpass=f=7000,dynaudnorm=g=6", wav],
                   check=True)
model = Model(MODEL)
w = wave.open(wav)
rec = KaldiRecognizer(model, w.getframerate())
rec.SetWords(True)
words = []
while True:
    data = w.readframes(4000)
    if not data:
        break
    if rec.AcceptWaveform(data):
        words += json.loads(rec.Result()).get("result", [])
words += json.loads(rec.FinalResult()).get("result", [])
json.dump(words, open("/tmp/asr_words.json", "w"), ensure_ascii=False)
print("слов:", len(words))
