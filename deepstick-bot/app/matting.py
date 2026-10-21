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

from .encode import encode_frames, probe
from .ffmpeg_util import find_ffmpeg

log = logging.getLogger(__name__)

_SESSION = None
_SESSION_TRIED = False
LAST_SESSION_ERRORS: list[str] = []  # для диагностики из пробы/админки

# Сначала модель сегментации именно людей, потом универсальные.
_MODELS = ("u2net_human_seg", "u2net", "isnet-general-use")


def _get_session():
    global _SESSION, _SESSION_TRIED
    if _SESSION_TRIED:
        return _SESSION
    _SESSION_TRIED = True
    try:
        from rembg import new_session  # type: ignore
    except Exception as e:
        log.info("rembg не установлен — вырезание фона из видео недоступно")
        LAST_SESSION_ERRORS.append(f"import rembg: {type(e).__name__}: {str(e)[:300]}")
        return None
    for model in _MODELS:
        try:
            _SESSION = new_session(model)  # модель качается 1 раз в ~/.u2net
            log.info("Вырезание фона из видео: модель %s", model)
            return _SESSION
        except Exception as e:
            log.warning("Модель %s не загрузилась, пробую следующую", model)
            LAST_SESSION_ERRORS.append(f"{model}: {type(e).__name__}: {str(e)[:200]}")
    return None


def _cut_frame(png_bytes: bytes, session) -> Image.Image:  # noqa: ANN001
    from rembg import remove  # type: ignore

    out = remove(png_bytes, session=session)
    img = Image.open(io.BytesIO(out)).convert("RGBA")
    # лёгкое сглаживание рваных краёв маски
    alpha = img.split()[3].filter(ImageFilter.GaussianBlur(1.0))
    img.putalpha(alpha)
    return img  # без обводок и рамок


MAX_STICKER_SECONDS = 2.9  # лимит Telegram — 3 c, берём с запасом


def sticker_frame_cap(fps: int, max_seconds: float = MAX_STICKER_SECONDS) -> int:
    """Сколько кадров можно оставить, чтобы WebM не превысил лимит Telegram."""
    return max(1, int(max_seconds * fps))


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
        # Нейросети отдают 3+ секунды, а Telegram не берёт стикеры длиннее
        # 3 c (STICKER_VIDEO_LONG) — обрезаем хвост до безопасных 2.9 c.
        cap = sticker_frame_cap(fps)
        if len(raw_frames) > cap:
            log.info("Обрезаю стикер: %s -> %s кадров (лимит Telegram)",
                     len(raw_frames), cap)
            raw_frames = raw_frames[:cap]

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
