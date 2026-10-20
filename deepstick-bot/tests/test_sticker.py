"""Проверка главного инварианта: файл проходит требования Telegram к видеостикерам."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app.effects import prepare_subject, render_frames  # noqa: E402
from app.encode import MAX_BYTES, encode_frames, probe  # noqa: E402
from app.scenarios import match_scenario  # noqa: E402


def _photo() -> Image.Image:
    img = Image.new("RGB", (600, 600), (60, 120, 190))
    d = ImageDraw.Draw(img)
    d.ellipse([180, 90, 420, 330], fill=(255, 205, 150))
    d.rectangle([150, 350, 450, 590], fill=(220, 60, 60))
    return img


def test_keyword_matching():
    assert match_scenario("Лечу на ракете в космос!").id == "rocket"
    assert match_scenario("дирижирую оркестром котов").id == "bounce"  # нет совпадения -> дефолт
    assert match_scenario("я влюблён").id == "love"


def test_sticker_meets_telegram_spec(tmp_path):
    subject = prepare_subject(_photo(), style="original", remove_bg=False)
    out = tmp_path / "s.webm"
    encode_frames(lambda: render_frames(subject, "bounce", fps=30, duration=1.2),
                  out, fps=30, duration=1.2)
    meta = probe(out)
    assert meta["codec"] == "vp9"
    assert meta["width"] == 512 and meta["height"] == 512
    assert meta["fps"] <= 30
    assert meta["duration"] <= 3.0
    assert meta["size"] <= MAX_BYTES
    assert not meta["has_audio"]
