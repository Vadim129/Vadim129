#!/usr/bin/env python3
"""Загрузка готового файла в заранее созданную resumable-сессию Google Drive.

Сессию создаёт коннектор Arena; здесь только потоковая отправка чанками
(по 8 МиБ, требование Drive — кратность 256 КиБ), без внешних зависимостей.
"""
import json
import os
import sys
import urllib.error
import urllib.request

CHUNK = 8 * 1024 * 1024
KEEP = 256 * 1024


def put(url, data, total, offset, final):
    cmd = "upload, finalize" if final else "upload"
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("X-Goog-Upload-Offset", str(offset))
    req.add_header("X-Goog-Upload-Command", cmd)
    req.add_header("X-Goog-Upload-Total-Size", str(total))
    req.add_header("Content-Length", str(len(data)))
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)


def main(url, path, out):
    total = os.path.getsize(path)
    print(f"файл {path}: {total} байт, чанк {CHUNK}")
    offset = 0
    with open(path, "rb") as fh:
        while offset < total:
            data = fh.read(CHUNK)
            final = offset + len(data) >= total
            st, body, hdr = put(url, data, total, offset, final)
            status = hdr.get("X-Goog-Upload-Status", "?")
            print(f"  offset {offset:>10} +{len(data):>8} -> HTTP {st} status={status}")
            if st not in (200, 201, 308):
                raise SystemExit(f"ошибка загрузки: {st} {body[:500]}")
            if final:
                with open(out, "w") as f:
                    f.write(json.dumps({"status": st, "response": body}, ensure_ascii=False, indent=1))
                print("завершено:", body[:400])
                return
            offset += len(data)
            if status == "active" and st == 308:
                pass


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "/tmp/upload.json")
