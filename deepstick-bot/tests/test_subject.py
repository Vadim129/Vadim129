"""Правила фона: вырезанное не режем никогда; рамок нет ни в одном режиме."""
from PIL import Image

from app.effects import has_transparency, prepare_subject


def _cutout(size=200, box=100) -> Image.Image:
    from PIL import ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    off = (size - box) // 2
    ImageDraw.Draw(img).ellipse([off, off, off + box, off + box],
                                fill=(200, 30, 30, 255))
    return img


def _white_opaque_pixels(img: Image.Image) -> int:
    return sum(1 for r, g, b, a in img.getdata()
               if (r, g, b, a) == (255, 255, 255, 255))


def test_has_transparency():
    assert not has_transparency(Image.new("RGB", (10, 10), (255, 255, 255)))
    assert not has_transparency(Image.new("RGBA", (10, 10), (1, 2, 3, 255)))
    assert has_transparency(_cutout())


def test_cutout_never_recut_and_no_frame():
    for remove_bg in (True, False):  # ни в каком режиме
        out = prepare_subject(_cutout(), style="original", remove_bg=remove_bg)
        assert out.mode == "RGBA"
        assert out.split()[3].getpixel((0, 0)) == 0      # угол прозрачный
        assert _white_opaque_pixels(out) == 0            # никакой белой рамки
        hist = out.split()[3].histogram()
        assert sum(hist[1:255]) > 0                      # край гладкий


def test_opaque_without_cutting_stays_plain_rectangle():
    photo = Image.new("RGB", (120, 90), (30, 60, 90))
    out = prepare_subject(photo, style="original", remove_bg=False)
    assert out.split()[3].getpixel((0, 0)) == 255        # как есть, без фона-рамки
    assert _white_opaque_pixels(out) == 0
