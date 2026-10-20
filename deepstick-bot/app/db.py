"""SQLite-хранилище: пользователи, настройки, история генераций, последний сценарий.

Файл БД лежит в DATA_DIR (в Docker — volume ./data), переживает перезапуски.
Никакой оплаты/лимитов здесь нет и не планируется — только история и настройки.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self._db() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT,
                created_at REAL, last_seen REAL);
            CREATE TABLE IF NOT EXISTS settings(
                user_id INTEGER PRIMARY KEY,
                remove_bg INTEGER NOT NULL DEFAULT 1,
                auto_pack INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS generations(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, ts REAL,
                kind TEXT, scenario TEXT, style TEXT, emoji TEXT, file_id TEXT);
            CREATE TABLE IF NOT EXISTS last_job(
                user_id INTEGER PRIMARY KEY, photo TEXT, style TEXT,
                scenario_id TEXT, custom_text TEXT, emoji TEXT);
            """)

    def _db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------- пользователи
    def ensure_user(self, user_id: int, first_name: str = "", username: str = "") -> None:
        now = time.time()
        with self._db() as c:
            c.execute(
                "INSERT INTO users(user_id, first_name, username, created_at, last_seen) "
                "VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET "
                "first_name=excluded.first_name, username=excluded.username, last_seen=excluded.last_seen",
                (user_id, first_name, username, now, now))

    # --------------------------------------------------------------- настройки
    def get_settings(self, user_id: int) -> dict:
        with self._db() as c:
            row = c.execute("SELECT remove_bg, auto_pack FROM settings WHERE user_id=?",
                            (user_id,)).fetchone()
        if row is None:
            return {"remove_bg": True, "auto_pack": True}
        return {"remove_bg": bool(row["remove_bg"]), "auto_pack": bool(row["auto_pack"])}

    def toggle_setting(self, user_id: int, key: str) -> bool:
        if key not in ("remove_bg", "auto_pack"):
            raise ValueError(key)
        cur = self.get_settings(user_id)
        new = not cur[key]
        with self._db() as c:
            c.execute(
                f"INSERT INTO settings(user_id, {key}) VALUES(?,?) "
                f"ON CONFLICT(user_id) DO UPDATE SET {key}=excluded.{key}",
                (user_id, int(new)))
        return new

    # --------------------------------------------------------------- генерации
    def log_generation(self, user_id: int, kind: str, scenario: str, style: str,
                       emoji: str, file_id: str | None) -> int:
        with self._db() as c:
            cur = c.execute(
                "INSERT INTO generations(user_id, ts, kind, scenario, style, emoji, file_id) "
                "VALUES(?,?,?,?,?,?,?)",
                (user_id, time.time(), kind, scenario, style, emoji, file_id))
            return int(cur.lastrowid)

    def history(self, user_id: int, limit: int = 10) -> list[sqlite3.Row]:
        with self._db() as c:
            return list(c.execute(
                "SELECT * FROM generations WHERE user_id=? AND file_id IS NOT NULL "
                "ORDER BY id DESC LIMIT ?", (user_id, limit)))

    def get_generation(self, gen_id: int, user_id: int) -> sqlite3.Row | None:
        with self._db() as c:
            return c.execute("SELECT * FROM generations WHERE id=? AND user_id=?",
                             (gen_id, user_id)).fetchone()

    # ------------------------------------------------------------- последний job
    def set_last_job(self, user_id: int, photo: str, style: str,
                     scenario_id: str | None, custom_text: str | None, emoji: str) -> None:
        with self._db() as c:
            c.execute(
                "INSERT INTO last_job(user_id, photo, style, scenario_id, custom_text, emoji) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET photo=excluded.photo, "
                "style=excluded.style, scenario_id=excluded.scenario_id, "
                "custom_text=excluded.custom_text, emoji=excluded.emoji",
                (user_id, photo, style, scenario_id, custom_text, emoji))

    def get_last_job(self, user_id: int) -> dict | None:
        with self._db() as c:
            row = c.execute("SELECT * FROM last_job WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------ админка
    def stats(self) -> dict:
        day = time.time() - 86400
        with self._db() as c:
            users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
            gens = c.execute("SELECT COUNT(*) n FROM generations").fetchone()["n"]
            today = c.execute("SELECT COUNT(*) n FROM generations WHERE ts>?", (day,)).fetchone()["n"]
            top = c.execute(
                "SELECT scenario, COUNT(*) n FROM generations GROUP BY scenario "
                "ORDER BY n DESC LIMIT 5").fetchall()
        return {"users": users, "generations": gens, "today": today,
                "top": [(r["scenario"], r["n"]) for r in top]}
