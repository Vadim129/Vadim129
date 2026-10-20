"""Покадровое вырезание фона из сгенерированного нейросетью видео.

Зачем: image-to-video возвращает прямоугольное видео с фоном исходного фото,
а стикер должен быть «фигуркой» на прозрачности. Поэтому:
  видео -> кадры PNG -> rembg по каждому кадру (модель сегментации человека)
  -> белая обводка -> WebM VP9 с альфой (yuva420p).

Если rembg/модель недоступны — возвращаем False, и вызывающий код сделает
обычную прямоугольную конверсию (бот не должен падать из-за фона).
"""
from __future__ import annotations

import io
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter

from .effects import _add_white_stroke
from .encode import encode_frames, probe
from .ffmpeg_util import find_ffmpeg

log = logging.getLogger(__name__)

_SESSION = None
_SESSION_TRIED = False

# Сначала модель сегментации именно людей, потом универсальные.
_MODELS = ("u2net_human_seg", "u2net", "isnet-general-use")


def _get_session():
    global _SESSION, _SESSION_TRIED
    if _SESSION_TRIED:
        return _SESSION
    _SESSION_TRIED = True
    try:
        from rembg import new_session  # type: ignore
    except Exception:
        log.info("rembg не установлен — вырезание фона из видео недоступно")
        return None
    for model in _MODELS:
        try:
            _SESSION = new_session(model)  # модель качается 1 раз в ~/.u2net
            log.info("Вырезание фона из видео: модель %s", model)
            return _SESSION
        except Exception:
            log.warning("Модель %s не загрузилась, пробую следующую", model)
    return None


def _cut_frame(png_bytes: bytes, session) -> Image.Image:  # noqa: ANN001
    from rembg import remove  # type: ignore

    out = remove(png_bytes, session=session)
    img = Image.open(io.BytesIO(out)).convert("RGBA")
    # лёгкое сглаживание рваных краёв маски
    alpha = img.split()[3].filter(ImageFilter.GaussianBlur(0.7))
    img.putalpha(alpha)
    return _add_white_stroke(img, width=6)


def matte_encode(mp4: Path, webm: Path, fps_cap: int = 16) -> bool:
    """MP4 от нейросети -> прозрачный WebM-стикер с вырезанной фигуркой."""
    session = _get_session()
    if session is None:
        return False
    ffmpeg = find_ffmpeg()
    meta = probe(mp4)
    src_fps = meta["fps"] or fps_cap
    fps = max(8, min(fps_cap, int(round(src_fps))))
    tmp = Path(tempfile.mkdtemp(prefix="matte_"))
    try:
        frames_dir = tmp / "frames"
        frames_dir.mkdir()
        vf = (f"fps={fps},scale=512:512:force_original_aspect_ratio=decrease,"
              "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000")
        proc = subprocess.run(
            [ffmpeg, "-y", "-i", str(mp4), "-vf", vf, str(frames_dir / "%04d.png")],
            capture_output=True, text=True)
        if proc.returncode != 0:
            log.warning("ffmpeg не извлёк кадры: %s", proc.stderr[-300:])
            return False
        raw_frames = sorted(frames_dir.glob("*.png"))
        if not raw_frames:
            return False

        matted_dir = tmp / "matted"
        matted_dir.mkdir()
        kept: list[Path] = []
        for i, frame_path in enumerate(raw_frames):
            try:
                img = _cut_frame(frame_path.read_bytes(), session)
            except Exception:
                log.exception("Вырезание кадра %s упало", frame_path.name)
                return False
            out_path = matted_dir / f"{i:04d}.png"
            img.save(out_path)
            kept.append(out_path)
        log.info("Вырезано кадров: %s @ %s fps", len(kept), fps)

        def frames():
            for p in kept:
                with Image.open(p) as im:
                    yield im.convert("RGBA").copy()

        encode_frames(frames, webm, fps=fps, duration=len(kept) / fps)
        return True
    except Exception:
        log.exception("Покадровое вырезание фона не удалось")
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
