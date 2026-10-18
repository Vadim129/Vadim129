#!/usr/bin/env python3
"""Отправка файла в resumable-сессию Google Drive.

Пробуем оба варианта протокола (X-Goog-Upload-* и Content-Range) и пишем
подробный лог инкрементально, чтобы отказ был виден даже при падении.
"""
import json
import os
import sys
import traceback
import urllib.error
import urllib.request

CHUNK = 8 * 1024 * 1024
LOG_PATH = "/tmp/upload_log.txt"
_fh = None


def log(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    if _fh:
        _fh.write(line + "\n")
        _fh.flush()


def req(url, data, headers):
    r = urllib.request.Request(url, data=data, method="PUT")
    for k, v in headers.items():
        r.add_header(k, v)
    try:
        with urllib.request.urlopen(r, timeout=600) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}", {}


def hdr_xgoog(offset, final, total):
    return {
        "X-Goog-Upload-Offset": str(offset),
        "X-Goog-Upload-Command": "upload, finalize" if final else "upload",
        "X-Goog-Upload-Total-Size": str(total),
        "Content-Type": "application/octet-stream",
    }


def hdr_range(start, end, total):
    return {
        "Content-Range": f"bytes {start}-{end}/{total}",
        "Content-Type": "application/octet-stream",
    }


def backend(url, path, total, mode):
    """mode: 'xgoog' | 'range'. Возвращает (ok, offset_продвинулся)."""
    log(f"-- режим {mode} --")
    offset = 0
    with open(path, "rb") as fh:
        while offset < total:
            data = fh.read(CHUNK)
            end = offset + len(data) - 1
            final = offset + len(data) >= total
            h = hdr_xgoog(offset, final, total) if mode == "xgoog" else hdr_range(offset, end, total)
            st, body, hd = req(url, data, h)
            log(f"{mode}: offset {offset} +{len(data)} -> HTTP {st} "
                f"range={hd.get('Range')} status={hd.get('X-Goog-Upload-Status')} "
                f"body={body[:300]}")
            if st in (200, 201):
                return True, True
            if st == 308:
                offset += len(data)
                continue
            return False, offset > 0
    return False, False


def main(url, path, out):
    total = os.path.getsize(path)
    log(f"файл {path}: {total} байт; URI: {url.split('?')[0]}")
    result = {"ok": False, "mode": None, "total": total}
    for mode in ("xgoog", "range"):
        ok, moved = backend(url, path, total, mode)
        if ok:
            result.update(ok=True, mode=mode)
            break
        if moved:
            log(f"{mode}: часть данных уже принята, второй протокол не пробуем")
            break
    with open(out, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    _fh = open(LOG_PATH, "w")
    try:
        main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "/tmp/upload.json")
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        log("ТРАССИРОВКА:\n" + traceback.format_exc())
        raise
