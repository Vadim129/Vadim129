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
             "rides a small rocket flying upward: body bounces from acceleration, one arm waves, other holds on tight, legs dangling and kicking, hair and clothes flutter in the wind, mouth open in an excited cheer, continuous strong full-body motion"),
    Scenario("laugh", "😂", "Дикий смех", "shake",
             "laughs uncontrollably: head throws back and shakes, shoulders shake hard, mouth wide open laughing, eyes squeezed shut, hands slap knees, belly shaking, continuous strong motion"),
    Scenario("love", "😍", "Влюблён", "love",
             "falls in love: hands press to the chest then blow kisses to the camera, head tilts dreamily side to side, eyes turn to hearts, wide happy smile, swaying body, continuous expressive motion"),
    Scenario("wow", "😮", "Шок / вау", "zoom",
             "is shocked: eyes go wide, eyebrows jump up, jaw drops open, both hands fly to the cheeks, body recoils back then leans in again, exaggerated surprise, continuous strong facial and body motion"),
    Scenario("dance", "💃", "Танцую", "dance",
             "dances energetically: arms wave above the head and swing side to side, hips sway, shoulders bounce to the rhythm, spins half-way and back, big smile, continuous strong full-body dancing"),
    Scenario("fire", "🔥", "Я в огне / крут", "fire",
             "acts cool and epic: puts on sunglasses with one hand, nods confidently, crosses arms, then points at the camera, smirk, flames-like energy around, rhythmic confident movements"),
    Scenario("portal", "🌀", "Открываю портал", "portal",
             "opens a magical portal: both arms draw big circles in the air, palms push forward opening a swirling vortex, hair blows back, amazed expression, continuous strong arm and body motion"),
    Scenario("hello", "👋", "Привет!", "wave",
             "waves hello enthusiastically: one arm raised high waving left-right, other hand beckons, head nods, huge friendly smile, bouncing in place, continuous strong motion"),
    Scenario("yes", "✅", "Да / согласен", "nod",
             "nods yes vigorously: head nods up-down repeatedly, thumbs up with both hands, approving smile, shoulders bounce happily, continuous clear motion"),
    Scenario("no", "🚫", "Нет / ни за что", "no",
             "shakes head no decisively: head shakes left-right repeatedly, arms crossed then one finger wags no-no, firm frown, body turns side to side, continuous clear motion"),
    Scenario("spin", "🌀", "Кружусь", "spin",
             "spins around joyfully: full body turns 360 degrees again and again, arms spread wide, laughing, hair and clothes flying, continuous spinning motion"),
    Scenario("bounce", "🤪", "Прыгаю от радости", "bounce",
             "jumps up and down with joy: knees bend and whole body leaps high repeatedly, arms pump up at every jump, huge smile, hair bouncing, continuous strong jumping"),
    Scenario("money", "💸", "Дождь из денег", "money",
             "celebrates in money rain: throws banknotes up with both hands, catches falling bills, laughs, dances in place, head thrown back happily, continuous strong motion"),
    Scenario("sleep", "😴", "Сплю / устал", "sleep",
             "is very sleepy: yawns widely covering mouth with a hand, eyes slowly close and open, head nods down and jerks up, body sways, rubbing eyes, continuous slow motion"),
    Scenario("angry", "😡", "Бесит!", "angry",
             "is furious: face turns red, eyebrows frown hard, shakes fists, stomps, head shakes in rage, mouth shouts silently, body trembling with anger, continuous strong motion"),
    Scenario("winner", "🏆", "Я победил!", "winner",
             "celebrates victory: jumps with both arms raised in a V, pumps fists, cheers with mouth wide open, chest out proudly, bouncing triumphantly, continuous strong motion"),
    Scenario("cry", "😭", "Плачу", "cry",
             "cries hard: tears stream down both cheeks, shoulders sob up and down, hands wipe tears and cover the face then drop, mouth trembles open in sobs, head bows and shakes, continuous strong motion"),
]

SCENARIOS_BY_ID = {s.id: s for s in SCENARIOS}

# Обязательный хвост любого промпта в image-to-video. Без него бесплатные
# модели любят возвращать почти статичную картинку с одним морганием.
MOTION_SUFFIX = (
    " The person performs this action with BIG, CLEAR, CONTINUOUS movements of "
    "the head, face, arms and whole body during the entire video. "
    "It must be a real moving video, NOT a still photo, NOT only blinking, "
    "NOT only a camera zoom or shake. Exaggerated facial expression matching "
    "the action. Keep the exact face, hairstyle and identity of the person "
    "from the photo. The character stays centered and fully visible. "
    "Seamless loop, no text, no watermark, no other people."
)


def build_prompt(style: Style, scenario: Scenario, custom_text: str | None) -> str:
    """Финальный промпт нейросети: стиль + действие + (текст юзера) + движения."""
    parts = [f"{style.ai_prompt}. The main character from the photo {scenario.ai_prompt}."]
    if custom_text:
        parts.append(f"User's own scenario (may be in Russian, follow its meaning): {custom_text}.")
    parts.append(MOTION_SUFFIX)
    return " ".join(parts)


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
