"""Клиент ComfyUI (Kaggle-бэкенд нейрогенерации) + сборка ноутбука Kaggle.

Схема: владелец запускает из бота Kaggle-кернел (kaggle/comfy_kernel.py):
ComfyUI с Wan 2.2 TI2V-5B поднимается на бесплатной GPU, наружу выходит
cloudflared-туннель, его URL кернел пишет в tunnel.json своих выходных
файлов, бот забирает URL через Kaggle API и ходит в ComfyUI по HTTP:
upload/image -> prompt -> history -> view. Всё остальное (маттинг,
локальный откат) — как у HF-провайдера.
"""
from __future__ import annotations

import base64
import json
import re
import time
import uuid
from pathlib import Path

import httpx

NEGATIVE = (
    "low quality, worst quality, blurry, static, still image, deformed, "
    "distorted face, extra fingers, watermark, text, logo, jpeg artifacts"
)

_TUNNEL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def build_workflow(prompt_text: str, image_name: str, seed: int,
                   width: int = 512, height: int = 512, length: int = 49,
                   steps: int = 20, cfg: float = 5.0, fps: int = 16) -> dict:
    """API-воркфлоу Wan 2.2 TI2V-5B: картинка + промпт -> mp4."""
    return {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": "wan2.2_ti2v_5B_fp16.safetensors",
                         "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                         "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader",
              "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": prompt_text}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": NEGATIVE}},
        "7": {"class_type": "WanImageToVideo",
              "inputs": {"positive": ["5", 0], "negative": ["6", 0],
                         "vae": ["3", 0], "width": width, "height": height,
                         "length": length, "batch_size": 1,
                         "start_image": ["4", 0]}},
        "12": {"class_type": "ModelSamplingSD3",
               "inputs": {"model": ["1", 0], "shift": 8.0}},
        "8": {"class_type": "KSampler",
              "inputs": {"model": ["12", 0], "seed": seed, "steps": steps,
                         "cfg": cfg, "sampler_name": "euler",
                         "scheduler": "simple", "positive": ["7", 0],
                         "negative": ["7", 1], "latent_image": ["7", 2],
                         "denoise": 1.0}},
        "9": {"class_type": "VAEDecode",
              "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "CreateVideo",
               "inputs": {"images": ["9", 0], "fps": float(fps)}},
        "11": {"class_type": "SaveVideo",
               "inputs": {"video": ["10", 0], "filename_prefix": "deepstick",
                          "format": "mp4", "codec": "h264"}},
    }


def find_tunnel_url(text: str) -> str | None:
    """Достать URL cloudflared-туннеля из произвольного текста (лог кернела)."""
    m = _TUNNEL_RE.search(text or "")
    return m.group(0) if m else None


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def format_log_tail(text: str, limit: int = 3000) -> str:
    """Компактный и безопасный хвост лога Kaggle для показа в Telegram.

    Оставляем последние строки (там обычно traceback), срезаем ANSI-цвета,
    сверхдлинные progress-бары и маскируем адрес туннеля: ComfyUI за ним
    без авторизации, поэтому светить конкретный поддомен в диагностике
    не нужно.
    """
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    raw = _ANSI_RE.sub("", raw)
    raw = _TUNNEL_RE.sub("https://<tunnel>.trycloudflare.com", raw)
    lines = []
    for line in raw.split("\n"):
        line = line.rstrip()
        if len(line) > 320:
            line = line[:317] + "..."
        if line or (lines and lines[-1]):
            lines.append(line)
    while lines and not lines[-1]:
        lines.pop()
    tail = "\n".join(lines[-90:])
    if len(tail) > limit:
        tail = tail[-limit:]
    return tail.strip()


def parse_sse_payload(payload: str) -> str | None:
    """Одна строка SSE-потока логов Kaggle -> текст (None = конец потока)."""
    payload = (payload or "").strip()
    if payload == "END_OF_LOG":
        return None
    try:
        obj = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        return payload
    if isinstance(obj, dict):
        return str(obj.get("data") or "")
    return ""


def parse_log_blob(body: str) -> str:
    """Лог завершённой сессии Kaggle: JSON-массив событий или plain text."""
    try:
        payload = json.loads(body or "")
    except (json.JSONDecodeError, ValueError):
        return body or ""
    if isinstance(payload, list):
        return "".join(str(e.get("data") or "") for e in payload
                       if isinstance(e, dict))
    if isinstance(payload, dict):
        return str(payload.get("data") or "")
    return body or ""


def extract_tunnel(output: dict, exclude: set[str] | None = None) -> str | None:
    """URL туннеля из ответа Kaggle kernels/output: tunnel.json или лог.

    Формат Kaggle API: {"files": [{"fileName": ..., "fileData": "<base64>"}],
    "log": "..."} — поля могут отсутствовать, всё проверяем мягко.
    exclude — уже проверенные мёртвые адреса прошлых сессий: пропускаем,
    чтобы не зациклиться на устаревшем туннеле.
    """
    skip = exclude or set()
    for f in output.get("files") or []:
        if f.get("fileName") == "tunnel.json" and f.get("fileData"):
            try:
                data = json.loads(base64.b64decode(f["fileData"]))
                url = str(data.get("url") or "").rstrip("/")
                if url and url not in skip:
                    return url
            except Exception:
                pass
    # В тексте берём ПОСЛЕДНИЙ адрес: свежий туннель печатается позже.
    text = (output.get("log") or "") + "\n" + json.dumps(output)
    for url in reversed(_TUNNEL_RE.findall(text)):
        url = url.rstrip("/")
        if url not in skip:
            return url
    return None


def pick_kernel(kernels, username: str) -> dict | None:
    """Найти наш ComfyUI-кернел в списке Kaggle по названию или адресу.

    Kaggle может создать ноутбук с адресом, производным от заголовка, а
    не ровно из переданного slug — поэтому статус и обновление надо вести
    по фактическому ref из аккаунта, а не по предположению.
    """
    def val(obj, key):  # noqa: ANN001, ANN202
        return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)

    matches = []
    for kernel in kernels or []:
        ref = str(val(kernel, "ref") or "")
        slug = str(val(kernel, "slug") or "")
        title = str(val(kernel, "title") or "")
        tail = (ref.rsplit("/", 1)[-1] if ref else slug.rsplit("/", 1)[-1]).lower()
        title_key = " ".join(title.lower().split())
        if "deepstick-comfy" not in tail and title_key not in {
                "deepstick comfyui (wan 2.2)", "deepstick comfy"}:
            continue
        if not ref:
            ref = slug if "/" in slug else f"{username}/{slug}"
        kid = val(kernel, "id")
        matches.append({
            "ref": ref,
            "title": title or "Deepstick Comfy",
            "id": int(kid) if str(kid or "").isdigit() else None,
            "_seen": str(val(kernel, "last_run_time") or ""),
        })
    if not matches:
        return None
    matches.sort(key=lambda item: item["_seen"], reverse=True)
    result = matches[0]
    result.pop("_seen", None)
    return result


def build_notebook(kernel_code: str) -> str:
    """Код кернела (.py с маркерами '# CELL: ...') -> JSON ноутбука Kaggle."""
    cells, cur = [], {"title": "main", "lines": []}
    for line in kernel_code.splitlines():
        if line.startswith("# CELL:"):
            if cur["lines"]:
                cells.append(cur)
            cur = {"title": line.split(":", 1)[1].strip(), "lines": []}
        else:
            cur["lines"].append(line)
    if cur["lines"]:
        cells.append(cur)
    nb_cells = [{
        "cell_type": "code", "execution_count": None, "id": f"cell-{i}",
        "metadata": {}, "outputs": [],
        "source": [ln + "\n" for ln in c["lines"]],
    } for i, c in enumerate(cells)]
    return json.dumps({
        "cells": nb_cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python",
                           "name": "python3"},
            "language_info": {"name": "python", "version": "3.10"},
        },
        "nbformat": 4, "nbformat_minor": 5,
    })


async def comfy_generate(base_url: str, photo: Path, prompt: str, out: Path,
                         timeout_s: float = 720.0) -> None:
    """Сгенерировать mp4 через ComfyUI. Любая проблема — исключение наверх."""
    base = base_url.rstrip("/")
    deadline = time.monotonic() + timeout_s
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        with open(photo, "rb") as fh:
            r = await client.post(
                f"{base}/upload/image",
                files={"image": (photo.name, fh, "image/png")},
                data={"overwrite": "true"})
        r.raise_for_status()
        image_name = r.json()["name"]

        wf = build_workflow(prompt, image_name, seed=uuid.uuid4().int % (2 ** 31))
        r = await client.post(f"{base}/prompt",
                              json={"prompt": wf, "client_id": uuid.uuid4().hex})
        r.raise_for_status()
        prompt_id = r.json()["prompt_id"]

        file_ref = None
        while time.monotonic() < deadline:
            await _sleep(10)
            r = await client.get(f"{base}/history/{prompt_id}")
            r.raise_for_status()
            hist = r.json().get(prompt_id) or {}
            status = (hist.get("status") or {}).get("status_str")
            if status == "error":
                raise RuntimeError(f"ComfyUI workflow error: {str(hist)[:300]}")
            for node_out in (hist.get("outputs") or {}).values():
                for key in ("gifs", "videos", "images", "video"):
                    for item in node_out.get(key) or []:
                        name = item.get("filename") or ""
                        if name.lower().endswith((".mp4", ".webm")):
                            file_ref = item
            if file_ref:
                break
        if not file_ref:
            raise RuntimeError("ComfyUI: видео не появилось за отведённое время")

        r = await client.get(
            f"{base}/view",
            params={"filename": file_ref["filename"],
                    "subfolder": file_ref.get("subfolder", ""),
                    "type": file_ref.get("type", "output")})
        r.raise_for_status()
        out.write_bytes(r.content)
        if out.stat().st_size < 10_000:
            raise RuntimeError("ComfyUI: подозрительно пустой видеофайл")


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
