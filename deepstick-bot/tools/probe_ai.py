#!/usr/bin/env python3
"""Проверка реестра бесплатных image-to-video нейросетей (HF Spaces) из CI.

Идёт по SPACE_SPECS из app.ai_video; каждый спейс пробует с HF_TOKEN
и анонимно (разные пулы ZeroGPU-квоты). Вердикты — аннотациями GitHub
(::notice/::error), чтобы результат был виден без скачивания логов.
Первый успешный результат дополнительно проверяется на конвертацию
в стикер и покадровое вырезание фона (фигурка на прозрачности).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROMPT = ("a happy person jumps up and down with joy, waving both arms, "
          "big smile, lively full-body motion, seamless loop")
ATTEMPT_TIMEOUT = 420  # секунд на одну попытку одного спейса
MAX_VERIFIED = 4       # сколько успехов достаточно подтвердить за один запуск


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


def check_sticker_and_matting(video: Path) -> bool:
    """Полный путь стикера: конвертация + вырезанная фигурка на прозрачности."""
    try:
        from app.encode import convert_video, probe

        webm = convert_video(video, Path("/tmp/probe_sticker.webm"))
        note("notice", "AI probe sticker OK", str(probe(webm)))
    except Exception as e:
        note("error", "AI probe sticker FAIL", str(e))
        return False
    try:
        from app import matting
        from app.encode import probe as probe_fn
        from app.matting import matte_encode

        session = matting._get_session()
        note("notice", "AI probe matting session",
             f"session={session!r}; errors={matting.LAST_SESSION_ERRORS}")
        matted = Path("/tmp/probe_matted.webm")
        if not matte_encode(video, matted):
            note("error", "AI probe matting FAIL", "matte_encode вернул False")
            return False
        note("notice", "AI probe matting OK", str(probe_fn(matted)))
        # Прозрачность меряем через libvpx-vp9: нативный декодер теряет альфу
        frame_png = Path("/tmp/probe_matted_frame.png")
        subprocess.run(["ffmpeg", "-y", "-c:v", "libvpx-vp9", "-i", str(matted),
                        "-frames:v", "1", str(frame_png)],
                       capture_output=True, timeout=60)
        from PIL import Image

        alpha = Image.open(frame_png).convert("RGBA").split()[3]
        hist = alpha.histogram()
        transparent = sum(hist[:128]) / (512 * 512) * 100
        note("notice", "AI probe matting alpha",
             f"прозрачных пикселей в кадре: {transparent:.0f}%")
        return True
    except Exception as e:
        note("error", "AI probe matting FAIL", str(e))
        return False


def check_matting_synthetic(sample: Path) -> None:
    """Видео нет (квоты исчерпаны) — проверяем вырезание на синтетическом видео."""
    try:
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
            frame_png = Path("/tmp/probe_matted_frame.png")
            subprocess.run(["ffmpeg", "-y", "-c:v", "libvpx-vp9", "-i", str(matted),
                            "-frames:v", "1", str(frame_png)],
                           capture_output=True, timeout=60)
            from PIL import Image

            alpha = Image.open(frame_png).convert("RGBA").split()[3]
            hist = alpha.histogram()
            transparent = sum(hist[:128]) / (512 * 512) * 100
            note("notice", "AI probe matting alpha (synthetic)",
                 f"прозрачных пикселей в кадре: {transparent:.0f}%")
        else:
            note("error", "AI probe matting FAIL (synthetic)", "matte_encode вернул False")
    except Exception as e:
        note("error", "AI probe matting FAIL (synthetic)", f"{type(e).__name__}: {e}")


def main() -> int:
    from app.ai_video import SPACE_SPECS, _call_space_sync, _is_quota_error

    note("notice", "AI probe start",
         f"HF_TOKEN задан: {bool(os.getenv('HF_TOKEN'))}; спейсов: {len(SPACE_SPECS)}")
    try:
        from huggingface_hub import get_zero_gpu_quota

        q = get_zero_gpu_quota()  # токен подхватывается из HF_TOKEN окружения
        note("notice", "AI probe ZeroGPU quota",
             f"осталось {q.remaining} c из {q.base}; сброс: {q.resets_at} UTC")
    except Exception as e:
        note("notice", "AI probe ZeroGPU quota", f"не удалось узнать: {e}")

    sample = make_sample(Path("/tmp/probe_input.jpg"))
    token = os.getenv("HF_TOKEN") or None
    dead: set[str] = set()
    verified: list[str] = []
    checked_pipeline = False

    for spec in SPACE_SPECS:
        if len(verified) >= MAX_VERIFIED:
            break
        for ident, tok in (("token", token), ("anon", None)):
            if ident == "token" and not token:
                continue
            if ident in dead or len(verified) >= MAX_VERIFIED:
                continue
            out = Path(f"/tmp/probe_{spec['id'].replace('/', '_')}_{ident}.mp4")
            t0 = time.time()
            try:
                ex = ThreadPoolExecutor(max_workers=1)
                fut = ex.submit(_call_space_sync, spec, sample, PROMPT, out, tok)
                try:
                    fut.result(timeout=ATTEMPT_TIMEOUT)
                finally:
                    ex.shutdown(wait=False)  # зависший вызов не держим: CI убьёт job
            except FutureTimeout:
                note("error", f"AI probe FAIL {spec['id']} [{ident}]",
                     f"таймаут {ATTEMPT_TIMEOUT} c")
                continue
            except Exception as e:
                if _is_quota_error(e):
                    dead.add(ident)
                tb = traceback.format_exc(limit=3)
                note("error", f"AI probe FAIL {spec['id']} [{ident}]",
                     f"{type(e).__name__}: {e} || {tb} ({time.time() - t0:.0f} c)")
                continue
            size = out.stat().st_size if out.exists() else 0
            if size <= 10_000:
                note("error", f"AI probe FAIL {spec['id']} [{ident}]",
                     f"пустой результат {size} байт")
                continue
            note("notice", f"AI probe OK {spec['id']} [{ident}]",
                 f"видео {size} байт за {time.time() - t0:.0f} c")
            verified.append(f"{spec['id']}[{ident}]")
            if not checked_pipeline:
                checked_pipeline = True
                out.replace("/tmp/probe_output.mp4")
                if not check_sticker_and_matting(Path("/tmp/probe_output.mp4")):
                    return 1
            break  # этот спейс работает — следующий

    note("notice", "AI probe verified",
         f"рабочих спейсов подтверждено: {len(verified)}: {', '.join(verified) or 'нет'}")
    if verified:
        return 0
    check_matting_synthetic(sample)
    note("error", "AI probe ALL FAILED", "ни один бесплатный спейс не сработал")
    return 1


if __name__ == "__main__":
    os._exit(main())  # не ждём зависшие потоки попыток на выходе
