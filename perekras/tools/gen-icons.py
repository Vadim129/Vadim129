#!/usr/bin/env python3
# Генератор иконок приложения «Своя иконка» (без внешних зависимостей).
# Рисует PNG всех плотностей + foreground для адаптивной иконки.
# Запуск: python3 tools/gen-icons.py   (из папки svoyaikonka/)
import math
import os
import struct
import zlib

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'src', 'main')


# ---------- минимальный PNG-писатель ----------
def png_bytes(w, h, rgba):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgba[y * w * 4:(y + 1) * w * 4]

    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))


# ---------- геометрия (SDF) ----------
def sd_round_box(x, y, half, r):
    qx = abs(x) - half + r
    qy = abs(y) - half + r
    ax, ay = max(qx, 0.0), max(qy, 0.0)
    return math.hypot(ax, ay) + min(max(qx, qy), 0.0) - r


def sd_circle(x, y, r):
    return math.hypot(x, y) - r


def sd_polygon(x, y, pts):
    d = (x - pts[0][0]) ** 2 + (y - pts[0][1]) ** 2
    s = 1.0
    n = len(pts)
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        wx, wy = x - ax, y - ay
        t = max(0.0, min(1.0, (wx * ex + wy * ey) / max(ex * ex + ey * ey, 1e-9)))
        px, py = wx - ex * t, wy - ey * t
        d = min(d, px * px + py * py)
        c1 = y >= ay
        c2 = y < by
        c3 = ex * wy > ey * wx
        if (c1 and c2 and c3) or (not c1 and not c2 and not c3):
            s = -s
    return s * math.sqrt(d)


def star_pts(cx, cy, r_out, r_in, teeth):
    pts = []
    for i in range(teeth * 2):
        a = -math.pi / 2 + i * math.pi / teeth
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def gradient(t, stops):
    """t: 0..1, stops: [(pos, (r,g,b)), ...]"""
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if p0 <= t <= p1:
            k = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
            return tuple(int(round(c0[j] + (c1[j] - c0[j]) * k)) for j in range(3))
    return stops[-1][1]


STOPS = [
    (0.00, (124, 92, 255)),   # фиолетовый
    (0.45, (86, 128, 255)),   # синий
    (1.00, (34, 211, 238)),   # циан
]


def shade(px, py, size, kind, ss=3):
    """Возвращает (r,g,b,a) для точки в координатах -1..1 (центр 0)."""
    half = size / 2.0
    x = (px - half) / half
    y = (py - half) / half
    if kind == 'legacy':
        # фон: скруглённый квадрат на весь размер
        if sd_round_box(x, y, 0.985, 0.42) > 0:
            return None
    elif kind == 'fg':
        # foreground адаптивной иконки: прозрачный фон, глиф в безопасной зоне
        pass
    elif kind == 'round':
        if sd_circle(x, y, 0.985) > 0:
            return None

    glyph_scale = {  # во сколько раз уменьшить глиф внутри иконки
        'legacy': 1.0,
        'round': 1.0,
        'fg': 1.0,
    }[kind]

    # фон только для legacy/round: диагональный градиент
    col = None
    if kind in ('legacy', 'round'):
        t = (x + y + 2.0) / 4.0
        col = gradient(t, STOPS)

    gx, gy = x / glyph_scale, y / glyph_scale
    if kind == 'fg':
        gx, gy = x / 0.62, y / 0.62   # глиф меньше — попадает в safe zone

    # блик-полукруг сверху
    if kind == 'fg':
        if sd_circle(gx - 0.02, gy + 0.02, 0.60) <= 0:
            t = (gx + gy + 2.0) / 4.0
            col = gradient(t, STOPS)
        else:
            return None
    # белая четырёхлучевая звезда + точка
    star = star_pts(0.0, -0.06, 0.40, 0.115, 4)
    in_star = sd_polygon(gx, gy + 0.06, star) <= 0
    in_dot = sd_circle(gx - 0.30, gy - 0.36, 0.105) <= 0
    if in_star or in_dot:
        return (255, 255, 255, 255)
    if col is None:
        return None
    return (col[0], col[1], col[2], 255)


def render(size, kind, ss=3):
    buf = bytearray(size * size * 4)
    for py in range(size):
        for px in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(ss):
                for sx in range(ss):
                    fx = px + (sx + 0.5) / ss
                    fy = py + (sy + 0.5) / ss
                    c = shade(fx, fy, size, kind)
                    if c:
                        acc[0] += c[0]
                        acc[1] += c[1]
                        acc[2] += c[2]
                        acc[3] += 255
            n = ss * ss
            a = acc[3] / n
            if a <= 0:
                continue
            # цвет усредняем только по «закрашенным» сэмплам
            cov = acc[3] / 255.0
            i = (py * size + px) * 4
            buf[i] = int(acc[0] / cov)
            buf[i + 1] = int(acc[1] / cov)
            buf[i + 2] = int(acc[2] / cov)
            buf[i + 3] = int(a)
    return bytes(buf)


DENSITIES = {'mdpi': 1.0, 'hdpi': 1.5, 'xhdpi': 2.0, 'xxhdpi': 3.0, 'xxxhdpi': 4.0}


def main():
    for d, k in DENSITIES.items():
        outdir = os.path.join(ROOT, 'res', 'mipmap-' + d)
        os.makedirs(outdir, exist_ok=True)
        for name, kind, base in (
            ('ic_launcher', 'legacy', 48),
            ('ic_launcher_round', 'round', 48),
            ('ic_launcher_foreground', 'fg', 108),
        ):
            size = int(round(base * k))
            data = render(size, kind)
            path = os.path.join(outdir, name + '.png')
            with open(path, 'wb') as f:
                f.write(png_bytes(size, size, data))
            print('wrote', os.path.relpath(path, ROOT), size)
    # превью 512 для README
    os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
    size = 512
    data = render(size, 'legacy', ss=2)
    with open(os.path.join(ROOT, 'docs', 'icon-512.png'), 'wb') as f:
        f.write(png_bytes(size, size, data))
    print('wrote docs/icon-512.png')


if __name__ == '__main__':
    main()
