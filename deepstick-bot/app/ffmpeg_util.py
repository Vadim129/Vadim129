"""Поиск ffmpeg: системный -> env FFMPEG_PATH -> бинарь из imageio-ffmpeg."""
from __future__ import annotations

import os
import shutil


def find_ffmpeg() -> str:
    env = os.getenv("FFMPEG_PATH")
    if env and os.path.exists(env):
        return env
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "ffmpeg не найден. Поставь ffmpeg в систему или `pip install imageio-ffmpeg`."
        ) from exc
