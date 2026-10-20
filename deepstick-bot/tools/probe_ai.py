#!/usr/bin/env python3
"""Проверка бесплатной image-to-video нейросети (HF Space) из CI.

Генерирует реальное видео по тестовой картинке и печатает вердикт
аннотациями GitHub (::notice/::error), чтобы результат был виден без логов.

    python tools/probe_ai.py [space] [api_name]
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SPACE = sys.argv[1] if len(sys.argv) > 1 else os.getenv("HF_SPACE", "multimodalart/wan2-1-fast")


def make_sample(path: Path) -> Path:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (512, 512), (70, 130, 200))
    d = ImageDraw.Draw(img)
    d.ellipse([170, 60, 340, 230], fill=(255, 205, 150))
    d.ellipse([215, 130, 240, 155], fill=(20, 20, 20))
    d.ellipse([275, 130, 300, 155], fill=(20, 20, 20))
    d.arc([220, 140, 295, 200], start=10, end=170, fill=(20, 20, 20), width=6)
    d.rectangle([160, 240, 350, 470], fill=(220, 60, 60))
    d.rectangle([110, 250, 155, 380], fill=(255, 205, 150))   # руки
    d.rectangle([355, 250, 400, 380], fill=(255, 205, 150))
    img.save(path)
    return path


def main() -> int:
    print(f"::notice title=AI probe::Проверяю спейс {SPACE} (токен HF задан: {bool(os.getenv('HF_TOKEN'))})")
    sample = make_sample(Path("/tmp/probe_input.jpg"))
    out = Path("/tmp/probe_output.mp4")
    t0 = time.time()
    try:
        from app.ai_video import _via_hf_sync

        _via_hf_sync(
            sample,
            "a happy person jumps up and down with joy, waving both arms, "
            "big smile, lively full-body motion, seamless loop",
            out,
        )
    except Exception as e:
        print(f"::error title=AI probe FAILED::{SPACE}: {type(e).__name__}: {str(e)[:400]}")
        return 1
    dt = time.time() - t0
    size = out.stat().st_size if out.exists() else 0
    if size > 10_000:
        print(f"::notice title=AI probe OK::{SPACE} сгенерировал видео {size} байт за {dt:.0f} c -> /tmp/probe_output.mp4")
        # и сразу проверяем, что из него получается валидный стикер Telegram
        try:
            from app.encode import convert_video, probe

            webm = convert_video(out, Path("/tmp/probe_sticker.webm"))
            print(f"::notice title=AI probe sticker::WebM-стикер из нейросети: {probe(webm)}")
        except Exception as e:
            print(f"::error title=AI probe sticker FAILED::конвертация в стикер: {e}")
            return 1
        return 0
    print(f"::error title=AI probe FAILED::{SPACE}: пустой результат ({size} байт) за {dt:.0f} c")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
