"""Бегущая строка «заяц на коне гонится за мужчиной» + эквалайзер под бит.

Рисуется «дешёвым маркером»: дрожащие линии, кривая перспектива, кривые пропорции.
Полоса (720x190) клеится в низ кадра 720x1280.
"""
import math, random
from PIL import Image, ImageDraw, ImageFont

W, H = 720, 190
SCENE_H = 132                 # полоса погони
BARS_H = H - SCENE_H          # полоса эквалайзера
GROUND = 122                  # линия земли внутри полосы
INK = (26, 22, 20, 255)
WHITE = (255, 255, 255, 255)

HORSE = (196, 138, 74, 255)
HORSE_D = (146, 96, 46, 255)
MAN_SHIRT = (78, 132, 196, 255)
MAN_PANTS = (52, 60, 82, 255)
SKIN = (238, 198, 164, 255)
RABBIT = (250, 250, 248, 255)
PINK = (240, 150, 170, 255)
RED = (206, 62, 58, 255)
GREEN = (84, 152, 94, 255)
YELLOW = (240, 198, 76, 255)
GREY = (150, 150, 150, 255)
BLUE = (74, 110, 190, 255)


def _canvas(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


try:
    FONT_BIG = ImageFont.load_default(size=21)
except Exception:                                    # старый Pillow
    FONT_BIG = ImageFont.load_default()


class Pen:
    """Маркер: линии дрожат, толщина гуляет, углы не сходятся."""

    def __init__(self, draw, rng):
        self.d = draw
        self.rng = rng

    def jitter(self, p, amount):
        return (p[0] + self.rng.uniform(-amount, amount),
                p[1] + self.rng.uniform(-amount, amount))

    def line(self, a, b, color=INK, width=3, wobble=1.1, segs=5, taper=True):
        pts = []
        for i in range(segs + 1):
            f = i / segs
            p = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            if 0 < i < segs:
                p = self.jitter(p, wobble)
            pts.append(p)
        for i in range(len(pts) - 1):
            w = width
            if taper and i in (0, len(pts) - 2):
                w = max(1, width - 1)
            self.d.line([pts[i], pts[i + 1]], fill=color, width=w, joint="curve")

    def poly(self, pts, fill=None, outline=INK, width=3, wobble=1.0, close=True, shrink=0.985,
             origin=(360, 66)):
        pts = [self.jitter(p, wobble) for p in pts]
        if fill:
            inner = [(p[0] * shrink + origin[0] * (1 - shrink),
                      p[1] * shrink + origin[1] * (1 - shrink)) for p in pts]
            self.d.polygon(inner, fill=fill)
        if outline:
            seq = pts + [pts[0]] if close else pts
            for i in range(len(seq) - 1):
                self.line(seq[i], seq[i + 1], outline, width, wobble * 0.8, segs=3, taper=False)

    def ellipse(self, box, fill=None, outline=INK, width=3, wobble=0.9, flat=0.0, n=14):
        x0, y0, x1, y1 = box
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
        pts = []
        for i in range(n):
            a = 2 * math.pi * i / n
            r = 1.0 + self.rng.uniform(-0.05, 0.05) + flat * math.cos(a * 2)
            pts.append((cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r))
        self.poly(pts, fill=fill, outline=outline, width=width, wobble=wobble, origin=(cx, cy))

    def scribble(self, box, color, n=8, width=2):
        x0, y0, x1, y1 = box
        for _ in range(n):
            a = (self.rng.uniform(x0, x1), self.rng.uniform(y0, y1))
            b = (a[0] + self.rng.uniform(-8, 8), a[1] + self.rng.uniform(2, 6))
            self.line(a, b, color, width, 0.7, segs=2, taper=False)


# ----------------------------------------------------------------- конь с зайцем
def horse_ride(phase):
    """phase 0..1 — фаза галопа. Холст 160x126, копыта на y=126."""
    im = _canvas(160, 126)
    d = ImageDraw.Draw(im)
    p = Pen(d, random.Random(1000 + int(round(phase * 8))))
    bob = math.sin(phase * 2 * math.pi) * 2.5

    # ноги (две передние, две задние), копыта на земле
    for i, (x, flip) in enumerate([(90, 1), (82, 1), (44, -1), (36, -1)]):
        ang = math.sin(phase * 2 * math.pi + i * math.pi / 2) * 0.85
        hip = (x, 96 + bob * 0.4)
        knee = (hip[0] + math.sin(ang) * 10 * flip, 113)
        hoof = (knee[0] + math.sin(ang * 1.5) * 12, 126)
        p.line(hip, knee, INK, 4)
        p.line(knee, hoof, INK, 3)
        p.line((hoof[0] - 4, hoof[1] - 1), (hoof[0] + 5, hoof[1]), INK, 3, 0.5)

    # корпус
    p.ellipse((14, 62 + bob, 104, 104 + bob), fill=HORSE, outline=INK, width=4, flat=0.03)
    p.scribble((26, 74 + bob, 92, 96 + bob), HORSE_D, n=9)
    # шея
    p.poly([(94, 86 + bob), (104, 44 + bob), (120, 36 + bob), (130, 62 + bob)], fill=HORSE, width=4)
    # голова + морда
    p.ellipse((108, 30 + bob, 142, 62 + bob), fill=HORSE, outline=INK, width=4, flat=0.05)
    p.poly([(136, 40 + bob), (156, 44 + bob), (154, 58 + bob), (132, 56 + bob)], fill=HORSE_D, width=3)
    # уши
    p.poly([(110, 32 + bob), (112, 14 + bob), (120, 30 + bob)], fill=HORSE, width=3)
    p.poly([(124, 30 + bob), (130, 14 + bob), (134, 30 + bob)], fill=HORSE, width=3)
    # глаз, ноздря
    d.ellipse((117, 42 + bob, 123, 48 + bob), fill=INK)
    d.ellipse((146, 46 + bob, 151, 51 + bob), fill=INK)
    # грива
    for i in range(5):
        p.line((104 + i * 2, 40 + bob + i * 8), (96 + i * 2, 30 + bob + i * 8), INK, 3, 1.0)
    # хвост
    for i in range(4):
        p.line((16, 70 + bob + i * 3), (4 - i * 2, 62 + bob + i * 10), INK, 3, 1.2)
    # седло
    p.poly([(40, 62 + bob), (74, 58 + bob), (78, 70 + bob), (42, 74 + bob)], fill=RED, width=3)

    # ---- заяц: сидит в седле, уши торчком, лапы с поводьями ----
    y = bob * 1.3
    p.ellipse((44, 30 + y, 84, 66 + y), fill=RABBIT, outline=INK, width=3, flat=0.04)     # туловище
    p.ellipse((64, 4 + y, 98, 38 + y), fill=RABBIT, outline=INK, width=3, flat=0.04)      # голова
    # уши (мотаются назад от скорости)
    ear = math.sin(phase * 2 * math.pi) * 4
    p.ellipse((66 - ear, -16 + y + 8, 76 - ear, 12 + y), fill=RABBIT, outline=INK, width=3)
    p.ellipse((80 - ear, -14 + y + 8, 89 - ear, 12 + y), fill=RABBIT, outline=INK, width=3)
    p.ellipse((68 - ear, -6 + y + 8, 74 - ear, 8 + y), fill=PINK, outline=None)
    p.ellipse((82 - ear, -5 + y + 8, 87 - ear, 8 + y), fill=PINK, outline=None)
    # злая морда
    d.ellipse((82, 16 + y, 88, 22 + y), fill=INK)
    d.ellipse((92, 22 + y, 97, 27 + y), fill=PINK)
    p.line((78, 10 + y), (86, 13 + y), INK, 2, 0.4)          # бровь
    p.line((84, 30 + y), (95, 28 + y), INK, 2, 0.5)          # ухмылка
    # передние лапы с поводьями
    p.line((80, 38 + y), (108, 52 + y), RABBIT, 6, 0.5)
    p.line((90, 40 + y), (114, 58 + y), RABBIT, 5, 0.5)
    p.line((108, 50 + y), (126, 60 + bob), RED, 2, 0.5)
    p.line((112, 56 + y), (128, 62 + bob), RED, 2, 0.5)
    # задняя лапа в стремя
    p.line((54, 62 + y), (48, 76 + y), RABBIT, 6, 0.5)
    return im


# ----------------------------------------------------------------- мужчина
def man(pose, phase=0.0):
    """Холст 120x124, ступни на y≈118. Бежит вправо и вечно спотыкается."""
    im = _canvas(120, 124)
    d = ImageDraw.Draw(im)
    p = Pen(d, random.Random(2000 + int(round(phase * 8)) * 7 + (abs(hash(pose)) % 89)))
    if pose == "run":
        sw = math.sin(phase * 2 * math.pi)
        hip = (54, 82)
        p.line((56, 58), hip, MAN_SHIRT, 16, 0.4)
        p.ellipse((46, 34, 78, 66), fill=MAN_SHIRT, outline=INK, width=3)
        p.ellipse((52, 8, 78, 36), fill=SKIN, outline=INK, width=3)          # голова
        p.ellipse((50, 4, 62, 12), fill=(60, 48, 40, 255), outline=INK, width=2)  # волосы
        d.ellipse((64, 16, 71, 23), fill=WHITE)
        d.ellipse((66, 18, 70, 22), fill=INK)
        d.ellipse((66, 26, 73, 33), fill=INK)                                # орущий рот
        p.line((54, 44), (36 - 10 * sw, 44 + 16 * sw), SKIN, 5)              # руки
        p.line((70, 44), (84 + 10 * sw, 36 - 12 * sw), SKIN, 5)
        for sgn, ph in ((1, 0.0), (-1, 0.5)):
            a = math.sin((phase + ph) * 2 * math.pi)
            knee = (hip[0] + 14 * a, hip[1] + 16)
            foot = (knee[0] + 12 * a, 118)
            p.line(hip, knee, MAN_PANTS, 9, 0.4)
            p.line(knee, foot, MAN_PANTS, 8, 0.4)
            p.line((foot[0] - 10, foot[1]), (foot[0] + 4, foot[1] - 1), INK, 4, 0.4)
    elif pose == "trip":
        p.line((44, 62), (78, 70), MAN_SHIRT, 16, 0.4)
        p.ellipse((38, 36, 70, 68), fill=MAN_SHIRT, outline=INK, width=3)
        p.ellipse((62, 26, 88, 52), fill=SKIN, outline=INK, width=3)
        p.ellipse((62, 20, 76, 28), fill=(60, 48, 40, 255), outline=INK, width=2)
        d.ellipse((76, 34, 83, 41), fill=WHITE)
        d.ellipse((78, 36, 82, 40), fill=INK)
        d.ellipse((78, 44, 86, 52), fill=INK)                                # рот открыт, паника
        p.line((46, 46), (24, 24), SKIN, 5)
        p.line((60, 48), (46, 18), SKIN, 5)
        p.line((76, 70), (100, 100), MAN_PANTS, 9, 0.4)
        p.line((72, 72), (88, 112), MAN_PANTS, 9, 0.4)
        p.line((34, 62), (16, 92), MAN_PANTS, 9, 0.4)
    elif pose == "fall":
        p.line((26, 58), (64, 48), MAN_SHIRT, 16, 0.4)
        p.ellipse((18, 40, 50, 72), fill=MAN_SHIRT, outline=INK, width=3)
        p.ellipse((62, 42, 88, 68), fill=SKIN, outline=INK, width=3)
        p.ellipse((62, 36, 76, 44), fill=(60, 48, 40, 255), outline=INK, width=2)
        d.ellipse((76, 50, 83, 57), fill=WHITE)
        d.ellipse((78, 52, 82, 56), fill=INK)
        d.ellipse((78, 60, 86, 67), fill=INK)
        p.line((26, 62), (8, 84), SKIN, 5)
        p.line((34, 46), (18, 22), SKIN, 5)
        p.line((58, 62), (92, 44), MAN_PANTS, 9, 0.4)
        p.line((56, 70), (94, 60), MAN_PANTS, 9, 0.4)
    elif pose == "down":
        p.line((22, 88), (60, 84), MAN_SHIRT, 15, 0.4)
        p.ellipse((14, 74, 46, 102), fill=MAN_SHIRT, outline=INK, width=3)
        p.ellipse((60, 78, 86, 104), fill=SKIN, outline=INK, width=3)
        p.ellipse((60, 72, 74, 80), fill=(60, 48, 40, 255), outline=INK, width=2)
        d.ellipse((72, 86, 78, 92), fill=INK)
        p.line((78, 92), (86, 96), INK, 2, 0.4)     # язык
        p.line((56, 92), (92, 96), MAN_PANTS, 9, 0.4)
        p.line((54, 98), (90, 108), MAN_PANTS, 9, 0.4)
    elif pose == "up":
        p.line((52, 66), (60, 92), MAN_SHIRT, 15, 0.4)
        p.ellipse((42, 42, 72, 72), fill=MAN_SHIRT, outline=INK, width=3)
        p.ellipse((54, 20, 78, 46), fill=SKIN, outline=INK, width=3)
        p.ellipse((52, 15, 66, 23), fill=(60, 48, 40, 255), outline=INK, width=2)
        d.ellipse((68, 28, 75, 35), fill=WHITE)
        d.ellipse((70, 30, 74, 34), fill=INK)
        d.ellipse((68, 38, 76, 45), fill=INK)
        p.line((44, 54), (26, 100), SKIN, 5)        # опора о землю
        p.line((66, 54), (80, 38), SKIN, 5)
        p.line((60, 92), (86, 112), MAN_PANTS, 9, 0.4)
        p.line((58, 94), (40, 118), MAN_PANTS, 9, 0.4)
    return im


# ----------------------------------------------------------------- реквизит
def prop(kind):
    im = _canvas(96, 84)
    d = ImageDraw.Draw(im)
    p = Pen(d, random.Random(3000 + sum(map(ord, kind))))
    if kind == "banana":
        p.ellipse((22, 56, 74, 82), fill=YELLOW, width=3)
        p.line((30, 62), (62, 58), (160, 118, 44, 255), 3, 0.7)
    elif kind == "hole":
        p.ellipse((12, 50, 84, 82), fill=(54, 44, 36, 255), outline=INK, width=3, flat=0.09)
        p.line((24, 60), (44, 56), (14, 12, 10, 255), 2, 0.5)
        p.line((50, 70), (70, 62), (14, 12, 10, 255), 2, 0.5)
    elif kind == "lamp":
        p.line((44, 82), (44, 8), INK, 5)
        p.line((44, 10), (70, 10), INK, 4)
        p.ellipse((62, 6, 84, 26), fill=YELLOW, width=3)
    elif kind == "puddle":
        p.ellipse((10, 56, 86, 80), fill=(150, 200, 220, 255), width=3, flat=0.10)
        p.line((26, 64), (46, 62), (86, 148, 178, 255), 2, 0.5)
    elif kind == "can":
        p.poly([(28, 82), (32, 40), (64, 40), (68, 82)], fill=GREY, width=3)
        p.line((30, 48), (66, 48), INK, 3, 0.4)
        p.ellipse((38, 22, 60, 40), fill=(184, 194, 184, 255), width=2)
        p.line((48, 22), (48, 12), INK, 3, 0.4)
    elif kind == "cone":
        p.poly([(48, 24), (70, 82), (24, 82)], fill=(238, 130, 62, 255), width=3)
        p.line((36, 62), (58, 62), WHITE, 5, 0.4)
        p.line((42, 46), (54, 46), WHITE, 5, 0.4)
        p.line((16, 82), (78, 82), INK, 4, 0.4)
    elif kind == "cat":
        p.ellipse((18, 42, 64, 80), fill=GREY, width=3)
        p.ellipse((48, 26, 78, 56), fill=GREY, width=3)
        p.poly([(52, 30), (54, 14), (62, 28)], fill=GREY, width=2)
        p.poly([(68, 28), (76, 14), (78, 30)], fill=GREY, width=2)
        d.ellipse((60, 36, 65, 41), fill=INK)
        d.ellipse((70, 36, 75, 41), fill=INK)
        p.line((66, 72), (54, 84), INK, 3, 0.5)
    return im


# ----------------------------------------------------------------- фон улицы
def background(width=1500):
    im = _canvas(width, SCENE_H)
    d = ImageDraw.Draw(im)
    rng = random.Random(7)
    p = Pen(d, rng)
    p.line((4, GROUND), (width - 4, GROUND - 2), INK, 3, 1.4, segs=18)
    for x in range(10, width - 20, 58):
        p.line((x, GROUND + 10), (x + 28, GROUND + 9), (172, 166, 158, 255), 2, 0.7)
    x = 6
    while x < width - 50:
        kind = rng.choice(["house", "house", "tree", "lamp", "tree", "house"])
        if kind == "house":
            w, h = rng.randint(52, 88), rng.randint(44, 88)
            top = GROUND - h
            p.poly([(x, top), (x + w, top + 2), (x + w, GROUND), (x, GROUND - 2)],
                   fill=(242, 236, 224, 255), width=3)
            p.line((x, top), (x + w // 2, top - 18), INK, 3, 0.8)
            p.line((x + w // 2, top - 18), (x + w, top + 2), INK, 3, 0.8)
            for wy in range(top + 14, GROUND - 16, 22):
                for wx in range(x + 8, x + w - 14, 20):
                    if rng.random() < 0.7:
                        p.poly([(wx, wy), (wx + 11, wy), (wx + 11, wy + 11), (wx, wy + 11)],
                               fill=(204, 222, 240, 255), width=2, wobble=0.5)
            x += w + rng.randint(8, 20)
        elif kind == "tree":
            p.line((x + 10, GROUND), (x + 10, GROUND - 36), INK, 5, 0.7)
            p.ellipse((x - 14, GROUND - 74, x + 36, GROUND - 26), fill=GREEN, width=3, flat=0.07)
            p.ellipse((x + 2, GROUND - 66, x + 32, GROUND - 36), fill=(62, 132, 76, 255), width=2)
            x += 50
        else:
            p.line((x + 6, GROUND), (x + 6, GROUND - 78), INK, 4, 0.6)
            p.line((x + 6, GROUND - 78), (x + 26, GROUND - 78), INK, 3, 0.6)
            p.ellipse((x + 18, GROUND - 88, x + 34, GROUND - 72), fill=YELLOW, width=3)
            x += 36
    for cx in range(24, width - 50, 214):
        p.ellipse((cx, 6, cx + 56, 28), fill=None, outline=(196, 196, 196, 255), width=2, flat=0.10)
    return im


class Ticker:
    """Готовая полоса бегущей строки на момент t."""

    EVENTS = ["banana", "hole", "lamp", "can", "puddle", "cat"]
    CAPTIONS = ["БЕГИ!", "ОЙ.", "НЕ СЕГОДНЯ", "ААА", "ЗАЯЦ ЖДЁТ", "ПОМОГИТЕ"]
    SPEED = 52.0          # px/сек — строка едет влево

    def __init__(self, bars=44, seed=1, beat=0.5):
        self.bg = background(1500)
        self.rides = [horse_ride(i / 8) for i in range(8)]
        self.runs = [man("run", i / 8) for i in range(8)]
        self.props = {k: prop(k) for k in self.EVENTS}
        self.bars = bars
        self.beat = beat

    def layer(self, t, bands, pulse=0.0):
        """bands — высоты 0..1 для каждого бара; pulse — сила удара 0..1."""
        strip = Image.new("RGBA", (W, H), WHITE)
        d = ImageDraw.Draw(strip)
        p = Pen(d, random.Random(int(t * 1000) % 100000))

        # --- сцена ---
        scene = Image.new("RGBA", (W, SCENE_H), WHITE)
        off = int((t * self.SPEED) % (self.bg.width - W - 2))
        scene.alpha_composite(self.bg.crop((off, 0, off + W, SCENE_H)), (0, 0))

        ep_len = self.beat * 8
        ep = int(t / ep_len)
        ph = (t % ep_len) / ep_len
        ev = self.EVENTS[ep % len(self.EVENTS)]

        bob = math.sin(t * 9.5) * 1.6
        hx = 96 + math.sin(t * 1.9) * 7
        hy = 4 + bob
        jump = 0.0
        if 0.40 < ph < 0.60:                 # конь перелетает через упавшего
            jump = 22 * math.sin((ph - 0.40) / 0.20 * math.pi)
        mx = 380 + math.sin(t * 1.4) * 5
        my = 2

        # причина падения
        if ph < 0.64:
            pr = self.props[ev]
            scene.alpha_composite(pr, (int(mx) + 2, GROUND - 84))

        # мужчина
        if ph < 0.42:
            frame, fdx, fdy = self.runs[int(t * 8) % 8], 0, 0
        elif ph < 0.54:
            frame, fdx, fdy = man("trip"), 0, -int(3 * math.sin((ph - 0.42) / 0.12 * math.pi))
        elif ph < 0.65:
            frame, fdx, fdy = man("fall"), -4, 4
        elif ph < 0.80:
            frame, fdx, fdy = man("down"), -2, 10
        elif ph < 0.94:
            frame, fdx, fdy = man("up"), 2, 8
        else:
            frame, fdx, fdy = self.runs[int(t * 8) % 8], 2, 6
        scene.alpha_composite(frame, (int(mx) + fdx, int(my) + fdy))

        # заяц на коне
        scene.alpha_composite(self.rides[int(t * 8) % 8], (int(hx), int(hy - jump)))

        # звёздочки/пыль от падения
        if 0.50 < ph < 0.88:
            for i in range(3):
                a = t * 5.5 + i * 2.2
                sx = mx + 34 + math.cos(a) * 20
                sy = my + 46 + math.sin(a) * 8 - fdy
                p.line((sx - 4, sy), (sx + 4, sy), YELLOW, 2, 0.4, segs=2, taper=False)
                p.line((sx, sy - 4), (sx, sy + 4), YELLOW, 2, 0.4, segs=2, taper=False)

        # подпись над сценой — как в меме
        cap = self.CAPTIONS[ep % len(self.CAPTIONS)]
        if 0.05 < ph < 0.55:
            d.text((392, 10), cap, font=FONT_BIG, fill=INK)
            d.text((393, 11), cap, font=FONT_BIG, fill=(70, 60, 56, 255))

        strip.alpha_composite(scene, (0, 0))

        # рамка полосы
        p.line((2, 1), (W - 2, 2), INK, 3, 1.0, segs=14)
        p.line((2, SCENE_H - 1), (W - 2, SCENE_H), INK, 3, 1.0, segs=14)

        # --- эквалайзер ---
        n = self.bars
        bw = (W - 14) / n
        base_y = H - 4
        for i in range(n):
            v = bands[i] if i < len(bands) else 0.0
            v = max(0.03, min(1.0, v * (0.72 + 0.6 * pulse)))
            h = int(v * (BARS_H - 8))
            x0 = 7 + i * bw + 1.0
            x1 = x0 + bw - 2.0
            color = [INK, RED, INK, BLUE, INK, GREEN][i % 6]
            p.poly([(x0, base_y), (x0 + 0.6, base_y - h), (x1, base_y - h - 1), (x1 - 0.4, base_y)],
                   fill=color, outline=INK, width=2, wobble=0.5,
                   origin=((x0 + x1) / 2, base_y - h / 2))
        return strip
