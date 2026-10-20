#!/usr/bin/env python3
"""Render Matt's reaction using the repository's video-by-code renderer.

Example:
  python3 mat-bot/render_trailer.py --trailer google_drive/VID_20261020_211631_568.mp4 --preview
  python3 mat-bot/render_trailer.py --trailer google_drive/VID_20261020_211631_568.mp4
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "mat-bot"
SKILL = ROOT / "skills" / "video-by-code"
CONFIG = PROJECT / "mat-trailer.json"
FPS = 30
TRAILER_AT = 5.45
FRAME_X, FRAME_Y, FRAME_W = 40, 650, 1000
FRAME_COLOR = "0xF13B46"


def ffmpeg_path() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise SystemExit("Install dependencies: python3 -m pip install Pillow numpy imageio-ffmpeg") from exc


def duration_of(ffmpeg: str, media: Path) -> float:
    proc = subprocess.run([ffmpeg, "-hide_banner", "-i", str(media)],
                          capture_output=True, text=True)
    match = re.search(r"Duration: (\d+):(\d+):([\d.]+)", proc.stderr)
    if not match:
        raise RuntimeError(f"Could not read media duration: {media}")
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))


def extract_voice(ffmpeg: str, source: Path, start: float, length: float, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fade_out = max(0.0, length - 0.045)
    subprocess.run([
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-ss", f"{start:.3f}", "-t", f"{length:.3f}",
        "-af", f"afade=t=in:st=0:d=0.025,afade=t=out:st={fade_out:.3f}:d=0.045",
        "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(target)
    ], check=True)


def render_base(ffmpeg: str, work: Path, preview: bool) -> Path:
    voice_dir = PROJECT / "voice-trailer"
    # These are clean phrase boundaries in Matt's existing repository recordings:
    # voice3/01-privet: «Привет! Я Мэт.»; voice9/05-svyaz: «Я на связи круглосуточно.»
    extract_voice(ffmpeg, PROJECT / "voice3" / "01-privet.mp3", 0.0, 1.19,
                  voice_dir / "intro.wav")
    extract_voice(ffmpeg, PROJECT / "voice9" / "05-svyaz.mp3", 1.02, 1.17,
                  voice_dir / "online.wav")
    work.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(SKILL / "scripts" / "render.py"), str(CONFIG), "--out", str(work)]
    if preview:
        cmd.append("--preview")
    subprocess.run(cmd, cwd=ROOT, check=True)
    return work / ("черновик.mp4" if preview else "base.mp4")


def compose(ffmpeg: str, base: Path, trailer: Path, output: Path,
            preview: bool, trailer_duration: float) -> None:
    base_width = 360 if preview else 1080
    base_height = 640 if preview else 1920
    scale = base_width / 1080
    x = int(round(FRAME_X * scale))
    y = int(round(FRAME_Y * scale))
    width = int(round(FRAME_W * scale))
    width -= width % 2
    # Preserve the original 2176:928 trailer ratio, keeping the landscape insert crisp.
    height = int(round(width * 928 / 2176))
    height -= height % 2
    pad = max(2, int(round(14 * scale)))
    border = max(2, int(round(4 * scale)))
    bx, by = x - pad, y - pad
    bw, bh = width + 2 * pad, height + 2 * pad
    end = TRAILER_AT + trailer_duration
    delay_ms = round(TRAILER_AT * 1000)

    # Put the horizontal trailer into a red-edged cinema frame in the portrait chat.
    # The original trailer soundtrack is mixed quietly under Matt's recorded lines.
    filters = (
        f"[1:v]trim=duration={trailer_duration:.3f},setpts=PTS-STARTPTS+{TRAILER_AT}/TB,"
        f"fps={FPS},scale={width}:{height}:flags=lanczos,setsar=1,format=yuv420p[film];"
        f"[0:v]drawbox=x={bx}:y={by}:w={bw}:h={bh}:color={FRAME_COLOR}:t={border}:"
        f"enable='between(t,{TRAILER_AT:.3f},{end:.3f})'[plate];"
        f"[plate][film]overlay=x={x}:y={y}:eof_action=pass:shortest=0:"
        f"enable='between(t,{TRAILER_AT:.3f},{end:.3f})',format=yuv420p[v];"
        f"[0:a]volume=0.82[chat];"
        f"[1:a]atrim=duration={trailer_duration:.3f},asetpts=PTS-STARTPTS,"
        f"afade=t=in:st=0:d=0.18,afade=t=out:st={max(0.0, trailer_duration - 0.28):.3f}:d=0.25,"
        f"volume=0.50,adelay={delay_ms}|{delay_ms}[film_audio];"
        f"[chat][film_audio]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
        f"alimiter=limit=0.95[a]"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(base), "-i", str(trailer),
        "-filter_complex", filters, "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast" if preview else "medium",
        "-crf", "27" if preview else "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output)
    ], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trailer", required=True, type=Path, help="Original horizontal trailer file")
    parser.add_argument("--out", type=Path, help="Final MP4 path")
    parser.add_argument("--work", type=Path, default=ROOT / "work" / "mat-trailer-build")
    parser.add_argument("--preview", action="store_true", help="Render and compose a 360x640 preview")
    args = parser.parse_args()
    trailer = args.trailer.resolve()
    if not trailer.is_file():
        parser.error(f"Trailer not found: {trailer}")
    ffmpeg = ffmpeg_path()
    base = render_base(ffmpeg, args.work.resolve(), args.preview)
    output = args.out.resolve() if args.out else (
        args.work.resolve() / "preview-composite.mp4" if args.preview
        else ROOT / "deliverables" / "mat-trailer.mp4"
    )
    compose(ffmpeg, base, trailer, output, args.preview, duration_of(ffmpeg, trailer))
    print(json.dumps({"output": str(output), "preview": args.preview,
                      "trailer_at_s": TRAILER_AT,
                      "trailer_duration_s": round(duration_of(ffmpeg, trailer), 3)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
