"""Сценарии и стили.

`effect`    — локальная Pillow-анимация из каталога app/effects.py EFFECTS
              (бесплатный режим без нейросетей, основной).
`ai_prompt` — английский промпт для image-to-video модели, когда задан
              AI_PROVIDER (нейро-режим; локально не используется).
Сценарии сгруппированы по категориям для клавиатуры бота.
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    emoji: str
    title: str
    category: str
    effect: str
    ai_prompt: str


CATEGORIES: list[tuple[str, str]] = [
    ("emotions", "😀 Эмоции"),
    ("gestures", "👋 Жесты"),
    ("moves", "🏃 Движения"),
    ("dance", "🕺 Танцы"),
    ("party", "🎉 Праздник"),
    ("nature", "🌦 Природа"),
    ("magic", "✨ Магия и космос"),
    ("action", "💪 Экшн и спорт"),
]

_P = "the character from the photo performs this with big continuous motion"

SCENARIOS: list[Scenario] = [
    # ------------------------------------------------------------- эмоции
    Scenario("laugh", "😂", "Дикий смех", "emotions", "laugh",
             "laughs uncontrollably: head throws back, shoulders shake, mouth wide open, hands slap knees"),
    Scenario("cry", "😭", "Плачу", "emotions", "cry",
             "cries hard: tears stream down, shoulders sob, hands wipe tears, head bows"),
    Scenario("love", "😍", "Влюблён", "emotions", "love_beat",
             "falls in love: hands to the chest, blows kisses, dreamy sway, hearts in eyes"),
    Scenario("wow", "😮", "Шок / вау", "emotions", "wow",
             "is shocked: eyes wide, jaw drops, hands fly to the cheeks, recoils back"),
    Scenario("mind_blown", "🤯", "Взрыв мозга", "emotions", "mind_blown",
             "mind blown: head explodes with surprise, hands grab the head, eyes pop"),
    Scenario("angry", "😡", "Бесит!", "emotions", "angry",
             "is furious: shakes fists, stomps, face turns red, silent shouting"),
    Scenario("rage", "💢", "В ярости", "emotions", "rage_red",
             "rages: trembling with anger, veins popping, fists clenched, stomping"),
    Scenario("sleep", "😴", "Сплю / устал", "emotions", "sleep",
             "is very sleepy: yawns widely, eyes close, head nods down and jerks up"),
    Scenario("dizzy", "😵", "Голова кругом", "emotions", "dizzy",
             "is dizzy: wobbles in circles, eyes spinning, barely keeps balance"),
    Scenario("scared", "😱", "Испугался", "emotions", "scared",
             "is terrified: jumps back, hands up, trembling, mouth open in a scream"),
    Scenario("shy", "😳", "Смущаюсь", "emotions", "shy",
             "is shy: blushes, looks down, fidgets, small embarrassed smile"),
    Scenario("sick", "🤢", "Плохо мне", "emotions", "sick",
             "feels sick: turns green, holds stomach, wobbles weakly"),
    Scenario("proud", "😌", "Горжусь", "emotions", "proud",
             "is proud: chest out, chin up, confident satisfied smile, slow nod"),
    Scenario("bored", "🥱", "Скучно", "emotions", "bored",
             "is bored: yawns, sighs, looks around lazily, head droops"),
    Scenario("kiss", "😘", "Воздушный поцелуй", "emotions", "kiss",
             "blows kisses to the camera with both hands, winks, loving smile"),
    Scenario("wink", "😉", "Подмигиваю", "emotions", "wink",
             "winks playfully, finger guns at the camera, cheeky grin"),
    Scenario("dead", "💀", "Отключился", "emotions", "dead_fun",
             "pretends to faint dramatically, falls over, tongue out, then pops back"),
    Scenario("drool", "🤤", "Таю от восторга", "emotions", "drool",
             "melts with delight: dreamy face, sways happily, hands to cheeks"),
    # ------------------------------------------------------------- жесты
    Scenario("hello", "👋", "Привет!", "gestures", "hello_wave",
             "waves hello enthusiastically: arm raised high, bouncing, huge smile"),
    Scenario("yes", "✅", "Да / согласен", "gestures", "nod_yes",
             "nods yes vigorously, double thumbs up, approving smile"),
    Scenario("no", "🚫", "Нет / ни за что", "gestures", "big_no",
             "shakes head no decisively, arms crossed, finger wags no-no"),
    Scenario("ok", "👌", "Всё отлично", "gestures", "ok_ring",
             "shows OK gesture, winks, satisfied nod, relaxed bounce"),
    Scenario("thanks", "🙏", "Спасибо!", "gestures", "thanks_bow",
             "bows gratefully with hands together, warm thankful smile"),
    Scenario("applause", "👏", "Аплодисменты", "gestures", "applause",
             "claps enthusiastically above the head, cheering, big smile"),
    Scenario("facepalm", "🤦", "Фейспалм", "gestures", "facepalm",
             "facepalms hard, shakes head slowly in disbelief, deep sigh"),
    Scenario("shrug", "🤷", "Не знаю", "gestures", "shrug",
             "shrugs with palms up, eyebrows raised, puzzled face"),
    Scenario("think", "🤔", "Думаю", "gestures", "think",
             "thinks hard: strokes chin, looks up, taps forehead, aha moment"),
    Scenario("salute", "🫡", "Есть!", "gestures", "salute",
             "salutes sharply, stands at attention, chest out, serious face"),
    Scenario("fist", "✊", "Так держать!", "gestures", "fist_pump",
             "pumps fist in the air triumphantly, cheers, energetic jumps"),
    Scenario("please", "🥺", "Ну пожалуйста", "gestures", "please",
             "begs cutely: puppy eyes, hands clasped together, pleading sway"),
    Scenario("stop", "✋", "Стоп!", "gestures", "stop_push",
             "raises palm: stop! steps back, firm serious expression"),
    Scenario("point", "👉", "Это ты!", "gestures", "point_cam",
             "points at the camera accusingly then laughs, finger wagging"),
    # ------------------------------------------------------------- движения
    Scenario("bounce", "🤪", "Прыгаю от радости", "moves", "bounce",
             "jumps up and down with joy, arms pump up, huge smile, hair bouncing"),
    Scenario("jump_big", "🐸", "Большой прыжок", "moves", "jump_big",
             "crouches then leaps high with arms up, lands with a bounce"),
    Scenario("hop_small", "🐇", "Попрыгунчик", "moves", "hop_small",
             "does quick small happy hops in place, giggling"),
    Scenario("run", "🏃", "Бегу на месте", "moves", "run_place",
             "runs in place fast, arms pumping, determined face, hair flying"),
    Scenario("walk", "🚶", "Шагаю", "moves", "walk_place",
             "walks confidently in place, arms swinging, cheerful stride"),
    Scenario("swim", "🏊", "Плыву", "moves", "swim",
             "swims freestyle in the air, arms rotating, splashing happily"),
    Scenario("glide", "🪽", "Планирую", "moves", "glide",
             "glides like a bird with arms spread, soaring side to side"),
    Scenario("carve", "🎿", "Виражи", "moves", "carve",
             "carves turns like skiing downhill, leaning left and right fast"),
    Scenario("surf", "🏄", "На волне", "moves", "surf",
             "surfs balancing on a wave, arms out, knees bent, splashes around"),
    Scenario("skate", "🛼", "На роликах", "moves", "skate",
             "roller-skates gliding side to side, arms swinging, big smile"),
    Scenario("zombie", "🧟", "Зомби", "moves", "zombie",
             "walks like a zombie: arms forward, lurching side to side, groaning"),
    Scenario("rope", "🪢", "Скакалка", "moves", "jump_rope",
             "jumps rope rhythmically, rope spinning around, smiling"),
    Scenario("workout", "🏋️", "Тренировка", "moves", "workout",
             "does push-ups and flexes muscles, sweating, proud grin"),
    Scenario("stretch", "🧎", "Растяжка", "moves", "stretch",
             "stretches side to side gracefully, reaches up high, relaxes"),
    Scenario("yoga", "🧘", "Медитация", "moves", "yoga",
             "meditates levitating cross-legged, calm breathing, peaceful face"),
    Scenario("levitate", "🪷", "Левитация", "moves", "levitate",
             "levitates slowly above the ground, robe fluttering, mystical pose"),
    Scenario("float", "🕊", "Парю", "moves", "float",
             "floats weightlessly, gentle bobbing, arms relaxed, dreamy"),
    Scenario("sway", "🎋", "Качаюсь", "moves", "sway",
             "sways gently side to side like dancing slowly, eyes half closed"),
    Scenario("pendulum", "🕰", "Маятник", "moves", "pendulum",
             "swings like a pendulum side to side, hypnotic rhythm"),
    Scenario("spin_slow", "🎡", "Плавное вращение", "moves", "spin_slow",
             "turns slowly and gracefully, arms slightly out, smiling"),
    Scenario("twirl", "💫", "Кружение", "moves", "spin",
             "spins around joyfully again and again, arms wide, laughing"),
    Scenario("peek", "👀", "Подглядываю", "moves", "peek",
             "peeks from side to side curiously, sneaking glances at the camera"),
    Scenario("dash", "💨", "Рывок", "moves", "dash_side",
             "dashes left and right super fast leaving motion trails"),
    # ------------------------------------------------------------- танцы
    Scenario("dance", "💃", "Танцую", "dance", "dance_groove",
             "dances energetically: arms wave, hips sway, shoulders bounce, spins"),
    Scenario("spin", "🌀", "Кружусь в танце", "dance", "dance_spin",
             "spins dancing with musical joy, skirt/hair flying around"),
    Scenario("disco", "🪩", "Диско", "dance", "disco",
             "does disco moves: point up-down, hip bumps, Saturday-night energy"),
    Scenario("breakdance", "🤸", "Брейк-данс", "dance", "breakdance",
             "breakdances: spins on the floor, freezes, acrobatic moves"),
    Scenario("moonwalk", "🌙", "Лунная походка", "dance", "moonwalk",
             "moonwalks smoothly backwards, hat tip, iconic glide"),
    Scenario("robot", "🤖", "Танец робота", "dance", "robot_dance",
             "does the robot dance: stiff mechanical arm and head moves to the beat"),
    # ------------------------------------------------------------- праздник
    Scenario("winner", "🏆", "Я победил!", "party", "winner",
             "celebrates victory: jumps with arms in a V, pumps fists, cheers"),
    Scenario("money", "💸", "Дождь из денег", "party", "money",
             "celebrates in money rain: throws banknotes up, catches bills, laughs"),
    Scenario("party", "🥳", "Вечеринка", "party", "party",
             "parties hard: jumps, throws confetti, dances with a huge grin"),
    Scenario("fireworks", "🎆", "Салют", "party", "fireworks",
             "watches fireworks in awe, points up, fireworks burst around"),
    Scenario("gift", "🎁", "Сюрприз!", "party", "gift_shake",
             "shakes a gift box curiously then it pops open with confetti"),
    Scenario("champagne", "🍾", "Шампанское", "party", "champagne",
             "pops champagne and sprays it celebrating, laughing"),
    Scenario("crown", "👑", "Я король", "party", "crown",
             "acts like royalty: crown appears, proud wave, chin up"),
    Scenario("medal", "🥇", "Чемпион", "party", "medal",
             "receives a gold medal, bites it proudly, waves to the crowd"),
    Scenario("cheers", "🥂", "Тост!", "party", "cheers",
             "raises a glass for a toast, clinks, drinks and smiles"),
    Scenario("cake", "🎂", "День рождения", "party", "cake",
             "celebrates birthday: blows candles, claps, makes a wish"),
    Scenario("balloons", "🎈", "Улетаю на шарике", "party", "balloons",
             "floats up holding a balloon, waves from above, amazed"),
    # ------------------------------------------------------------- природа
    Scenario("rain", "🌧", "Под дождём", "nature", "rain",
             "stands in the rain, looks up, catches drops, wet hair, smiling"),
    Scenario("snow", "❄️", "Снегопад", "nature", "snow",
             "catches snowflakes, spins slowly in falling snow, winter joy"),
    Scenario("sunny", "☀️", "На солнышке", "nature", "sunny",
             "basks in sunshine, stretches happily, sunglasses on, relaxed"),
    Scenario("rainbow", "🌈", "Радуга", "nature", "rainbow_arc",
             "points at a rainbow in wonder, jumps happily under it"),
    Scenario("autumn", "🍂", "Листопад", "nature", "autumn",
             "plays in falling autumn leaves, throws leaves up, laughs"),
    Scenario("spring", "🌸", "Цветение", "nature", "spring",
             "stands in falling cherry petals, spins gently, serene smile"),
    Scenario("ocean", "🌊", "Морская волна", "nature", "ocean",
             "rides a wave, splashes water, summer beach energy"),
    Scenario("wind", "🌬", "На ветру", "nature", "wind",
             "leans into strong wind, clothes and hair flutter wildly"),
    Scenario("night", "🌙", "Добрая ночь", "nature", "night",
             "waves under the moon and stars, sleepy peaceful mood"),
    Scenario("storm", "⛈", "Гроза", "nature", "storm",
             "gets caught in a thunderstorm, lightning flashes, jumps scared"),
    Scenario("campfire", "🔥", "У костра", "nature", "campfire",
             "sits by a campfire warming hands, cozy flickering light"),
    Scenario("freeze", "🥶", "Замёрз", "nature", "freeze",
             "freezes and shivers in the cold, hugs themselves, teeth chattering"),
    # ------------------------------------------------------------- магия и космос
    Scenario("portal", "🌀", "Открываю портал", "magic", "portal",
             "opens a magical portal: arms draw circles, vortex swirls, hair blows back"),
    Scenario("magic", "✨", "Волшебство", "magic", "magic",
             "casts a magic spell: waves hands, sparkles burst around, amazed"),
    Scenario("rocket", "🚀", "Лечу на ракете", "magic", "rocket",
             "rides a small rocket flying upward: waves, legs dangling, hair fluttering"),
    Scenario("ufo", "🛸", "Похищение НЛО", "magic", "ufo",
             "is beamed up by a UFO: floats upward in a light beam, surprised"),
    Scenario("comet", "☄️", "Комета", "magic", "comet",
             "flies like a comet with a sparkling tail across the sky"),
    Scenario("orbit", "🪐", "На орбите", "magic", "orbit",
             "orbits weightlessly around, planets circling, astronaut wonder"),
    Scenario("astronaut", "👨‍🚀", "Невесомость", "magic", "astronaut",
             "floats in zero gravity, slow somersault, astronaut awe"),
    Scenario("witch", "🧹", "Полёт на метле", "magic", "witch",
             "flies on a broomstick, cape fluttering, cackling happily"),
    Scenario("crystal", "🔮", "Гадание", "magic", "crystal",
             "gazes into a crystal ball, mystical glow, foretells fortune"),
    Scenario("potion", "🧪", "Волшебное зелье", "magic", "potion",
             "brews a bubbling magic potion, green glow, excited alchemist"),
    Scenario("ghost", "👻", "Я призрак", "magic", "ghost_float",
             "floats like a cute ghost, fades in and out, spooky waving"),
    Scenario("teleport", "⚡", "Телепорт", "magic", "teleport",
             "teleports in flashes of light, disappearing and reappearing"),
    Scenario("dream", "💭", "Мечтаю", "magic", "dream",
             "daydreams floating among thought bubbles, dreamy smile"),
    Scenario("timewarp", "🕰", "Машина времени", "magic", "time_warp",
             "travels through time: clock swirls, reality warps around"),
    Scenario("sparkle", "🌟", "Сияю", "magic", "sparkle_clean",
             "shines and sparkles like a star, glamorous poses, glitter around"),
    # ------------------------------------------------------------- экшн и спорт
    Scenario("fire", "🔥", "Я в огне / крут", "action", "cool",
             "acts cool and epic: sunglasses on, confident nod, points at camera"),
    Scenario("superhero", "🦸", "Супергерой", "action", "superhero",
             "flies like a superhero: fist forward, cape flapping, heroic"),
    Scenario("hero", "🛡️", "Герой", "action", "hero_pose",
             "strikes a heroic pose, chest out, wind blowing, epic stance"),
    Scenario("boxer", "🥊", "Боксёр", "action", "boxer",
             "boxes: dodges and jabs fast, footwork bouncing, fierce face"),
    Scenario("karate", "🥋", "Каратэ", "action", "karate",
             "does karate chops and kicks, sharp stances, shouts kiai"),
    Scenario("ninja", "🥷", "Ниндзя", "action", "ninja",
             "moves like a ninja: vanishes and dashes side to side stealthily"),
    Scenario("race", "🏎", "На гонке", "action", "race",
             "races at high speed, wind blasting, gripping the wheel, thrilled"),
    Scenario("power", "💪", "Силач", "action", "weightlift",
             "lifts a heavy barbell straining, muscles shaking, drops it proud"),
    Scenario("football", "⚽", "Футболист", "action", "football",
             "juggles a football with feet and knees, tricks, celebrates a goal"),
    Scenario("basketball", "🏀", "Баскетбол", "action", "basketball",
             "dribbles a basketball and shoots, jumps high, scores"),
    Scenario("sneak", "🕵️", "Крадусь", "action", "sneak",
             "sneaks tiptoeing, looks side to side, sneaky grin"),
    Scenario("fishing", "🎣", "На рыбалке", "action", "fishing",
             "fishes from a boat, rod bends, reels in a catch excitedly"),
    Scenario("idea", "💡", "Идея!", "action", "idea",
             "gets a brilliant idea: lightbulb moment, finger up, excited face"),
    Scenario("alarm", "⏰", "Будильник!", "action", "alarm",
             "panics at the alarm clock, jumps out of bed, rushes around"),
    Scenario("photo", "📸", "На фото!", "action", "photo_flash",
             "poses for photos, camera flashes, model poses changing"),
    Scenario("panic", "🫨", "Паника", "action", "heartbeat_panic",
             "panics: heart pounding, looks around frantically, hands shaking"),
]

SCENARIOS_BY_ID = {s.id: s for s in SCENARIOS}


def scenarios_in(category: str) -> list[Scenario]:
    return [s for s in SCENARIOS if s.category == category]


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
    (("портал", "маги", "волшеб", "portal", "magic"), "portal"),
    (("привет", "здравствуй", "hello", "hi", "маш"), "hello"),
    (("соглас", "одобря", "yes", "окей"), "yes"),
    (("нет", "отказ", "ни за что", " no "), "no"),
    (("круж", "крути", "spin", "верч"), "spin"),
    (("денег", "деньги", "богат", "money", "зарплат", "миллион"), "money"),
    (("сплю", "спать", "устал", "сон", "sleep", "спит"), "sleep"),
    (("бесит", "злю", "злость", "angry", "ненавиж", "раздража"), "angry"),
    (("побед", "выигра", "чемпион", "winner", "лучший"), "winner"),
    (("плач", "груст", "слёз", "слез", "cry", "печал", "обид"), "cry"),
    (("бег", "бегу", "run", "марафон"), "run"),
    (("плыв", "плав", "swim", "бассейн"), "swim"),
    (("медит", "йог", "yoga", "дзен"), "yoga"),
    (("дожд", "rain", "ливень"), "rain"),
    (("снег", "snow", "зим"), "snow"),
    (("салют", "фейерверк", "firework"), "fireworks"),
    (("корол", "царь", "king", "корона"), "crown"),
    (("бокс", "box", "ринг"), "boxer"),
    (("супергер", "superhero", "герой"), "superhero"),
    (("призра", "ghost", "привиден"), "ghost"),
    (("рыбал", "рыбу", "fishing"), "fishing"),
    (("идея", "idea", "придумал", "эврика"), "idea"),
    (("футбол", "football", "гол"), "football"),
    (("робот", "robot"), "robot"),
    (("страх", "боюсь", "испуг", "scared"), "scared"),
    (("поцелу", "kiss", "чмок"), "kiss"),
]


def match_scenario(text: str) -> Scenario:
    low = f" {text.lower()} "
    for words, sid in _KEYWORDS:
        if any(w in low for w in words):
            return SCENARIOS_BY_ID[sid]
    return SCENARIOS_BY_ID["bounce"]


# ------------------------------------------------------------- эмодзи -> движение
# Для режима оживления «по эмодзи»: движение подбирается под эмодзи каждого
# стикера; неизвестные эмодзи получают случайный сценарий.
_EMOJI_RAW: dict[str, list[str]] = {
    "rocket": ["🚀", "🛸", "✈️", "🛰️"],
    "laugh": ["😂", "🤣", "😆", "😅", "😹"],
    "love": ["😍", "❤️", "♥️", "💖", "💕", "💘", "😘", "🥰", "😻"],
    "wow": ["😮", "😱", "😳", "🤯", "😲", "🫢", "😯"],
    "dance": ["💃", "🕺", "🎉", "🥳", "🎊", "🪩"],
    "fire": ["🔥", "😎", "💪", "🤙", "👑", "🦁"],
    "portal": ["🌀", "🔮", "✨", "🌌", "🪄"],
    "hello": ["👋", "🙋", "✋", "🖐️", "🙂", "😊"],
    "yes": ["✅", "👍", "👌", "🆗", "💯", "🫡"],
    "no": ["🚫", "👎", "🙅", "🙄", "😒", "🤨"],
    "spin": ["🔄", "🎡", "🌪️", "💫", "🤸"],
    "bounce": ["🤪", "😜", "😝", "🙃", "🎈"],
    "money": ["💸", "💰", "🤑", "💵", "💎"],
    "sleep": ["😴", "💤", "🥱", "😪", "🌙"],
    "angry": ["😡", "🤬", "😠", "👿", "😤", "💢"],
    "winner": ["🏆", "🥇", "🏅", "🎖️", "👏", "🙌", "🤩"],
    "cry": ["😭", "😢", "🥺", "🥹", "💧", "😿"],
}


def _norm_emoji(emoji: str) -> str:
    return (emoji or "").replace("\uFE0F", "").strip()


EMOJI_TO_SCENARIO: dict[str, str] = {
    _norm_emoji(e): sid for sid, emojis in _EMOJI_RAW.items() for e in emojis
}


def scenario_for_emoji(emoji: str | None,
                       rng: random.Random | None = None) -> Scenario:
    """Сценарий под эмодзи стикера; неизвестный эмодзи — случайный сценарий."""
    sid = EMOJI_TO_SCENARIO.get(_norm_emoji(emoji or ""))
    if sid:
        return SCENARIOS_BY_ID[sid]
    return (rng or random).choice(SCENARIOS)
