"""Каталог анимаций: целостность, бесшовность, рендер всех эффектов."""
import math

import pytest
from PIL import Image, ImageDraw

from app.effects import EFFECTS, _sample_params, render_frames
from app.scenarios import (CATEGORIES, EMOJI_TO_SCENARIO, SCENARIOS,
                           SCENARIOS_BY_ID, match_scenario, scenarios_in)


def _subject() -> Image.Image:
    img = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([30, 30, 130, 130], fill=(230, 80, 60, 255))
    d.ellipse([62, 66, 78, 82], fill=(20, 20, 30, 255))
    d.ellipse([84, 66, 100, 82], fill=(20, 20, 30, 255))
    return img


def test_catalog_size_and_links():
    assert 95 <= len(EFFECTS) <= 130
    assert len(SCENARIOS) == len(EFFECTS)  # каталог 1:1
    assert len({s.id for s in SCENARIOS}) == len(SCENARIOS)
    for s in SCENARIOS:
        assert s.effect in EFFECTS, s.id
    for cid, _title in CATEGORIES:
        assert len(scenarios_in(cid)) >= 5, cid
    for sid in EMOJI_TO_SCENARIO.values():
        assert sid in SCENARIOS_BY_ID
    assert match_scenario("лечу на ракете").id == "rocket"
    assert match_scenario("дикий смех").id == "laugh"


def test_all_tracks_seamless():
    for eid, spec in EFFECTS.items():
        a, b = _sample_params(spec, 0.0), _sample_params(spec, 1.0)
        for k in a:
            if k == "rot":  # угловое расстояние: 360° == 0°
                assert abs((a[k] - b[k] + 180) % 360 - 180) < 1e-6, (eid, k)
            else:
                assert abs(a[k] - b[k]) < 1e-6, (eid, k, a[k], b[k])


@pytest.mark.parametrize("effect", sorted(EFFECTS))
def test_effect_renders(effect):
    frames = list(render_frames(_subject(), effect, fps=3, duration=1.0))
    assert len(frames) == 3
    assert all(f.size == (512, 512) and f.mode == "RGBA" for f in frames)
    # движение есть: кадры не все одинаковые
    assert frames[0].tobytes() != frames[1].tobytes() or \
        frames[1].tobytes() != frames[2].tobytes(), effect
