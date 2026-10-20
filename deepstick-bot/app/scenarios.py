"""Сценарии и стили.

`effect`    — локальная Pillow-анимация (бесплатный режим без нейросетей).
`ai_prompt` — английский промпт для image-to-video модели (Kling/Wan и т.п.),
              когда задан AI_PROVIDER. Именно так, судя по рекламе, работает
              оригинал: фото + стиль + текстовый сценарий -> i2v-генерация.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    emoji: str
    title: str
    effect: str
    ai_prompt: str


SCENARIOS: list[Scenario] = [
    Scenario("rocket", "🚀", "Лечу на ракете", "rocket",
             "the character happily rides a small cartoon rocket flying up through "
             "stars, wind in hair, excited smile, seamless loop, centred composition"),
    Scenario("laugh", "😂", "Дикий смех", "shake",
             "the character bursts out laughing, shoulders shaking, tears of joy, "
             "exaggerated funny expression, seamless loop"),
    Scenario("love", "😍", "Влюблён", "love",
             "the character falls in love, hearts floating around, dreamy smile, "
             "heart-eyes, seamless loop"),
    Scenario("wow", "😮", "Шок / вау", "zoom",
             "the character is shocked and amazed, jaw drops, camera quickly zooms "
             "in on the surprised face, seamless loop"),
    Scenario("dance", "💃", "Танцую", "dance",
             "the character dances joyfully to music, rhythmic body moves, "
             "party mood, seamless loop"),
    Scenario("fire", "🔥", "Я в огне / крут", "fire",
             "the character looks cool and confident with stylised flames around, "
             "sunglasses vibe, epic pose, seamless loop"),
    Scenario("portal", "🌀", "Открываю портал", "portal",
             "the character opens a glowing magical portal, swirling energy vortex "
             "behind, amazed look, seamless loop"),
    Scenario("hello", "👋", "Привет!", "wave",
             "the character waves hello friendly at the camera, big smile, "
             "seamless loop"),
    Scenario("yes", "✅", "Да / согласен", "nod",
             "the character nods yes approvingly, thumbs up, confident smile, "
             "seamless loop"),
    Scenario("no", "🚫", "Нет / ни за что", "no",
             "the character shakes head no decisively, arms crossed, firm "
             "expression, seamless loop"),
    Scenario("spin", "🌀", "Кружусь", "spin",
             "the character spins around joyfully full 360 degrees, playful, "
             "seamless loop"),
    Scenario("bounce", "🤪", "Прыгаю от радости", "bounce",
             "the character jumps up and down happily, pure joy, seamless loop"),
    Scenario("money", "💸", "Дождь из денег", "money",
             "money bills rain down around the happy character, rich vibes, "
             "seamless loop"),
    Scenario("sleep", "😴", "Сплю / устал", "sleep",
             "the character is sleepy, yawning, Zzz floating, cozy mood, "
             "seamless loop"),
    Scenario("angry", "😡", "Бесит!", "angry",
             "the character is furious, shaking with anger, comic rage, "
             "seamless loop"),
    Scenario("winner", "🏆", "Я победил!", "winner",
             "the character celebrates victory, golden stars, trophy energy, "
             "jumping with joy, seamless loop"),
    Scenario("cry", "😭", "Плачу", "cry",
             "the character cries dramatically with cartoon tears, sad but funny, "
             "seamless loop"),
]

SCENARIOS_BY_ID = {s.id: s for s in SCENARIOS}


@dataclass(frozen=True)
class Style:
    id: str
    emoji: str
    title: str
    ai_prompt: str


STYLES: list[Style] = [
    Style("original", "📸", "Как есть", "photorealistic, natural look"),
    Style("cartoon", "🎨", "Мультяшный", "bright cartoon style, bold colours"),
    Style("pixel", "👾", "Пиксель-арт", "retro pixel-art style"),
    Style("neon", "🌆", "Неон", "cyberpunk neon glow style"),
    Style("anime", "⛩️", "Аниме", "anime style, clean line art"),
    Style("vintage", "🎞️", "Винтаж", "vintage sepia film photo style"),
    Style("bw", "🖤", "Ч/Б", "dramatic black and white style"),
]

STYLES_BY_ID = {s.id: s for s in STYLES}

# Свободный текст пользователя -> ближайший готовый эффект (локальный режим).
# В AI-режиме текст уйдёт в модель как есть, это только fallback-подсказка.
_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("ракет", "космос", "rocket", "space", "полет", "полёт", "лети"), "rocket"),
    (("смех", "смею", "ржа", "laugh", "lol", "ору", "угар"), "laugh"),
    (("люб", "сердц", "love", "целу", "романт", "краш"), "love"),
    (("шок", "удив", "вау", "wow", "офиг", "shock"), "wow"),
    (("танц", "танцу", "dance", "диско", "вечерин", "пляш"), "dance"),
    (("огон", "горю", "горит", "fire", "крут", "эпич"), "fire"),
    (("портал", "маги", "волшеб", "portal", "magic", "холодильник"), "portal"),
    (("привет", "здравствуй", "hello", "hi", "маш"), "hello"),
    (("соглас", "одобря", "yes", "окей"), "yes"),
    (("нет", "отказ", "ни за что", " no "), "no"),
    (("круж", "крути", "spin", "верч"), "spin"),
    (("денег", "деньги", "богат", "money", "зарплат", "миллион"), "money"),
    (("сплю", "спать", "устал", "сон", "sleep", "спит"), "sleep"),
    (("бесит", "злю", "злость", "angry", "ненавиж", "раздража"), "angry"),
    (("побед", "выигра", "чемпион", "winner", "лучший"), "winner"),
    (("плач", "груст", "слёз", "слез", "cry", "печал", "обид"), "cry"),
]


def match_scenario(text: str) -> Scenario:
    low = f" {text.lower()} "
    for words, sid in _KEYWORDS:
        if any(w in low for w in words):
            return SCENARIOS_BY_ID[sid]
    return SCENARIOS_BY_ID["bounce"]
