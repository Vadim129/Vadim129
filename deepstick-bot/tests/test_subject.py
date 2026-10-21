"""Подготовка субъекта: готовую прозрачность не перерезаем, края — гладкие."""
from PIL import Image

from app.effects import has_transparency, prepare_subject


def _cutout(size=200, box=100) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    off = (size - box) // 2
    img.paste(Image.new("RGBA", (box, box), (200, 30, 30, 255)), (off, off))
    return img


def test_has_transparency():
    assert not has_transparency(Image.new("RGB", (10, 10), (255, 255, 255)))
    assert not has_transparency(Image.new("RGBA", (10, 10), (1, 2, 3, 255)))
    assert has_transparency(_cutout())


def test_prepare_subject_keeps_existing_cutout():
    out = prepare_subject(_cutout(), style="original", remove_bg=True)
    assert out.mode == "RGBA"
    assert out.split()[3].getpixel((0, 0)) == 0  # угол остался прозрачным
    # край сглажен: есть полупрозрачные пиксели, а не рваная бинарная маска
    hist = out.split()[3].histogram()
    assert sum(hist[1:255]) > 0
