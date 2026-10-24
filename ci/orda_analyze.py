#!/usr/bin/env python3
"""Whisper-разметка дорожки для клипа «Орда».

Пишет в <папка>/analysis:
  phrases.csv      — построчная разметка: когда начинается первое реально спетое слово строки
  words.json       — все слова с таймкодами и вероятностями
  расшифровка.txt  — читаемая расшифровка с таймкодами
  audio.json       — длительность, BPM, сетка битов, огибающая громкости
"""
import csv, json, math, os, subprocess, sys, wave

OUT = sys.argv[1]
AN = os.path.join(OUT, 'analysis')
os.makedirs(AN, exist_ok=True)
SONG = os.path.join(OUT, 'song.mp3')
FF = os.environ.get('FFMPEG') or 'ffmpeg'


def decode_mono(rate=16000):
    wav = os.path.join('/tmp', 'orda-mono.wav')
    subprocess.run([FF, '-y', '-v', 'error', '-i', SONG, '-ac', '1', '-ar', str(rate), wav], check=True)
    with wave.open(wav) as w:
        raw = w.readframes(w.getnframes())
    import numpy as np
    return np.frombuffer(raw, dtype=np.int16).astype('float32') / 32768.0, rate


def main():
    import numpy as np
    x, sr = decode_mono()
    dur = len(x) / sr
    print(f'длительность: {dur:.2f} c, сэмплов {len(x)}')
    win = int(sr * 0.05)
    env = np.sqrt(np.mean(x[: len(x) // win * win].reshape(-1, win) ** 2, axis=1))
    env = np.clip(env * 5.0, 0, 1)
    # темп и биты по автокорреляции огибающей атаки
    onset = np.maximum(0, np.diff(env, prepend=env[0]))
    fps = 1.0 / 0.05
    corr = np.correlate(onset, onset, mode='full')[len(onset) - 1:]
    lo, hi = int(fps * 60 / 190), int(fps * 60 / 70)
    seg = corr[lo:hi]
    lag = lo + int(np.argmax(seg)) if len(seg) else lo
    bpm = 60.0 * fps / max(1, lag)
    while bpm < 85:
        bpm *= 2
    while bpm > 175:
        bpm /= 2
    print(f'BPM≈{bpm:.1f}, лаг {lag} кадров')

    # сетка битов по фазе сильных атак
    period = 60.0 / bpm
    phase_scores = [float(np.sum(onset[int(round(p * fps)):: max(1, int(round(period * fps)))][:400])) for p in np.arange(0, period, 0.01)]
    phase = float(np.arange(0, period, 0.01)[int(np.argmax(phase_scores))]) if phase_scores else 0.0
    beats = [round(phase + i * period, 3) for i in range(int((dur - phase) / period) + 1)]
    audio = {
        'duration': round(dur, 3),
        'bpm': round(bpm, 2),
        'beat_period': round(period, 3),
        'beats': beats,
        'env_rate': 20,
        'env': [round(float(v), 3) for v in env],
    }
    with open(os.path.join(AN, 'audio.json'), 'w', encoding='utf-8') as f:
        json.dump(audio, f, ensure_ascii=False)

    # --- Whisper ---
    # даём модели готовый wav: pyav в некоторых версиях не умеет открывать mp3 напрямую
    from faster_whisper import WhisperModel
    wav16 = os.path.join('/tmp', 'orda-16k.wav')
    subprocess.run([FF, '-y', '-v', 'error', '-i', SONG, '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', wav16], check=True)
    model_name = os.environ.get('WHISPER_MODEL', 'medium')
    print(f'модель: {model_name} (int8, cpu)')
    try:
        model = WhisperModel(model_name, device='cpu', compute_type='int8')
    except Exception as exc:            # нет памяти/модели — берём поменьше
        print('не поднялась', model_name, exc, '— пробую small')
        model_name = 'small'
        model = WhisperModel(model_name, device='cpu', compute_type='int8')
    segments, info = model.transcribe(
        wav16,
        language='ru',
        initial_prompt=None,
        beam_size=5,
        vad_filter=True,
        vad_parameters={'min_silence_duration_ms': 350},
        condition_on_previous_text=False,
        word_timestamps=True,
    )
    print(f'язык: {info.language} p={info.language_probability:.2f}, длительность сегментов {info.duration:.1f}')

    phrases, words = [], []
    for i, seg in enumerate(segments, 1):
        ws = []
        for w in (seg.words or []):
            item = {'w': w.word.strip(), 's': round(float(w.start), 3), 'e': round(float(w.end), 3), 'p': round(float(w.probability), 3)}
            if item['w']:
                ws.append(item)
                words.append(item)
        if not ws:
            continue
        first = ws[0]
        conf = 'high' if first['p'] >= 0.75 else ('medium' if first['p'] >= 0.45 else 'low')
        phrases.append({
            'idx': len(phrases) + 1,
            'start_sec': first['s'],
            'end_sec': round(float(seg.end), 3),
            'phrase': seg.text.strip(),
            'first_word': first['w'],
            'first_word_prob': first['p'],
            'confidence': conf,
        })
        print(f'[{len(phrases):02d}] {first["s"]:7.2f}  {conf:6s}  {seg.text.strip()}')

    with open(os.path.join(AN, 'phrases.csv'), 'w', encoding='utf-8', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(phrases[0].keys()) if phrases else ['idx'])
        wr.writeheader()
        wr.writerows(phrases)
    with open(os.path.join(AN, 'words.json'), 'w', encoding='utf-8') as f:
        json.dump({'model': model_name, 'duration': round(dur, 3), 'words': words}, f, ensure_ascii=False)
    with open(os.path.join(AN, 'расшифровка.txt'), 'w', encoding='utf-8') as f:
        f.write(f'дорожка {dur:.2f} c, BPM≈{bpm:.1f}, модель {model_name}\n\n')
        for p in phrases:
            f.write(f'{p["start_sec"]:7.2f}–{p["end_sec"]:7.2f}  [{p["confidence"]}]  {p["phrase"]}\n')
    print('готово:', len(phrases), 'строк,', len(words), 'слов')


if __name__ == '__main__':
    main()
