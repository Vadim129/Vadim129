"""Конфигурация из .env / окружения."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Config:
    token: str
    remove_bg: bool          # вырезать фон (нужен rembg, иначе игнор)
    sticker_fps: int = 30
    sticker_duration: float = 2.8

    @classmethod
    def load(cls) -> "Config":
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise SystemExit("Нет BOT_TOKEN. Скопируй .env.example в .env и впиши токен от @BotFather.")
        return cls(
            token=token,
            remove_bg=os.getenv("REMOVE_BG", "auto").lower() in ("auto", "on", "1", "true"),
            sticker_fps=int(os.getenv("STICKER_FPS", "30")),
            sticker_duration=float(os.getenv("STICKER_DURATION", "2.8")),
        )
