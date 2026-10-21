"""Индивидуальный доступ к нейросети и статистика пользователей."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Database  # noqa: E402


def test_ai_access_and_users(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_user(1, "Owner", "Owner")
    db.ensure_user(2, "Ann", "Alice")
    db.ensure_user(3, "No Nick", "")

    assert {int(r["user_id"]) for r in db.list_users()} == {1, 2, 3}
    assert db.find_user_by_username("@alice")["user_id"] == 2
    assert db.find_user_by_username("ALICE")["user_id"] == 2
    assert db.find_user_by_username("@ghost") is None

    assert db.ai_allowed_ids() == set()
    assert db.is_ai_allowed(2) is False
    assert db.set_ai_allowed(2, True) is True
    db.set_ai_allowed(99, True)  # доступ можно выдать заранее, до первого /start
    assert db.ai_allowed_ids() == {2, 99}
    assert db.is_ai_allowed(99) is True
    assert db.set_ai_allowed(2, False) is False
    assert db.ai_allowed_ids() == {99}

    st = db.stats()
    assert st["users"] == 3
    assert st["with_username"] == 2
    assert st["ai_allowed"] == 1
