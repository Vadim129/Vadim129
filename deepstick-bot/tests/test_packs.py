import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Database  # noqa: E402
from app.packs import custom_pack_name  # noqa: E402


def test_pack_registry(tmp_path):
    db = Database(tmp_path / "t.db")
    pid = db.add_pack(7, "ds_7_pabc123_by_mybot", "Весёлые")
    db.add_pack(7, "ds_7_pdef456_by_mybot", "Работа")
    db.add_pack(8, "ds_8_pxyz789_by_mybot", "Чужой")
    packs = db.list_packs(7)
    assert [p["id"] for p in packs] == [pid, pid + 1]
    assert db.get_pack_rec(7, pid)["title"] == "Весёлые"
    assert db.get_pack_rec(8, pid) is None  # чужой пак не отдаём
    db.rename_pack_rec(7, pid, "Очень весёлые")
    assert db.get_pack_rec(7, pid)["title"] == "Очень весёлые"
    assert db.delete_pack_rec(7, pid) is True
    assert db.delete_pack_rec(7, pid) is False
    assert len(db.list_packs(7)) == 1


def test_pack_refs(tmp_path):
    db = Database(tmp_path / "t.db")
    db.put_ref(7, "ds_7_pabc_by_b", "FILE_ID_1", "ref0000001")
    rec = db.get_ref("ref0000001", 7)
    assert rec["file_id"] == "FILE_ID_1" and rec["pack_name"] == "ds_7_pabc_by_b"
    assert db.get_ref("ref0000001", 8) is None  # чужой ref не отдаём
    db.delete_ref("ref0000001")
    assert db.get_ref("ref0000001", 7) is None


def test_custom_pack_name_format():
    name = custom_pack_name(123456789, "My_Bot!", "AbC-123456789")
    assert name == "ds_123456789_pabc12345_by_my_bot"
    assert len(name) <= 64
    long_name = custom_pack_name(1, "a" * 40, "zz")
    assert len(long_name) <= 64


def test_active_pack_setting(tmp_path):
    db = Database(tmp_path / "t.db")
    assert db.get_settings(7)["active_pack"] == "main"
    db.set_active_pack(7, "3")
    assert db.get_settings(7)["active_pack"] == "3"
    # переключение других настроек не должно сбрасывать текущий пак
    db.toggle_setting(7, "remove_bg")
    assert db.get_settings(7)["active_pack"] == "3"
    db.set_active_pack(7, "main")
    assert db.get_settings(7)["active_pack"] == "main"
