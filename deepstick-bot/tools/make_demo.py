#!/usr/bin/env python3
"""Офлайн-демо без Telegram: фото -> видеостикер .webm (+ .gif для предпросмотра).

    python tools/make_demo.py                       # сгенерирует тестовое фото само
    python tools/make_demo.py my.jpg --effect dance --style cartoon
    python tools/make_demo.py my.jpg --no-rembg     # если rembg не стоит
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app.effects import prepare_subject, render_frames  # noqa: E402
from app.encode import encode_frames, probe  # noqa: E402
from app.scenarios import SCENARIOS_BY_ID  # noqa: E402


def sample_photo(path: Path) -> Path:
    """Рисуем условного «человечка», если своего фото под рукой нет."""
    img = Image.new("RGB", (800, 800), (70, 130, 200))
    d = ImageDraw.Draw(img)
    d.ellipse([250, 120, 550, 420], fill=(255, 205, 150))          # лицо
    d.ellipse([320, 240, 360, 280], fill=(20, 20, 20))             # глаза
    d.ellipse([440, 240, 480, 280], fill=(20, 20, 20))
    d.arc([320, 280, 480, 380], start=10, end=170, fill=(20, 20, 20), width=10)  # улыбка
    d.rectangle([220, 430, 580, 790], fill=(220, 60, 60))          # тело
    img.save(path)
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("photo", nargs="?", help="путь к фото (по умолчанию — сгенерируем)")
    ap.add_argument("--effect", default="rocket", help="rocket|laugh|love|wow|dance|fire|portal|hello|yes|no|spin|bounce или id сценария")
    ap.add_argument("--style", default="original", help="original|cartoon|pixel|neon")
    ap.add_argument("--out", default="examples/sticker.webm")
    ap.add_argument("--no-rembg", action="store_true")
    ap.add_argument("--gif", action="store_true", help="ещё и .gif превью рядом")
    args = ap.parse_args()

    effect = SCENARIOS_BY_ID[args.effect].effect if args.effect in SCENARIOS_BY_ID else args.effect
    photo = Path(args.photo) if args.photo else sample_photo(Path("examples/sample.jpg"))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(photo) as img:
        subject = prepare_subject(img.copy(), style=args.style, remove_bg=not args.no_rembg)
    subject.save("examples/subject.png")

    frames_for_gif = []

    def make_frames():
        for f in render_frames(subject, effect, fps=30, duration=2.8):
            if args.gif and len(frames_for_gif) < 84:
                frames_for_gif.append(f.convert("RGBA"))
            yield f

    encode_frames(make_frames, out, fps=30, duration=2.8)
    print("probe:", probe(out))
    if args.gif and frames_for_gif:
        gif = out.with_suffix(".gif")
        bg = [Image.alpha_composite(Image.new("RGBA", f.size, (40, 40, 50, 255)), f).convert("P") for f in frames_for_gif[::2]]
        bg[0].save(gif, save_all=True, append_images=bg[1:], duration=66, loop=0)
        print("gif:", gif)


if __name__ == "__main__":
    main()
