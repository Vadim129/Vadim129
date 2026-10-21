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
            CREATE TABLE IF NOT EXISTS packs(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                name TEXT UNIQUE, title TEXT, created_at REAL);
            CREATE TABLE IF NOT EXISTS pack_refs(
                ref TEXT PRIMARY KEY, user_id INTEGER, pack_name TEXT, file_id TEXT);
            CREATE TABLE IF NOT EXISTS globals(
                key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS ai_access(
                user_id INTEGER PRIMARY KEY, created_at REAL);
            """)
            # Миграция: текущий пак, в который падают новые стикеры
            cols = [r[1] for r in c.execute("PRAGMA table_info(settings)")]
            if "active_pack" not in cols:
                c.execute("ALTER TABLE settings ADD COLUMN active_pack TEXT DEFAULT 'main'")

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

    def list_users(self) -> list[sqlite3.Row]:
        """Все известные боту пользователи, сначала недавно активные."""
        with self._db() as c:
            return list(c.execute(
                "SELECT * FROM users "
                "ORDER BY COALESCE(last_seen, created_at, 0) DESC, user_id")) 

    def find_user_by_username(self, username: str) -> sqlite3.Row | None:
        """Найти известного боту пользователя по @username (без учёта регистра)."""
        name = (username or "").strip().lstrip("@").lower()
        if not name:
            return None
        with self._db() as c:
            return c.execute(
                "SELECT * FROM users WHERE lower(username)=?", (name,)).fetchone()

    # ------------------------------------------------- индивидуальный нейродоступ
    def ai_allowed_ids(self) -> set[int]:
        with self._db() as c:
            return {int(r["user_id"]) for r in c.execute("SELECT user_id FROM ai_access")}

    def is_ai_allowed(self, user_id: int) -> bool:
        with self._db() as c:
            return c.execute("SELECT 1 FROM ai_access WHERE user_id=?",
                             (user_id,)).fetchone() is not None

    def set_ai_allowed(self, user_id: int, allowed: bool) -> bool:
        with self._db() as c:
            if allowed:
                c.execute("INSERT OR IGNORE INTO ai_access(user_id, created_at) "
                          "VALUES(?,?)", (user_id, time.time()))
            else:
                c.execute("DELETE FROM ai_access WHERE user_id=?", (user_id,))
        return allowed

    # --------------------------------------------------------------- настройки
    def get_settings(self, user_id: int) -> dict:
        with self._db() as c:
            row = c.execute("SELECT remove_bg, auto_pack, active_pack FROM settings "
                            "WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            return {"remove_bg": True, "auto_pack": True, "active_pack": "main"}
        return {"remove_bg": bool(row["remove_bg"]), "auto_pack": bool(row["auto_pack"]),
                "active_pack": row["active_pack"] or "main"}

    def set_active_pack(self, user_id: int, target: str) -> None:
        """target: 'main' или id именного пака — куда падают новые стикеры."""
        with self._db() as c:
            c.execute(
                "INSERT INTO settings(user_id, active_pack) VALUES(?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET active_pack=excluded.active_pack",
                (user_id, str(target)))

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

    # ------------------------------------------------- глобальные настройки
    def get_global(self, key: str, default: str = "") -> str:
        with self._db() as c:
            row = c.execute("SELECT value FROM globals WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_global(self, key: str, value: str) -> None:
        with self._db() as c:
            c.execute("INSERT INTO globals(key, value) VALUES(?,?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (key, value))

    def first_user_id(self) -> int | None:
        """Первый зарегистрированный пользователь = владелец бота."""
        with self._db() as c:
            row = c.execute("SELECT user_id FROM users ORDER BY created_at LIMIT 1").fetchone()
        return int(row["user_id"]) if row else None

    # ------------------------------------------------------------- стикерпаки
    def add_pack(self, user_id: int, name: str, title: str) -> int:
        with self._db() as c:
            cur = c.execute(
                "INSERT INTO packs(user_id, name, title, created_at) VALUES(?,?,?,?)",
                (user_id, name, title, time.time()))
            return int(cur.lastrowid)

    def list_packs(self, user_id: int) -> list[sqlite3.Row]:
        with self._db() as c:
            return list(c.execute(
                "SELECT * FROM packs WHERE user_id=? ORDER BY id", (user_id,)))

    def get_pack_rec(self, user_id: int, pack_id: int) -> sqlite3.Row | None:
        with self._db() as c:
            return c.execute("SELECT * FROM packs WHERE id=? AND user_id=?",
                             (pack_id, user_id)).fetchone()

    def rename_pack_rec(self, user_id: int, pack_id: int, title: str) -> None:
        with self._db() as c:
            c.execute("UPDATE packs SET title=? WHERE id=? AND user_id=?",
                      (title, pack_id, user_id))

    def delete_pack_rec(self, user_id: int, pack_id: int) -> bool:
        with self._db() as c:
            cur = c.execute("DELETE FROM packs WHERE id=? AND user_id=?",
                            (pack_id, user_id))
            return cur.rowcount > 0

    # ------------------------------------------- короткие ссылки на стикеры пака
    # file_id стикера не влезает в callback_data (<=64 байт), поэтому кнопкам
    # удаления выдаём короткий ref, а file_id храним здесь.
    def put_ref(self, user_id: int, pack_name: str, file_id: str, ref: str) -> str:
        with self._db() as c:
            c.execute(
                "INSERT INTO pack_refs(ref, user_id, pack_name, file_id) VALUES(?,?,?,?) "
                "ON CONFLICT(ref) DO UPDATE SET file_id=excluded.file_id, "
                "pack_name=excluded.pack_name",
                (ref, user_id, pack_name, file_id))
        return ref

    def get_ref(self, ref: str, user_id: int) -> sqlite3.Row | None:
        with self._db() as c:
            return c.execute("SELECT * FROM pack_refs WHERE ref=? AND user_id=?",
                             (ref, user_id)).fetchone()

    def delete_ref(self, ref: str) -> None:
        with self._db() as c:
            c.execute("DELETE FROM pack_refs WHERE ref=?", (ref,))

    # ------------------------------------------------------------------ админка
    def stats(self) -> dict:
        day = time.time() - 86400
        with self._db() as c:
            users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
            with_username = c.execute(
                "SELECT COUNT(*) n FROM users WHERE username IS NOT NULL "
                "AND trim(username)<>''").fetchone()["n"]
            packs = c.execute("SELECT COUNT(*) n FROM packs").fetchone()["n"]
            ai_allowed = c.execute("SELECT COUNT(*) n FROM ai_access").fetchone()["n"]
            gens = c.execute("SELECT COUNT(*) n FROM generations").fetchone()["n"]
            today = c.execute("SELECT COUNT(*) n FROM generations WHERE ts>?", (day,)).fetchone()["n"]
            top = c.execute(
                "SELECT scenario, COUNT(*) n FROM generations GROUP BY scenario "
                "ORDER BY n DESC LIMIT 5").fetchall()
        return {"users": users, "with_username": with_username, "packs": packs,
                "ai_allowed": ai_allowed, "generations": gens, "today": today,
                "top": [(r["scenario"], r["n"]) for r in top]}
