#!/usr/bin/env python3
"""Whisper-разметка дорожки для клипа «Орда».

Пишет в <папка>/analysis:
  phrases.csv      — построчная разметка: начало первого реально спетого слова строки
  words.json       — все слова с таймкодами и вероятностями (лучший проход)
  расшифровка.txt  — читаемая расшифровка с таймкодами
  pass-<модель>.json / .txt — сырые проходы для сравнения
  audio.json       — длительность, BPM, биты, огибающая громкости
"""
import csv, json, math, os, subprocess, sys, wave

OUT = sys.argv[1]
AN = os.path.join(OUT, 'analysis')
os.makedirs(AN, exist_ok=True)
SONG = os.path.join(OUT, 'song.mp3')
FF = os.environ.get('FFMPEG') or 'ffmpeg'
MODELS = [m for m in os.environ.get('WHISPER_MODELS', 'large-v3,medium').split(',') if m.strip()]


def decode_mono(rate=16000):
    wav = os.path.join('/tmp', 'orda-mono.wav')
    subprocess.run([FF, '-y', '-v', 'error', '-i', SONG, '-ac', '1', '-ar', str(rate), wav], check=True)
    with wave.open(wav) as w:
        raw = w.readframes(w.getnframes())
    import numpy as np
    return np.frombuffer(raw, dtype=np.int16).astype('float32') / 32768.0, rate


def audio_structure(x, sr):
    import numpy as np
    win = int(sr * 0.05)
    env = np.sqrt(np.mean(x[: len(x) // win * win].reshape(-1, win) ** 2, axis=1))
    env = np.clip(env * 5.0, 0, 1)
    fps = 20.0
    onset = np.maximum(0, np.diff(env, prepend=env[0]))
    corr = np.correlate(onset, onset, mode='full')[len(onset) - 1:]
    cand = []
    for bpm in np.arange(70, 185, 0.25):
        lag = int(round(60 / bpm * fps))
        if 1 <= lag < len(corr):
            cand.append((float(corr[lag]), float(bpm)))
    cand.sort(reverse=True)
    bpm = cand[0][1]
    print(f'темп: {bpm:.2f} (топ: ' + ', '.join(f'{b:.1f}' for _, b in cand[:5]) + ')')
    period = 60.0 / bpm
    best = (0.0, -1.0)
    for phase in np.arange(0, period, 0.005):
        score = float(np.sum(onset[int(round(phase * fps)):: max(1, int(round(period * fps)))][:600]))
        if score > best[1]:
            best = (float(phase), score)
    phase = best[0]
    beats = [round(phase + i * period, 3) for i in range(int((len(x) / sr - phase) / period) + 1)]
    return {
        'duration': round(len(x) / sr, 3),
        'bpm': round(bpm, 2),
        'beat_period': round(period, 3),
        'beats': beats,
        'env_rate': int(fps),
        'env': [round(float(v), 3) for v in env],
    }


def main():
    import numpy as np
    x, sr = decode_mono()
    print(f'длительность: {len(x) / sr:.2f} c')
    audio = audio_structure(x, sr)
    with open(os.path.join(AN, 'audio.json'), 'w', encoding='utf-8') as f:
        json.dump(audio, f, ensure_ascii=False)

    from faster_whisper import WhisperModel
    best = None
    for name in MODELS:
        print(f'=== модель {name} ===', flush=True)
        try:
            model = WhisperModel(name, device='cpu', compute_type='int8')
        except Exception as exc:
            print('не поднялась:', type(exc).__name__, exc)
            continue
        segments, info = model.transcribe(
            x,
            language=None,                 # пусть определит сама
            beam_size=5,
            vad_filter=False,              # VAD на плотном миксе съедал половину строк
            condition_on_previous_text=True,
            word_timestamps=True,
            no_speech_threshold=0.85,
            log_prob_threshold=-1.5,
            temperature=[0.0, 0.2, 0.4],
        )
        phrases, words = [], []
        for seg in segments:
            ws = [{'w': w.word.strip(), 's': round(float(w.start), 3), 'e': round(float(w.end), 3),
                   'p': round(float(w.probability), 3)} for w in (seg.words or []) if w.word.strip()]
            if not ws:
                continue
            words.extend(ws)
            first = ws[0]
            conf = 'high' if first['p'] >= 0.75 else ('medium' if first['p'] >= 0.45 else 'low')
            phrases.append({'idx': len(phrases) + 1, 'start_sec': first['s'], 'end_sec': round(float(seg.end), 3),
                            'phrase': seg.text.strip(), 'first_word': first['w'],
                            'first_word_prob': first['p'], 'confidence': conf})
        print(f'{name}: язык={info.language} p={info.language_probability:.2f}, строк {len(phrases)}, слов {len(words)}')
        for p in phrases:
            print(f'  {p["start_sec"]:7.2f}  [{p["confidence"]}]  {p["phrase"]}')
        with open(os.path.join(AN, f'pass-{name}.json'), 'w', encoding='utf-8') as f:
            json.dump({'model': name, 'language': info.language, 'lang_prob': round(float(info.language_probability), 3),
                       'phrases': phrases, 'words': words}, f, ensure_ascii=False)
        with open(os.path.join(AN, f'pass-{name}.txt'), 'w', encoding='utf-8') as f:
            for p in phrases:
                f.write(f'{p["start_sec"]:7.2f}–{p["end_sec"]:7.2f}  [{p["confidence"]}]  {p["phrase"]}\n')
        if best is None or len(words) > len(best[2]):
            best = (name, phrases, words, info.language)

    if best is None:
        raise SystemExit('ни один проход не дал текста')
    name, phrases, words, lang = best
    print(f'лучший проход: {name} ({len(words)} слов, язык {lang})')
    with open(os.path.join(AN, 'phrases.csv'), 'w', encoding='utf-8', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(phrases[0].keys()) if phrases else ['idx'])
        wr.writeheader()
        wr.writerows(phrases)
    with open(os.path.join(AN, 'words.json'), 'w', encoding='utf-8') as f:
        json.dump({'model': name, 'language': lang, 'duration': audio['duration'], 'words': words}, f, ensure_ascii=False)
    with open(os.path.join(AN, 'расшифровка.txt'), 'w', encoding='utf-8') as f:
        f.write(f'дорожка {audio["duration"]:.2f} c, BPM≈{audio["bpm"]:.1f}, модель {name}, язык {lang}\n\n')
        for p in phrases:
            f.write(f'{p["start_sec"]:7.2f}–{p["end_sec"]:7.2f}  [{p["confidence"]}]  {p["phrase"]}\n')
    print('готово')


if __name__ == '__main__':
    main()
