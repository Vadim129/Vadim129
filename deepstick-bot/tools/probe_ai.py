#!/usr/bin/env python3
"""Проверка бесплатных image-to-video нейросетей (HF Spaces) из CI.

Пробует кандидатов по очереди реальной генерацией, печатает вердикты
аннотациями GitHub (::notice/::error), чтобы результат был виден без логов.
Останавливается на первом рабочем спейсе и проверяет конвертацию в стикер.
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROMPT = ("a happy person jumps up and down with joy, waving both arms, "
          "big smile, lively full-body motion, seamless loop")


def note(kind: str, title: str, msg: str) -> None:
    flat = " | ".join(str(msg).splitlines())[:900]
    print(f"::{kind} title={title}::{flat}", flush=True)


def make_sample(path: Path) -> Path:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (512, 512), (70, 130, 200))
    d = ImageDraw.Draw(img)
    d.ellipse([170, 60, 340, 230], fill=(255, 205, 150))
    d.ellipse([215, 130, 240, 155], fill=(20, 20, 20))
    d.ellipse([275, 130, 300, 155], fill=(20, 20, 20))
    d.arc([220, 140, 295, 200], start=10, end=170, fill=(20, 20, 20), width=6)
    d.rectangle([160, 240, 350, 470], fill=(220, 60, 60))
    d.rectangle([110, 250, 155, 380], fill=(255, 205, 150))
    d.rectangle([355, 250, 400, 380], fill=(255, 205, 150))
    img.save(path)
    return path


def attempt_ltx(sample: Path, out: Path) -> None:
    # Официальный спейс Lightricks, настоящий image-to-video (LTX distilled).
    from gradio_client import Client, handle_file

    client = Client("Lightricks/ltx-video-distilled", token=os.getenv("HF_TOKEN") or None)
    result = client.predict(
        prompt=PROMPT,
        input_image_filepath=handle_file(str(sample)),
        height_ui=512, width_ui=512, duration_ui=2.5,
        api_name="/image_to_video")
    from app.ai_video import _extract_video_file

    _extract_video_file(result, out)


def attempt_wan_fast(sample: Path, out: Path) -> None:
    # Параметры ровно как у бота: квадрат 512, 2.5 c, 6 шагов.
    from gradio_client import Client, handle_file

    client = Client("multimodalart/wan2-1-fast", token=os.getenv("HF_TOKEN") or None)
    result = client.predict(
        input_image=handle_file(str(sample)), prompt=PROMPT,
        height=512, width=512, duration_seconds=2.5, steps=6,
        api_name="/generate_video")
    from app.ai_video import _extract_video_file

    _extract_video_file(result, out)


def attempt_first_last(sample: Path, out: Path) -> None:
    from gradio_client import Client, handle_file

    client = Client("multimodalart/wan-2-2-first-last-frame",
                    token=os.getenv("HF_TOKEN") or None)
    result = client.predict(
        start_image_pil=handle_file(str(sample)),
        end_image_pil=handle_file(str(sample)),
        prompt=PROMPT, duration_seconds=2.1, steps=8, api_name="/generate_video")
    from app.ai_video import _extract_video_file

    _extract_video_file(result, out)


def attempt_wan_official(sample: Path, out: Path) -> None:
    import time as _time

    from gradio_client import Client, handle_file

    from app.ai_video import _extract_video_file

    client = Client("Wan-AI/Wan2.1", token=os.getenv("HF_TOKEN") or None)
    client.predict(prompt=PROMPT, image=handle_file(str(sample)),
                   api_name="/i2v_generation_async")
    deadline = _time.time() + 1200
    while _time.time() < deadline:
        _time.sleep(20)
        result = client.predict(api_name="/status_refresh")
        try:
            _extract_video_file(result, out)
            return
        except Exception:
            continue
    raise RuntimeError("Wan-AI/Wan2.1: видео не появилось за 20 минут")


ATTEMPTS = [
    ("Lightricks/ltx-video-distilled", attempt_ltx),
    ("multimodalart/wan2-1-fast", attempt_wan_fast),
    ("multimodalart/wan-2-2-first-last-frame", attempt_first_last),
    ("Wan-AI/Wan2.1", attempt_wan_official),
]


def main() -> int:
    note("notice", "AI probe start",
         f"HF_TOKEN задан: {bool(os.getenv('HF_TOKEN'))}; кандидатов: {len(ATTEMPTS)}")
    sample = make_sample(Path("/tmp/probe_input.jpg"))
    out = Path("/tmp/probe_output.mp4")
    for name, fn in ATTEMPTS:
        t0 = time.time()
        try:
            fn(sample, out)
        except Exception as e:
            tb = traceback.format_exc(limit=3)
            note("error", f"AI probe FAIL {name}",
                 f"{type(e).__name__}: {e} || {tb} ({time.time() - t0:.0f} c)")
            continue
        size = out.stat().st_size if out.exists() else 0
        if size <= 10_000:
            note("error", f"AI probe FAIL {name}", f"пустой результат {size} байт")
            continue
        note("notice", f"AI probe OK {name}",
             f"видео {size} байт за {time.time() - t0:.0f} c")
        try:
            from app.encode import convert_video, probe

            webm = convert_video(out, Path("/tmp/probe_sticker.webm"))
            note("notice", "AI probe sticker OK", str(probe(webm)))
        except Exception as e:
            note("error", "AI probe sticker FAIL", str(e))
            return 1
        # Главное требование: стикер должен быть вырезанной фигуркой на прозрачности
        try:
            from app import matting
            from app.matting import matte_encode

            session = matting._get_session()
            note("notice", "AI probe matting session",
                 f"session={session!r}; errors={matting.LAST_SESSION_ERRORS}")
            matted = Path("/tmp/probe_matted.webm")
            if not matte_encode(out, matted):
                note("error", "AI probe matting FAIL", "matte_encode вернул False")
                return 1
            from app.encode import probe as probe2

            note("notice", "AI probe matting OK", str(probe2(matted)))
        except Exception as e:
            note("error", "AI probe matting FAIL", str(e))
            return 1
        return 0
    # Видео нет (например, суточная ZeroGPU-квота исчерпана) — всё равно
    # проверяем вырезание фона на синтетическом видео из тестового фото:
    # маттинг обязан работать независимо от нейросети.
    try:
        import subprocess

        synth = Path("/tmp/probe_synth.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-loop", "1", "-i", str(sample), "-t", "2",
             "-vf", "scale=512:512:force_original_aspect_ratio=increase,crop=512:512,"
                    "zoompan=z='1+0.1*on/50':d=50:s=512x512:fps=25",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(synth)],
            check=True, capture_output=True, timeout=120)
        from app import matting
        from app.encode import probe as probe_fn
        from app.matting import matte_encode

        session = matting._get_session()
        note("notice", "AI probe matting session (synthetic)",
             f"session={session!r}; errors={matting.LAST_SESSION_ERRORS}")
        matted = Path("/tmp/probe_matted.webm")
        if matte_encode(synth, matted):
            note("notice", "AI probe matting OK (synthetic)", str(probe_fn(matted)))
            # Замеряем реальную прозрачность первого кадра результата
            frame_png = Path("/tmp/probe_matted_frame.png")
            subprocess.run(["ffmpeg", "-y", "-i", str(matted), "-frames:v", "1",
                            str(frame_png)], capture_output=True, timeout=60)
            from PIL import Image

            alpha = Image.open(frame_png).convert("RGBA").split()[3]
            hist = alpha.histogram()
            transparent = sum(hist[:128]) / (512 * 512) * 100
            note("notice", "AI probe matting alpha",
                 f"прозрачных пикселей в кадре: {transparent:.0f}%")
        else:
            note("error", "AI probe matting FAIL (synthetic)", "matte_encode вернул False")
    except Exception as e:
        note("error", "AI probe matting FAIL (synthetic)", f"{type(e).__name__}: {e}")
    note("error", "AI probe ALL FAILED", "ни один бесплатный спейс не сработал")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
