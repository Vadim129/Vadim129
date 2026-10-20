import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app.db import Database  # noqa: E402
from app.effects import render_frames, stylize  # noqa: E402
from app.scenarios import SCENARIOS, STYLES, match_scenario  # noqa: E402


def test_db_roundtrip(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_user(7, "Ann", "Ann")
    assert db.get_settings(7) == {"remove_bg": True, "auto_pack": True}
    assert db.toggle_setting(7, "remove_bg") is False
    assert db.get_settings(7)["remove_bg"] is False
    gid = db.log_generation(7, "photo", "🚀 Лечу на ракете", "original", "🚀", "FILE1")
    assert db.get_generation(gid, 7)["file_id"] == "FILE1"
    assert db.get_generation(gid, 999) is None  # чужую историю не отдаём
    db.set_last_job(7, "/tmp/p.jpg", "neon", "rocket", None, "auto")
    last = db.get_last_job(7)
    assert last["style"] == "neon" and last["scenario_id"] == "rocket"
    assert db.stats()["users"] == 1 and db.stats()["generations"] == 1


def test_all_effects_render_frames():
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([40, 20, 160, 140], fill=(255, 205, 150, 255))
    d.rectangle([50, 140, 150, 195], fill=(220, 60, 60, 255))
    for sc in SCENARIOS:
        frames = list(render_frames(img, sc.effect, fps=2, duration=1.0))
        assert len(frames) == 2
        assert all(f.size == (512, 512) and f.mode == "RGBA" for f in frames), sc.id


def test_all_styles():
    img = Image.new("RGB", (60, 60), (120, 80, 40))
    for st in STYLES:
        out = stylize(img, st.id)
        assert out.size == (60, 60), st.id


def test_extract_video_file(tmp_path):
    from app.ai_video import _extract_video_file

    src = tmp_path / "gen.mp4"
    src.write_bytes(b"0" * 2048)
    out = tmp_path / "out.mp4"
    # формат ответа multimodalart/wan2-1-fast: ({video: {...path}}, seed)
    _extract_video_file(({"video": {"path": str(src)}}, 42), out)
    assert out.read_bytes() == b"0" * 2048


def test_build_prompt_strong_motion():
    from app.scenarios import SCENARIOS_BY_ID, STYLES_BY_ID, build_prompt

    p = build_prompt(STYLES_BY_ID["original"], SCENARIOS_BY_ID["cry"], "плачу навзрыд")
    assert "NOT only blinking" in p          # запрет «одного моргания»
    assert "BIG, CLEAR, CONTINUOUS" in p     # требование больших движений
    assert "плачу навзрыд" in p              # текст пользователя не потерян
    assert "tears stream down" in p          # прописное движение сценария


def test_new_keywords():
    assert match_scenario("хочу дождь из денег").id == "money"
    assert match_scenario("я так устал, сплю").id == "sleep"
    assert match_scenario("это победа, я чемпион!").id == "winner"
