#!/usr/bin/env python3
# Три простых фона для собственного рабочего стола «Перекраса».
# Рисуются кодом (никаких библиотек), чтобы лежать прямо в APK.
import math
import os
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'app', 'src', 'main', 'assets', 'walls')


def png(w, h, rgba):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgba[y * w * 4:(y + 1) * w * 4]

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def dots(w, h):
    buf = bytearray(w * h * 4)
    step = 48
    for y in range(h):
        for x in range(w):
            r = 1.0
            if (x % step - step / 2) ** 2 + (y % step - step / 2) ** 2 < 9:
                r = 1.0 + 0.25 * math.sin((x + y) / 90.0)
            base = lerp((18, 22, 34), (44, 36, 72), (x + y) / float(w + h))
            i = (y * w + x) * 4
            buf[i] = min(255, int(base[0] * r))
            buf[i + 1] = min(255, int(base[1] * r))
            buf[i + 2] = min(255, int(base[2] * r))
            buf[i + 3] = 255
    return bytes(buf)


def waves(w, h):
    buf = bytearray(w * h * 4)
    for y in range(h):
        for x in range(w):
            v = 0.5 + 0.5 * math.sin(x / 120.0 + math.sin(y / 200.0) * 2.0)
            c = lerp((12, 34, 60), (18, 96, 120), v)
            i = (y * w + x) * 4
            buf[i], buf[i + 1], buf[i + 2], buf[i + 3] = c[0], c[1], c[2], 255
    return bytes(buf)


def dark(w, h):
    buf = bytearray(w * h * 4)
    for y in range(h):
        t = y / float(h)
        c = lerp((8, 8, 12), (28, 12, 40), t)
        for x in range(w):
            i = (y * w + x) * 4
            buf[i], buf[i + 1], buf[i + 2], buf[i + 3] = c[0], c[1], c[2], 255
    return bytes(buf)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (('wall_dots.png', dots), ('wall_waves.png', waves), ('wall_dark.png', dark)):
        w = h = 640
        data = fn(w, h)
        path = os.path.join(OUT, name)
        with open(path, 'wb') as f:
            f.write(png(w, h, data))
        print('wrote', os.path.relpath(path, ROOT))


if __name__ == '__main__':
    main()
