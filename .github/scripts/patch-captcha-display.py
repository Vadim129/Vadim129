#!/usr/bin/env python3
"""Build experimental ABI-specific APKs with the captcha prompt suppressed.

This does NOT bypass verification performed by a remote service. Never label the
result a working captcha bypass: an affected connection can stop responding.
"""
import copy
import hashlib
import struct
import sys
import zipfile
import zlib
from pathlib import Path

from loguru import logger
logger.remove()
from androguard.core.apk import APK
from androguard.core.dex import DEX

apk_path, output_dir = Path(sys.argv[1]), Path(sys.argv[2])
expected = '9309781c889578388c250651a9fa3c5c1d4a6e9a0b432dec7e7cc1f93abf57d6'
assert hashlib.sha256(apk_path.read_bytes()).hexdigest() == expected, 'unexpected APK'
source = APK(str(apk_path))
assert source.get_package() == 'com.cybportal.bs' and source.get_androidversion_name() == '1.0.6'
dex = bytearray(source.get_dex())
d = DEX(bytes(dex))
targets = {
    ('LM6/S;', 'onCaptchaRequired', '(Ljava/lang/String;)V'),
    ('Lcom/cybportal/bs/TProxyService;', 'lambda$onCaptchaResurfaceRequested$3', '(Ljava/lang/String;)V'),
}
found = set()
for cls in d.get_classes():
    for m in cls.get_methods():
        key = (cls.get_name(), m.get_name(), m.get_descriptor())
        if key not in targets:
            continue
        code = m.get_code()
        assert code and code.get_tries_size() == 0
        raw = code.get_bc().get_raw()
        start = m.get_code_off() + 16
        assert len(raw) >= 2 and len(raw) % 2 == 0 and dex[start:start+len(raw)] == raw
        dex[start:start+len(raw)] = b'\x0e\x00' + bytes(len(raw)-2)  # return-void, nop padding
        found.add(key)
assert found == targets, f'missing targets: {targets-found}'
dex[12:32] = hashlib.sha1(dex[32:]).digest()
struct.pack_into('<I', dex, 8, zlib.adler32(dex[12:]) & 0xffffffff)
assert hashlib.sha1(dex[32:]).digest() == dex[12:32]
assert zlib.adler32(dex[12:]) & 0xffffffff == struct.unpack_from('<I', dex, 8)[0]
new = DEX(bytes(dex))
for cls in new.get_classes():
    for m in cls.get_methods():
        if (cls.get_name(), m.get_name(), m.get_descriptor()) in targets:
            assert next(m.get_instructions()).get_name() == 'return-void'
output_dir.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(apk_path) as inp:
    for abi in ('arm64-v8a', 'armeabi-v7a'):
        target = output_dir / f'no-captcha-prompt-{abi}-unsigned.apk'
        with zipfile.ZipFile(target, 'w') as out:
            for info in inp.infolist():
                name = info.filename
                if name.startswith('lib/') and not name.startswith(f'lib/{abi}/'):
                    continue
                upper = name.upper()
                if upper.startswith('META-INF/') and (upper.endswith(('.RSA','.DSA','.EC','.SF')) or upper == 'META-INF/MANIFEST.MF'):
                    continue
                data = bytes(dex) if name == 'classes.dex' else inp.read(info)
                out.writestr(copy.copy(info), data)
        with zipfile.ZipFile(target) as check:
            assert check.testzip() is None
            assert check.read('classes.dex') == dex
            assert all(not n.startswith('lib/') or n.startswith(f'lib/{abi}/') for n in check.namelist())
        print(target, target.stat().st_size, flush=True)
