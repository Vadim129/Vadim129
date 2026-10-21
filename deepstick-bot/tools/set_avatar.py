"""Одноразово: поставить боту аватарку через Bot API (setMyProfilePhoto).

Запуск: BOT_TOKEN=... python tools/set_avatar.py [путь-к-картинке]
Печатает ответы Telegram: getMe -> setMyProfilePhoto -> getUserProfilePhotos.
"""
import json
import os
import sys
import urllib.request
import uuid
from pathlib import Path

API = "https://api.telegram.org/bot{token}/{method}"


def call(token: str, method: str, body: bytes | None = None,
         ctype: str | None = None):
    req = urllib.request.Request(API.format(token=token, method=method),
                                 data=body, method="POST" if body else "GET")
    if ctype:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def main() -> int:
    token = os.environ["BOT_TOKEN"]
    img = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parents[1] / "bot_avatar.png")
    data = img.read_bytes()
    print("image:", img, len(data), "bytes")

    me = call(token, "getMe")
    print("getMe:", json.dumps(me, ensure_ascii=False)[:300])
    bot_id = me["result"]["id"]

    boundary = uuid.uuid4().hex
    photo_json = json.dumps({"type": "static", "photo": "attach://avatar"})
    body = b""
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="photo"\r\n\r\n'
    body += photo_json.encode() + b"\r\n"
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="avatar"; filename="avatar.png"\r\n'
    body += b"Content-Type: image/png\r\n\r\n" + data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    res = call(token, "setMyProfilePhoto", body,
               f"multipart/form-data; boundary={boundary}")
    print("setMyProfilePhoto:", json.dumps(res, ensure_ascii=False)[:400])
    if not res.get("ok"):
        print("FAILED: метод недоступен или картинка отклонена — "
              "аватарку тогда ставит @BotFather (/setuserpic).")
        return 1

    photos = call(token, f"getUserProfilePhotos?user_id={bot_id}&limit=1")
    total = photos.get("result", {}).get("total_count")
    print("profile photos total:", total)
    print("AVATAR SET OK" if total else "set ok, but photos check empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
