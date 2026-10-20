"""Опциональная нейро-генерация image-to-video (режим «как оригинал»).

DeepStickBot, судя по его рекламе («загрузи фото, выбери стиль, опиши
сценарий»), не анимирует пиксели локально, а отдаёт фото+промпт в
image-to-video модель и потом перепаковывает результат в WebM-стикер.
Здесь — два популярных провайдера с очередями и поллингом:

  AI_PROVIDER=replicate  REPLICATE_API_TOKEN, REPLICATE_MODEL=kwaivgi/kling-v1.6-standard
  AI_PROVIDER=fal        FAL_KEY,             FAL_MODEL=fal-ai/kling-video/v1.6/standard/image-to-video

Без ключей модуль не используется: бот работает в бесплатном локальном режиме.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
from pathlib import Path

import httpx

log = logging.getLogger(__name__)


class AIError(RuntimeError):
    pass


def ai_enabled() -> bool:
    return os.getenv("AI_PROVIDER", "none").lower() in ("replicate", "fal", "hf")


def _data_uri(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


async def _download(url: str, out: Path) -> None:
    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as c:
        r = await c.get(url)
        r.raise_for_status()
        out.write_bytes(r.content)


async def _via_replicate(image: Path, prompt: str, out: Path) -> None:
    token = os.getenv("REPLICATE_API_TOKEN", "")
    model = os.getenv("REPLICATE_MODEL", "kwaivgi/kling-v1.6-standard")
    if not token:
        raise AIError("Нет REPLICATE_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"input": {"image": _data_uri(image), "prompt": prompt, "duration": 5}}
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"https://api.replicate.com/v1/models/{model}/predictions",
                         headers=headers, json=payload)
        if r.status_code >= 400:
            raise AIError(f"Replicate {r.status_code}: {r.text[:400]}")
        data = r.json()
        get_url = data["urls"]["get"]
        for _ in range(140):  # ~12 минут максимум
            await asyncio.sleep(5)
            r = await c.get(get_url, headers=headers)
            data = r.json()
            if data["status"] == "succeeded":
                output = data["output"]
                url = output[0] if isinstance(output, list) else output
                await _download(url if isinstance(url, str) else url["url"], out)
                return
            if data["status"] in ("failed", "canceled"):
                raise AIError(f"Replicate генерация упала: {data.get('error')}")
    raise AIError("Replicate: таймаут генерации")


async def _via_fal(image: Path, prompt: str, out: Path) -> None:
    key = os.getenv("FAL_KEY", "")
    model = os.getenv("FAL_MODEL", "fal-ai/kling-video/v1.6/standard/image-to-video")
    if not key:
        raise AIError("Нет FAL_KEY")
    headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    payload = {"image_url": _data_uri(image), "prompt": prompt, "duration": "5"}
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"https://queue.fal.run/{model}", headers=headers, json=payload)
        if r.status_code >= 400:
            raise AIError(f"fal.ai {r.status_code}: {r.text[:400]}")
        data = r.json()
        status_url, response_url = data["status_url"], data["response_url"]
        for _ in range(140):
            await asyncio.sleep(5)
            r = await c.get(status_url, headers=headers)
            status = r.json().get("status")
            if status == "COMPLETED":
                r = await c.get(response_url, headers=headers)
                payload_out = r.json()
                video = payload_out.get("video") or {}
                url = video.get("url") if isinstance(video, dict) else None
                if not url:
                    raise AIError(f"fal.ai: нет видео в ответе: {str(payload_out)[:300]}")
                await _download(url, out)
                return
            if status in ("FAILED", "ERROR"):
                raise AIError(f"fal.ai генерация упала: {r.text[:300]}")
    raise AIError("fal.ai: таймаут генерации")


def _extract_video_file(result, out: Path) -> None:
    """Вытащить видеофайл из любого ответа Gradio (вложенные dict/list/tuple)."""
    candidates: list[str] = []

    def walk(node) -> None:  # noqa: ANN001
        if isinstance(node, str):
            candidates.append(node)
        elif isinstance(node, dict):
            for key in ("video", "path", "url", "output"):
                if key in node:
                    walk(node[key])
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)

    walk(result)
    video_exts = (".mp4", ".webm", ".mov", ".gif")
    for cand in candidates:
        if Path(cand).exists() and cand.lower().endswith(video_exts):
            out.write_bytes(Path(cand).read_bytes())
            return
    for cand in candidates:
        if cand.startswith("http") and cand.split("?")[0].lower().endswith(video_exts):
            with httpx.Client(timeout=300, follow_redirects=True) as c:
                r = c.get(cand)
                r.raise_for_status()
                out.write_bytes(r.content)
            return
    raise AIError(f"Не нашёл видеофайл в ответе нейросети: {str(result)[:200]}")


def _via_hf_sync(image: Path, prompt: str, out: Path) -> None:
    """БЕСПЛАТНАЯ image-to-video нейросеть: публичный HF Space (движения персонажа).

    По умолчанию multimodalart/wan2-1-fast (Wan 2.1 I2V + CausVid LoRA):
    эндпоинт /generate_video(input_image, prompt, height, width,
    duration_seconds, steps...). Персонаж на видео реально двигается по промпту:
    прыгает, плачет, танцует — а не качается целиком, как в локальных эффектах.
    Спейс может попросить HF_TOKEN (бесплатный аккаунт HF, токен Read) для
    ZeroGPU-квоты. При любой ошибке вызывающий код откатится на локальную анимацию.
    """
    try:
        from gradio_client import Client, handle_file  # type: ignore
    except Exception as exc:
        raise AIError("gradio_client не установлен (pip install gradio_client)") from exc
    space = os.getenv("HF_SPACE", "multimodalart/wan2-1-fast")
    api_name = os.getenv("HF_API_NAME", "/generate_video")
    client = Client(space, token=os.getenv("HF_TOKEN") or None)
    if "wan2-1-fast" in space or api_name == "/generate_video":
        result = client.predict(
            input_image=handle_file(str(image)),
            prompt=prompt,
            height=512,
            width=512,
            duration_seconds=float(os.getenv("HF_DURATION", "2.9")),
            steps=int(os.getenv("HF_STEPS", "6")),
            api_name="/generate_video",
        )
    else:
        result = client.predict(handle_file(str(image)), prompt, api_name=api_name)
    _extract_video_file(result, out)


async def generate_ai_video(image: Path, prompt: str, out_mp4: Path) -> Path:
    provider = os.getenv("AI_PROVIDER", "none").lower()
    log.info("AI-генерация через %s: %s", provider, prompt[:120])
    if provider == "replicate":
        await _via_replicate(image, prompt, out_mp4)
    elif provider == "fal":
        await _via_fal(image, prompt, out_mp4)
    elif provider == "hf":
        timeout = float(os.getenv("AI_TIMEOUT", "900"))  # бесплатная очередь бывает долгой
        await asyncio.wait_for(asyncio.to_thread(_via_hf_sync, image, prompt, out_mp4),
                               timeout=timeout)
    else:
        raise AIError(f"Неизвестный AI_PROVIDER={provider}")
    if not out_mp4.exists() or out_mp4.stat().st_size == 0:
        raise AIError("AI-провайдер вернул пустой файл")
    return out_mp4
