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


# --------------------------------------------------- промпты именно под Wan
# У Wan/FastWan прежняя схема («стиль словами + BIG CONTINUOUS movements +
# exaggerated expression») ломала главное — персонажа: модель перерисовывала
# лицо и тело под текст. Здесь наоборот: стиль уже применён к входному кадру
# локально, а модель получает ОДНО простое движение из WAN_ACTIONS и жёсткий
# запрет менять внешность. Действия специально укрощены: без взрывов головы,
# акробатики и полных разворотов — всё, что гарантированно сносит лицо.
WAN_IDENTITY_SUFFIX = (
    "Animate only the character already visible in the first frame. "
    "Preserve the exact same face, identity, facial features, hairstyle, "
    "skin tone, clothing, colours, body proportions and final art style "
    "in every frame. Do not redesign, beautify, age or replace the "
    "character, and do not invent a new body, outfit, person or face. "
    "If only the head and shoulders are visible, animate only the head, "
    "face and shoulders. Keep the character centered and fully visible, "
    "ending close to the starting pose so the clip loops seamlessly. "
    "Static locked camera: no zoom, no pan, no tilt, no camera shake, "
    "no scene change; the background stays the same except for the simple "
    "requested effect around the character. No text, no watermark, "
    "no extra people."
)

WAN_ACTIONS: dict[str, str] = {
    # эмоции
    "laugh": "gives a short joyful laugh: mouth opens in a smile, eyes squint, head tilts back slightly, shoulders shake gently",
    "cry": "looks sad and cries softly: eyebrows rise, eyes glisten, shoulders tremble slightly",
    "love": "falls in love: soft dreamy smile, eyes brighten, head tilts slightly, hands if visible move gently toward the chest",
    "wow": "reacts with surprise: eyes widen, eyebrows rise, mouth opens slightly, head pulls back a little",
    "mind_blown": "reacts amazed: eyes widen, eyebrows rise, hands if visible touch the sides of the head",
    "angry": "looks annoyed: brows lower, lips press together, head shakes a tiny bit side to side",
    "rage": "shows controlled anger: shoulders tense, fists clench if visible, one short sharp head shake",
    "sleep": "looks sleepy: eyelids droop, one slow blink, head nods down slightly and lifts again",
    "dizzy": "looks dizzy: eyes glance in a small circle, head sways gently side to side",
    "scared": "reacts startled: eyes widen, mouth opens slightly, shoulders jump once",
    "shy": "looks shy: small smile, eyes glance down, head tilts slightly",
    "sick": "looks unwell: weak expression, head sways slowly, shoulders slump a little",
    "proud": "looks proud: chin lifts slightly, calm confident smile, one slow nod",
    "bored": "looks bored: eyelids lower, a small sigh, head tilts lazily to one side",
    "kiss": "blows one gentle kiss toward the camera: lips purse briefly, then a warm smile",
    "wink": "winks once playfully and gives a small cheeky smile",
    "dead": "play-acts fainting: eyes close, head tilts to the side, then returns to the starting pose",
    "drool": "looks delighted: dreamy smile, head tilts slightly, happy relaxed sway",
    # жесты
    "hello": "waves hello with one hand if hands are visible; otherwise nods warmly with a big friendly smile",
    "yes": "nods yes twice with an approving smile",
    "no": "shakes the head no slowly twice with a firm expression",
    "ok": "gives a satisfied nod and, if a hand is visible, shows a brief OK gesture",
    "thanks": "bows the head slightly in thanks, hands together if visible, warm smile",
    "applause": "claps briefly if hands are visible; otherwise bounces happily with a cheering smile",
    "facepalm": "does a brief facepalm if a hand is visible; otherwise closes the eyes and shakes the head slowly",
    "shrug": "shrugs gently: shoulders rise, eyebrows lift, palms turn up if visible",
    "think": "thinks: eyes glance upward, head tilts, then eyebrows rise as if an idea arrived",
    "salute": "gives a crisp small salute if a hand is visible, standing tall with a serious smile",
    "fist": "pumps one fist once if visible; otherwise gives an energetic triumphant nod",
    "please": "makes a pleading cute expression: eyebrows rise, hands clasp if visible, gentle sway",
    "stop": "raises one palm in a stop gesture if visible; otherwise leans back slightly with a firm look",
    "point": "points toward the camera if a hand is visible, then smiles; otherwise leans forward slightly and winks",
    # движения
    "bounce": "bounces happily in place twice with a joyful smile",
    "jump_big": "does one small crouch and one happy hop in place, staying centered",
    "hop_small": "does three quick tiny hops in place with a giggling expression",
    "run": "mimes running in place at a moderate pace, arms swinging only if visible",
    "walk": "mimes a confident walk in place with a gentle arm swing if visible",
    "swim": "mimes slow swimming strokes in place if arms are visible; otherwise bobs gently",
    "glide": "leans gently left and right as if gliding, arms slightly out if visible",
    "carve": "leans smoothly left then right as if carving turns, staying centered",
    "surf": "balances as if on a surfboard: knees bend slightly if visible, arms out gently",
    "skate": "glides side to side in place as if roller-skating, small controlled steps if feet are visible",
    "zombie": "does a playful zombie sway: arms forward if visible, slow side-to-side lean",
    "rope": "does small rhythmic hops as if jumping rope, staying in place",
    "workout": "does two controlled exercise reps in place: a small squat or an arm flex if visible",
    "stretch": "stretches gently: reaches upward if arms are visible, then relaxes",
    "yoga": "holds a calm meditative pose, breathing slowly with a peaceful expression",
    "levitate": "rises slightly and floats in place with a gentle bob and a calm expression",
    "float": "floats weightlessly in place with a slow gentle bob",
    "sway": "sways gently side to side in a smooth rhythm",
    "pendulum": "swings slowly side to side like a pendulum, staying centered",
    "spin_slow": "rotates slowly only a quarter turn and returns to face the camera",
    "twirl": "does one joyful slow twirl and returns to face the camera",
    "peek": "peeks left then right curiously and returns to center",
    "dash": "leans quickly left then right in place with playful energy, never leaving the frame",
    # танцы
    "dance": "dances gently in place: shoulders bounce, head bobs, arms move rhythmically if visible",
    "spin": "does one slow dance turn and returns to face the camera",
    "disco": "does simple disco moves in place: one arm points up then down if visible, hips sway gently",
    "breakdance": "does a playful low dance bounce in place, with no floor spin and no acrobatics",
    "moonwalk": "glides the feet in a moonwalk motion while staying centered, then returns",
    "robot": "does stiff robot-dance moves: small stepped head and arm movements if visible",
    # праздник
    "winner": "celebrates victory: arms rise if visible, one happy bounce, cheering smile",
    "money": "celebrates as a few banknotes fall around the character, reaching happily toward them if hands are visible",
    "party": "parties in place: happy bounce, arms wave if visible, confetti falls around",
    "fireworks": "looks up in awe and points upward if a hand is visible, fireworks sparkle in the background",
    "gift": "reacts with excited surprise as confetti pops around, reaching forward if hands are visible",
    "champagne": "makes a cheerful toast gesture if a hand is visible, joyful bounce and smile",
    "crown": "acts proudly like royalty: chin up, a royal wave if a hand is visible",
    "medal": "celebrates proudly with one happy bounce and a champion smile",
    "cheers": "raises a toast gesture if a hand is visible, then smiles warmly",
    "cake": "celebrates a birthday: claps if hands are visible, leans forward slightly as if blowing out candles, then smiles",
    "balloons": "floats upward slightly as if lifted by balloons, waving gently if a hand is visible",
    # природа
    "rain": "stands in gentle rain: looks up, smiles, raindrops fall around the character",
    "snow": "turns slightly in falling snow, catching a snowflake if a hand is visible, winter smile",
    "sunny": "basks in sunshine: stretches happily if arms are visible, relaxed smile",
    "rainbow": "points in wonder toward a rainbow in the background if a hand is visible, happy smile",
    "autumn": "smiles as autumn leaves drift and fall around the character, gentle sway",
    "spring": "stands among falling cherry petals with a gentle sway and a serene smile",
    "ocean": "rocks gently as if riding a small wave, water splashes around the lower frame",
    "wind": "leans into a breeze: hair and clothes flutter naturally while the character stays in place",
    "night": "waves gently under moonlight with a peaceful sleepy smile, stars twinkle in the background",
    "storm": "reacts to a brief lightning flash with a startled jump as rain falls around",
    "campfire": "warms hands by a campfire if hands are visible, cozy gentle sway",
    "freeze": "shivers in the cold: shoulders shake in small fast movements, arms hug inward if visible",
    # магия и космос
    "portal": "gestures as if opening a small magical portal beside the character, sparkles swirling nearby",
    "magic": "waves hands gently if visible as sparkles burst around, amazed smile",
    "rocket": "rises slightly as if riding a small rocket below the frame, waving happily if a hand is visible",
    "ufo": "floats upward slightly in a soft beam of light from above, surprised expression",
    "comet": "glides in a small gentle arc with a sparkling trail behind, staying in frame",
    "orbit": "floats weightlessly in a slow small circle and returns to center",
    "astronaut": "floats in zero gravity with a slow quarter-turn and returns upright",
    "witch": "glides side to side as if flying on a broom below the frame, clothes fluttering",
    "crystal": "makes mystical hand gestures if hands are visible, gazing forward with a focused look",
    "potion": "mimes stirring a bubbling potion if hands are visible, excited alchemist expression, green sparkles around",
    "ghost": "floats like a cute ghost: gentle bob, slight fade, friendly wave if a hand is visible",
    "teleport": "flickers in place with brief magical flashes, never leaving the frame",
    "dream": "daydreams with a dreamy smile, floating gently as soft bubbles rise around",
    "timewarp": "looks around in wonder as glowing rings swirl slowly in the background",
    "sparkle": "poses and shines like a star: small glamorous turns of the head, glitter sparkles around",
    # экшн и спорт
    "fire": "acts cool and epic: confident nod, then points at the camera if a hand is visible",
    "superhero": "flies in place like a superhero: one fist forward if visible, clothes flutter, heroic smile",
    "hero": "strikes a heroic pose: chest out if visible, chin up, confident stance",
    "boxer": "does light boxing in place: two small jabs if arms are visible, bouncy footwork",
    "karate": "does one controlled karate chop and stance if the body is visible, focused expression",
    "ninja": "moves stealthily side to side in small quick steps with a sneaky expression",
    "race": "leans as if racing at speed, hair blown by wind, thrilled expression",
    "power": "flexes or lifts with effort if arms are visible, proud strained grin",
    "football": "celebrates a goal with a happy bounce; if feet are visible, juggles an imaginary ball briefly",
    "basketball": "mimes dribbling and one shot if arms are visible, then a happy jump",
    "sneak": "sneaks in place: tiptoe steps if feet are visible, looking left and right",
    "fishing": "mimes holding a fishing rod and reeling in a catch if hands are visible, excited smile",
    "idea": "gets an idea: eyes widen, one finger rises if visible, excited smile",
    "alarm": "reacts to an alarm: startled jump, quick look around, hurried playful panic",
    "photo": "poses for photos: two small pose changes and a confident smile, brief camera flashes",
    "panic": "panics playfully: looks left and right quickly, shoulders shake, hands flutter if visible",
}


def build_prompt_wan(style: Style, scenario: Scenario,
                     custom_text: str | None) -> str:
    """Промпт для Wan/FastWan: стиль уже в сгенерированном стартовом кадре,
    одно простое движение, жёсткое сохранение персонажа. Отдельно от
    build_prompt: HF/LTX-моделям по-прежнему нужен сильный MOTION_SUFFIX,
    а Wan он вредит."""
    style_note = style.wan_prompt or style.ai_prompt
    if custom_text:
        action = ("performs the user's requested action, interpreted as one "
                  f"simple visible movement: {custom_text}")
    else:
        action = WAN_ACTIONS.get(scenario.id) or scenario.ai_prompt
    return (f"The input frame already shows the final character in the final "
            f"style ({style_note}); do not restyle or redraw it. "
            f"The character {action}. {WAN_IDENTITY_SUFFIX}")


def build_image_prompt(style: Style) -> str:
    """Промпт первой стадии (FLUX Kontext): фото -> стартовый кадр стикера.

    Пользовательское фото обычно не готово для видео: крупный план, обрезанная
    голова, пёстрый фон. Поэтому сначала генерируем чистый кадр: тот же
    человек, узнаваемое лицо, вся голова в кадре с запасом, ровный однотонный
    фон (его потом вырежет маттинг), стиль применён уже здесь. Сценарий сюда
    не подмешиваем: поза нейтральная, действие добавит видеомодель.
    """
    style_note = style.image_prompt or style.ai_prompt
    return (
        "Transform the reference photo into a clean sticker-ready character "
        f"portrait: {style_note}. Keep the exact same person: preserve facial "
        "identity, face shape, eyes, nose, mouth, hairstyle, hair colour, "
        "skin tone, apparent age and distinctive features; keep the clothing "
        "recognizable from the photo. Use the same visible framing as the "
        "reference, but center the character, keep the whole head fully "
        "inside the frame with clear margin around it, and do not crop the "
        "top of the head or the chin. If only the head and shoulders are "
        "visible, keep it a head-and-shoulders portrait and do not invent "
        "legs or a full body. Replace the background with one clean plain "
        "solid light-grey background with no objects and no scenery. "
        "Front-facing or slight three-quarter view, looking toward the "
        "camera, relaxed natural expression and neutral pose. Do not add "
        "new people, props, accessories, text or watermark, and do not "
        "change the outfit. Sharp detailed face, clean silhouette edges, "
        "square 1:1 composition."
    )


@dataclass(frozen=True)
class Style:
    id: str
    emoji: str
    title: str
    ai_prompt: str
    # Как стиль описан для Wan: стиль уже применён к стартовому кадру на
    # первой стадии, видеомодели запрещаем перерисовывать персонажа.
    wan_prompt: str = ""
    # Как стиль задан модели генерации стартового кадра (FLUX Kontext).
    image_prompt: str = ""


STYLES: list[Style] = [
    Style("original", "📸", "Как есть", "photorealistic, natural look",
          "photorealistic appearance identical to the input frame",
          "clean photorealistic portrait, natural colours and realistic skin texture"),
    Style("cartoon", "🎨", "Мультяшный", "bright cartoon style, bold colours",
          "bright flat cartoon look already applied to the input frame",
          "bright flat 2D cartoon character, bold clean outlines, simple cel shading, vivid colours"),
    Style("pixel", "👾", "Пиксель-арт", "retro pixel-art style",
          "retro pixel-art look already applied to the input frame",
          "retro pixel-art character portrait, chunky visible pixels, limited colour palette"),
    Style("neon", "🌆", "Неон", "cyberpunk neon glow style",
          "neon-lit look already applied to the input frame",
          "cyberpunk neon-lit character portrait, magenta and cyan rim light, dark-friendly colours"),
    Style("anime", "⛩️", "Аниме", "anime style, clean line art",
          "clean anime look already applied to the input frame",
          "clean anime character portrait, crisp line art, cel shading, expressive eyes"),
    Style("vintage", "🎞️", "Винтаж", "vintage sepia film photo style",
          "vintage sepia film look already applied to the input frame",
          "vintage sepia film portrait, warm faded tones, gentle film grain"),
    Style("bw", "🖤", "Ч/Б", "dramatic black and white style",
          "black-and-white look already applied to the input frame",
          "dramatic black-and-white portrait, strong contrast, monochrome only"),
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
