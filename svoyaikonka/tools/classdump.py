#!/usr/bin/env python3
"""Мини-парсер .class из android.jar: показать публичные методы класса с дескрипторами.
Нужен, чтобы сверять сигнатуры API без javap.
usage: python3 tools/classdump.py <android.jar> <dotted.ClassName> [--all] [--grep substr]
"""
import struct
import sys
import zipfile


def parse(data):
    pos = 8
    (cp_count,) = struct.unpack('>H', data[pos:pos + 2])
    pos += 2
    cp = [None] * cp_count
    i = 1
    while i < cp_count:
        tag = data[pos]
        pos += 1
        if tag == 1:
            (ln,) = struct.unpack('>H', data[pos:pos + 2])
            pos += 2
            cp[i] = data[pos:pos + ln].decode('utf-8', 'replace')
            pos += ln
        elif tag in (7, 8, 16, 19, 20):
            cp[i] = ('ref', struct.unpack('>H', data[pos:pos + 2])[0])
            pos += 2
        elif tag in (15,):
            pos += 3
        elif tag in (3, 4, 9, 10, 11, 12, 17, 18):
            pos += 4
        elif tag in (5, 6):
            pos += 8
            i += 1
        else:
            raise ValueError('bad tag %d at %d' % (tag, pos))
        i += 1
    pos += 6  # access, this, super
    (ifc,) = struct.unpack('>H', data[pos:pos + 2])
    pos += 2 + ifc * 2

    def skip_members(pos):
        (n,) = struct.unpack('>H', data[pos:pos + 2])
        pos += 2
        out = []
        for _ in range(n):
            acc, name_i, desc_i, ac = struct.unpack('>HHHH', data[pos:pos + 8])
            pos += 8
            for _ in range(ac):
                (alen,) = struct.unpack('>I', data[pos + 2:pos + 6])
                pos += 6 + alen
            out.append((acc, cp[name_i], cp[desc_i]))
        return pos, out

    pos, fields = skip_members(pos)
    pos, methods = skip_members(pos)
    return cp, fields, methods


def main():
    jar, cls = sys.argv[1], sys.argv[2]
    show_all = '--all' in sys.argv
    grep = None
    if '--grep' in sys.argv:
        grep = sys.argv[sys.argv.index('--grep') + 1].lower()
    with zipfile.ZipFile(jar) as z:
        data = z.read(cls.replace('.', '/') + '.class')
    cp, fields, methods = parse(data)
    print('class', cls, '| fields', len(fields), '| methods', len(methods))
    for acc, name, desc in methods:
        pub = bool(acc & 0x0001)
        if not pub and not show_all:
            continue
        if grep and grep.lower() not in name.lower():
            continue
        flags = []
        if acc & 0x0008:
            flags.append('static')
        if acc & 0x0010:
            flags.append('final')
        if not pub:
            flags.append('nonpublic')
        print('  %-40s %s %s' % (name, desc, ' '.join(flags)))


if __name__ == '__main__':
    main()
