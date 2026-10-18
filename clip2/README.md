# КЛИП «Я РУССКИЙ МУЖИК» — 9:16, 149 с

Энергичный монтажный клип по треку SHAMAN «Я русский мужик» (149,36 с, ~132 BPM).
Собран локально из материалов заказчика: 7 AI-видео + 2 фото.

## Результат

| файл | что это |
|---|---|
| `media/y_russkiy_muzhik_1080x1920.mp4` | 1080×1920, 30 fps, H.264 + AAC 192 kbps |
| `media/poster.jpg` | кадр-обложка |

## Как собрано

1. `prep.py` — декодирует 7 видео в `assets/src/*.npy` (640×640, 30 fps),
   готовит квадратные кропы фото, пишет сетку бит.
2. `render.py` — таймлайн из 65 шотов, привязанный к фразам трека; для каждого
   кадра: фон (блюр + грейд), карточка/овал/фулл-кадр/квадро, вспышка на сильную
   долю, speed-lines, whip-переход, зерно и виньетка, крупный текст.

## Ритм

- BPM 131,95, сетка бит в `assets/beats.json` (сдвиг −0,055 с по басу).
- Смена шота — на границе музыкальных фраз, удар/вспышка — на сильных долях.
- Тихие фрагменты (27–31, 71–74, 87–90, 102–105) — статичные карточки и овал.

## Пересборка

```bash
export PYTHONPATH=/home/user/.pylibs
python3 clip2/prep.py
python3 clip2/render.py --preview 2.5,29,60
python3 clip2/render.py --out clip2/media/silent.mp4 --crf 22
ffmpeg -y -i clip2/media/silent.mp4 -i clip2/assets/song.wav \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest \
  -movflags +faststart clip2/media/y_russkiy_muzhik_1080x1920.mp4
```
