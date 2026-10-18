#!/usr/bin/env python3
"""Заливка кадров в заранее открытые resumable-сессии Google Drive.

Манифест: строки «путь<TAB>URI». Скрипт идёт по списку, шлёт файл одним
PUT (все файлы < 1 МБ), повторяет при сетевых сбоях, ведёт лог.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def put(url, data, total, offset=0, final=True):
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("X-Goog-Upload-Offset", str(offset))
    req.add_header("X-Goog-Upload-Command", "upload, finalize" if final else "upload")
    req.add_header("X-Goog-Upload-Total-Size", str(total))
    req.add_header("Content-Type", "image/jpeg")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}", {}


def main(manifest):
    rows = []
    for ln in open(manifest, encoding="utf-8"):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        path, uri = ln.split("\t", 1)
        rows.append((path, uri))
    log(f"файлов к загрузке: {len(rows)}")
    ok = fail = 0
    for i, (rel, uri) in enumerate(rows, 1):
        path = os.path.normpath(os.path.join(BASE, "frames_h", rel))
        if not os.path.exists(path):
            log(f"[{i}] НЕТ ФАЙЛА {path}")
            fail += 1
            continue
        data = open(path, "rb").read()
        for attempt in range(1, 5):
            st, body, hdr = put(uri, data, len(data))
            status = hdr.get("X-Goog-Upload-Status")
            if st in (200, 201):
                log(f"[{i}] ok {os.path.basename(path)} {len(data)} b")
                ok += 1
                break
            log(f"[{i}] попытка {attempt}: HTTP {st} status={status} {body[:200]}")
            time.sleep(2 * attempt)
        else:
            log(f"[{i}] НЕ ЗАГРУЖЕН {os.path.basename(path)}")
            fail += 1
    log(f"итог: загружено {ok}, ошибок {fail}")
    with open("/tmp/upload_photos_log.json", "w", encoding="utf-8") as f:
        json.dump({"ok": ok, "fail": fail, "log": LOG}, f, ensure_ascii=False, indent=1)
    if fail:
        raise SystemExit(3)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "fix", "drive_manifest.tsv"))
