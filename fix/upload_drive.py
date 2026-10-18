#!/usr/bin/env python3
"""Отправка готового файла в заранее созданную resumable-сессию Google Drive.

Пробуем два способа: (A) один PUT всего файла, (B) чанками по 8 МиБ.
Любой ответ полностью пишется в лог, чтобы диагностировать отказ.
"""
import json
import os
import sys
import urllib.error
import urllib.request

CHUNK = 8 * 1024 * 1024
LOG = []


def log(*a):
    line = " ".join(str(x) for x in a)
    print(line)
    LOG.append(line)


def request(url, data, total, offset, final, extra=None):
    cmd = "upload, finalize" if final else "upload"
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("X-Goog-Upload-Offset", str(offset))
    req.add_header("X-Goog-Upload-Command", cmd)
    req.add_header("X-Goog-Upload-Total-Size", str(total))
    if extra:
        for k, v in extra.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}", {}


def attempt_single(url, path, total):
    log("== попытка A: один PUT всего файла ==")
    with open(path, "rb") as fh:
        data = fh.read()
    st, body, hdr = request(url, data, total, 0, True,
                            {"Content-Type": "video/mp4"})
    log(f"A: HTTP {st} status={hdr.get('X-Goog-Upload-Status')} body={body[:600]}")
    return st in (200, 201), body


def attempt_chunks(url, path, total):
    log("== попытка B: чанками ==")
    offset = 0
    with open(path, "rb") as fh:
        while offset < total:
            data = fh.read(CHUNK)
            final = offset + len(data) >= total
            st, body, hdr = request(url, data, total, offset, final)
            log(f"B: offset {offset} +{len(data)} -> HTTP {st} "
                f"status={hdr.get('X-Goog-Upload-Status')} body={body[:200]}")
            if st not in (200, 201, 308):
                return False, body
            if final:
                return st in (200, 201), body
            offset += len(data)
    return False, "loop ended"


def main(url, path, out):
    total = os.path.getsize(path)
    log(f"файл {path}: {total} байт")
    log("URI (без параметров):", url.split("?")[0])
    ok, body = attempt_single(url, path, total)
    if not ok:
        ok, body = attempt_chunks(url, path, total)
    with open(out, "w") as f:
        json.dump({"ok": ok, "response": body, "log": LOG}, ensure_ascii=False, indent=1)
    with open("/tmp/upload_log.txt", "w") as f:
        f.write("\n".join(LOG) + "\n")
    if not ok:
        raise SystemExit(2)
    log("загружено")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "/tmp/upload.json")
