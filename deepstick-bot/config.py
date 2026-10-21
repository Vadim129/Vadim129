"""Конфигурация из .env / окружения."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    token: str
    remove_bg: bool          # мастер-переключатель вырезания фона
    admin_ids: set[int] = field(default_factory=set)
    data_dir: Path = Path("data")
    sticker_fps: int = 30
    sticker_duration: float = 2.8
    kaggle_username: str = ""  # опциональный Kaggle-ComfyUI бэкенд
    kaggle_key: str = ""

    @classmethod
    def load(cls) -> "Config":
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise SystemExit("Нет BOT_TOKEN. Скопируй .env.example в .env и впиши токен от @BotFather.")
        admins = set()
        for part in os.getenv("ADMIN_IDS", "").replace(";", ",").split(","):
            part = part.strip()
            if part.lstrip("-").isdigit():
                admins.add(int(part))
        return cls(
            token=token,
            remove_bg=os.getenv("REMOVE_BG", "auto").lower() in ("auto", "on", "1", "true"),
            admin_ids=admins,
            data_dir=Path(os.getenv("DATA_DIR", "data")),
            sticker_fps=int(os.getenv("STICKER_FPS", "30")),
            sticker_duration=float(os.getenv("STICKER_DURATION", "2.8")),
            kaggle_username=os.getenv("KAGGLE_USERNAME", "").strip(),
            kaggle_key=os.getenv("KAGGLE_KEY", "").strip(),
        )
