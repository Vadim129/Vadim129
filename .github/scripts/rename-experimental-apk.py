#!/usr/bin/env python3
"""Rename the Android application label in the experimental arm64 APK."""
import copy
import hashlib
import struct
import sys
import zipfile
from pathlib import Path
from loguru import logger
logger.remove()
from androguard.core.apk import APK

src, dst = map(Path, sys.argv[1:])
assert hashlib.sha256(src.read_bytes()).hexdigest() == '6ad03961ed9f91ea34083fabb7dbcf1d1151d6653d537c91f5ff38dbb57cc5cd'
a = APK(str(src))
assert a.get_package() == 'com.cybportal.bs' and a.get_app_name() == 'КП БС'
with zipfile.ZipFile(src) as inp:
    d = bytearray(inp.read('AndroidManifest.xml'))
    root_type, root_header, root_size = struct.unpack_from('<HHI', d, 0)
    pool_type, pool_header, pool_size = struct.unpack_from('<HHI', d, 8)
    count, styles, flags, strings_start, styles_start = struct.unpack_from('<IIIII', d, 16)
    assert (root_type, root_header, root_size) == (3, 8, len(d))
    assert pool_type == 1 and pool_header == 28 and flags & 0x100 == 0 and styles == 0 and styles_start == 0
    pool_base = 8
    strings_base = pool_base + strings_start
    entries = [struct.unpack_from('<I', d, pool_base + pool_header + 4*i)[0] for i in range(count)]
    matches = []
    for off in entries:
        start = strings_base + off
        size = struct.unpack_from('<H', d, start)[0]
        assert size < 0x8000
        if d[start+2:start+2+2*size].decode('utf-16le') == 'КП БС':
            matches.append((off, start, size))
    assert len(matches) == 1
    target, start, size = matches[0]
    name = 'КП БС 64'
    new = struct.pack('<H', len(name)) + name.encode('utf-16le') + b'\x00\x00'
    old_end = start + 2 + 2*size + 2
    assert d[old_end-2:old_end] == b'\x00\x00'
    delta = len(new) - (old_end - start)
    assert delta > 0
    for i, off in enumerate(entries):
        if off > target:
            struct.pack_into('<I', d, pool_base + pool_header + 4*i, off + delta)
    d[start:old_end] = new
    padding = (-delta) % 4
    d[pool_base + pool_size + delta:pool_base + pool_size + delta] = bytes(padding)
    added = delta + padding
    struct.pack_into('<I', d, pool_base + 4, pool_size + added)
    struct.pack_into('<I', d, 4, root_size + added)
    with zipfile.ZipFile(dst, 'w') as out:
        for info in inp.infolist():
            name = info.filename
            upper = name.upper()
            if upper.startswith('META-INF/') and (upper.endswith(('.RSA', '.DSA', '.EC', '.SF')) or upper == 'META-INF/MANIFEST.MF'):
                continue
            data = bytes(d) if name == 'AndroidManifest.xml' else inp.read(info)
            out.writestr(copy.copy(info), data)
with zipfile.ZipFile(dst) as z:
    assert z.testzip() is None
    assert {n.split('/')[1] for n in z.namelist() if n.startswith('lib/')} == {'arm64-v8a'}
    with zipfile.ZipFile(src) as inp:
        assert z.read('classes.dex') == inp.read('classes.dex')
        assert z.read('lib/arm64-v8a/libgojni.so') == inp.read('lib/arm64-v8a/libgojni.so')
b = APK(str(dst))
assert b.get_package() == 'com.cybportal.bs' and b.get_app_name() == 'КП БС 64'
assert b.get_androidversion_name() == a.get_androidversion_name()
print('verified package', b.get_package(), 'label', b.get_app_name(), 'size', dst.stat().st_size)
