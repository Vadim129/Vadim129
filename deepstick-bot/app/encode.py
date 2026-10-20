"""Кодирование в видеостикер Telegram.

Жёсткие требования Telegram (core.telegram.org/stickers):
  WebM + VP9, одна сторона ровно 512 px, <= 3 c, <= 30 FPS,
  без звука, <= 256 КБ, поддерживается прозрачность (yuva420p).
Битрейт подбираем итеративно, пока файл не влезет в лимит.
"""
from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

from PIL import Image

from .ffmpeg_util import find_ffmpeg

MAX_BYTES = 256 * 1024
CANVAS = 512


def _run(cmd: list[str], stdin_data: Iterator[bytes] | None = None) -> None:
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE if stdin_data else None,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        if stdin_data is not None:
            assert proc.stdin
            for chunk in stdin_data:
                proc.stdin.write(chunk)
            proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "ignore") if proc.stderr else ""
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg упал: {err[-1500:]}")
    except BrokenPipeError:
        err = proc.stderr.read().decode("utf-8", "ignore") if proc.stderr else ""
        proc.wait()
        raise RuntimeError(f"ffmpeg упал: {err[-1500:]}") from None


def _vp9_args(bitrate_kbps: int) -> list[str]:
    return [
        "-an", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
        "-b:v", f"{bitrate_kbps}k", "-maxrate", f"{bitrate_kbps}k",
        "-bufsize", f"{bitrate_kbps * 2}k",
        "-deadline", "good", "-cpu-used", "2", "-row-mt", "1",
        "-auto-alt-ref", "0", "-metadata:s:v:0", "alpha_mode=1",
    ]


def encode_frames(make_frames: Callable[[], Iterator[Image.Image]], out: Path,
                  fps: int = 30, duration: float = 2.8,
                  max_bytes: int = MAX_BYTES) -> Path:
    """Поток Pillow-кадров -> WebM. make_frames вызывается заново на каждой попытке."""
    ffmpeg = find_ffmpeg()
    bitrate = int(max_bytes * 8 / max(duration, 0.1) / 1000 * 0.92)
    for _attempt in range(5):
        def raw() -> Iterator[bytes]:
            for frame in make_frames():
                yield frame.convert("RGBA").tobytes()

        cmd = [ffmpeg, "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
               "-s", f"{CANVAS}x{CANVAS}", "-r", str(fps), "-i", "-",
               *_vp9_args(max(60, bitrate)), str(out)]
        _run(cmd, raw())
        size = out.stat().st_size
        if size <= max_bytes:
            return out
        bitrate = int(bitrate * (max_bytes / size) * 0.88)
    raise RuntimeError(f"Не удалось ужать стикер до {max_bytes} байт (вышло {out.stat().st_size})")


def probe(path: Path) -> dict:
    """Метаданные файла через `ffmpeg -i` (ffprobe не нужен)."""
    ffmpeg = find_ffmpeg()
    proc = subprocess.run([ffmpeg, "-i", str(path)], capture_output=True, text=True)
    info = proc.stderr
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    video = re.search(r"Video: (\w+).*? (\d+)x(\d+).*?([\d.]+) fps", info)
    seconds = 0.0
    if dur:
        seconds = int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3))
    return {
        "codec": video.group(1) if video else None,
        "width": int(video.group(2)) if video else None,
        "height": int(video.group(3)) if video else None,
        "fps": float(video.group(4)) if video else None,
        "duration": seconds,
        "size": Path(path).stat().st_size,
        "has_audio": "Audio:" in info,
    }


def convert_video(inp: Path, out: Path, max_seconds: float = 2.97,
                  max_bytes: int = MAX_BYTES) -> Path:
    """Любое видео/GIF -> видеостикер: трим, 512x512 с прозрачной подложкой, VP9."""
    ffmpeg = find_ffmpeg()
    meta = probe(inp)
    dur = min(meta["duration"] or max_seconds, max_seconds) or max_seconds
    bitrate = int(max_bytes * 8 / dur / 1000 * 0.92)
    vf = ("fps=30,scale=512:512:force_original_aspect_ratio=decrease,"
          "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000,format=yuva420p")
    for _attempt in range(5):
        cmd = [ffmpeg, "-y", "-i", str(inp), "-t", f"{dur:.2f}", "-vf", vf,
               *_vp9_args(max(60, bitrate)), str(out)]
        _run(cmd)
        size = out.stat().st_size
        if size <= max_bytes:
            return out
        bitrate = int(bitrate * (max_bytes / size) * 0.88)
    raise RuntimeError(f"Не удалось ужать видео до {max_bytes} байт (вышло {out.stat().st_size})")
