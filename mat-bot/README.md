# Мэт — реакция на трейлер

Сценарий и сборка используют настоящую фотографию Мэта, его голосовые записи и рендерер `skills/video-by-code` из этого репозитория.

## Сборка

```bash
python3 -m pip install Pillow numpy imageio-ffmpeg
python3 mat-bot/render_trailer.py \
  --trailer google_drive/VID_20261020_211631_568.mp4 \
  --preview
python3 mat-bot/render_trailer.py \
  --trailer google_drive/VID_20261020_211631_568.mp4
```

Скрипт вырезает две чистые фразы из записей Мэта в `voice3/` и `voice9/`, строит вертикальную основу по `mat-trailer.json`, помещает горизонтальный трейлер в центральную кинорамку и подмешивает его оригинальный звук. Исходный видеоматериал не хранится в репозитории: перед сборкой передайте локальный файл через `--trailer`.

Полный разбор исходника: `trailer-analysis.md`.
