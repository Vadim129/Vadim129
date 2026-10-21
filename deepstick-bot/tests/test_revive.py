"""Оживление наборов: разбор ссылки и имя нового набора."""
from app.packs import alive_pack_name, parse_pack_name


def test_parse_pack_name():
    assert parse_pack_name("https://t.me/addstickers/Cats") == "Cats"
    assert parse_pack_name("t.me/addstickers/Funny_Dogs2?x=1") == "Funny_Dogs2"
    assert parse_pack_name("  https://t.me/addstickers/Abc_123 ") == "Abc_123"
    assert parse_pack_name("JustAName") == "JustAName"
    assert parse_pack_name("привет") is None
    assert parse_pack_name("https://t.me/BotFather") is None
    assert parse_pack_name("") is None
    assert parse_pack_name("ab") is None  # слишком короткое


def test_alive_pack_name():
    name = alive_pack_name("Cats", "mybot")
    assert name == "Cats_alive_by_mybot" and len(name) <= 64
    assert alive_pack_name("weird-name!", "b") == "weird_name_alive_by_b"
    assert len(alive_pack_name("x" * 100, "somebot")) <= 64
    assert alive_pack_name("!!!", "bot").endswith("_alive_by_bot")


def test_scenario_for_emoji():
    import random

    from app.scenarios import SCENARIOS, scenario_for_emoji

    assert scenario_for_emoji("😂").id == "laugh"
    assert scenario_for_emoji("❤️").id == "love"  # с variation selector
    assert scenario_for_emoji("🔥").id == "fire"
    assert scenario_for_emoji("😴").id == "sleep"
    assert scenario_for_emoji("🏆").id == "winner"
    # неизвестный / пустой эмодзи — случайный, но всегда валидный сценарий
    ids = {s.id for s in SCENARIOS}
    assert scenario_for_emoji("🦄", rng=random.Random(1)).id in ids
    assert scenario_for_emoji(None, rng=random.Random(1)).id in ids
    # сид даёт воспроизводимость
    assert (scenario_for_emoji("🦄", rng=random.Random(7)).id
            == scenario_for_emoji("🦄", rng=random.Random(7)).id)
