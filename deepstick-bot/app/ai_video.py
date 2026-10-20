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


_NEG = ("worst quality, inconsistent motion, blurry, jittery, distorted, "
        "still photo, frozen pose, no motion, static image")


def _ltx_kwargs(image: Path, prompt: str) -> dict:
    from gradio_client import handle_file  # type: ignore

    return dict(
        prompt=prompt, negative_prompt=_NEG,
        input_image_filepath=handle_file(str(image)),
        height_ui=512, width_ui=512,
        duration_ui=float(os.getenv("HF_DURATION", "2.5")),
        api_name="/image_to_video")


def _wan22_kwargs(image: Path, prompt: str, api_name: str = "/generate_video",
                  last_image: bool = False) -> dict:
    from gradio_client import handle_file  # type: ignore

    kwargs = dict(
        input_image=handle_file(str(image)), prompt=prompt,
        steps=int(os.getenv("HF_STEPS", "4")), duration_seconds=2.5,
        api_name=api_name)
    if last_image:
        kwargs["last_image"] = None
    return kwargs


def _ltx23_kwargs(image: Path, prompt: str) -> dict:
    from gradio_client import handle_file  # type: ignore

    return dict(
        input_image=handle_file(str(image)), prompt=prompt, duration=2.5,
        enhance_prompt=False, height=512, width=512, api_name="/generate_video")


def _hunyuan_kwargs(image: Path, prompt: str) -> dict:
    from gradio_client import handle_file  # type: ignore

    return dict(
        input_image=handle_file(str(image)), prompt=prompt,
        length=49, steps=6, do_rewrite=False, api_name="/generate")


def _cogvideo_kwargs(image: Path, prompt: str) -> dict:
    from gradio_client import handle_file  # type: ignore

    return dict(
        prompt=prompt, image_input=handle_file(str(image)), video_input=None,
        api_name="/generate")


def _firstlast_kwargs(image: Path, prompt: str) -> dict:
    from gradio_client import handle_file  # type: ignore

    return dict(
        start_image_pil=handle_file(str(image)),
        end_image_pil=handle_file(str(image)),
        prompt=prompt, duration_seconds=2.1, steps=8,
        api_name="/generate_video")


# Реестр БЕСПЛАТНЫХ image-to-video спейсов (настоящие движения персонажа).
# Порядок — по качеству/скорости. Каждый спейс пробуется дважды: с HF_TOKEN
# (пул квоты аккаунта, 300 c/сутки) и анонимно (отдельный гостевой пул) —
# кончилась одна квота, переключаемся на следующую нейросеть/пул.
SPACE_SPECS: list[dict] = [
    {"id": "Lightricks/ltx-video-distilled", "kwargs": _ltx_kwargs},
    {"id": "Upsampler/ltx-video", "kwargs": _ltx23_kwargs},
    {"id": "Upsampler/wan-2-2-14b-image-to-video", "kwargs": _wan22_kwargs},
    {"id": "preSalesAIAutomation/imagetovideo",
     "kwargs": lambda i, p: _wan22_kwargs(i, p, api_name="/generate_video_sync")},
    {"id": "multimodalart/Hunyuan-Video-1-5", "kwargs": _hunyuan_kwargs},
    {"id": "DeepRat/LTX-Video-ZeroGPU-Optimized", "kwargs": _ltx_kwargs},
    {"id": "makiblek/Wan_2.2_I2V_14B_Custom_Lora_Wow",
     "kwargs": lambda i, p: _wan22_kwargs(i, p, last_image=True)},
    {"id": "zai-org/CogVideoX-5B-Space", "kwargs": _cogvideo_kwargs},
    {"id": "multimodalart/wan-2-2-first-last-frame", "kwargs": _firstlast_kwargs},
]

_QUOTA_HINTS = ("quota", "exceeded", "runs limit", "gpu time", "credit")


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(h in msg for h in _QUOTA_HINTS)


def _call_space_sync(spec: dict, image: Path, prompt: str, out: Path,
                     token: str | None) -> None:
    """Один вызов одного спейса. Результат — сначала во временный файл."""
    try:
        from gradio_client import Client  # type: ignore
    except Exception as exc:
        raise AIError("gradio_client не установлен (pip install gradio_client)") from exc
    client = Client(spec["id"], token=token)
    result = client.predict(**spec["kwargs"](image, prompt))
    tmp = out.with_name(out.stem + ".part.mp4")
    _extract_video_file(result, tmp)
    tmp.replace(out)


def _hf_identities() -> list[tuple[str, str | None]]:
    """Пулы бесплатной квоты: каждый HF-токен = отдельный аккаунт со своими
    300 c/сутки, плюс анонимный гостевой пул. Токены: HF_TOKEN и/или
    HF_TOKENS (несколько через запятую — ротация аккаунтов)."""
    tokens: list[str] = []
    for t in os.getenv("HF_TOKENS", "").split(","):
        t = t.strip()
        if t and t not in tokens:
            tokens.append(t)
    single = os.getenv("HF_TOKEN", "").strip()
    if single and single not in tokens:
        tokens.insert(0, single)
    idents = [(f"token{i + 1}" if len(tokens) > 1 else "token", t)
              for i, t in enumerate(tokens)]
    idents.append(("anon", None))
    return idents


async def _via_hf(image: Path, prompt: str, out: Path) -> None:
    """БЕСПЛАТНЫЕ image-to-video нейросети: реестр публичных HF Spaces.

    Персонаж на видео реально двигается по промпту: прыгает, плачет, танцует.
    Идём по реестру спейсов; каждый пробуем по очереди со всеми пулами квоты
    (токены аккаунтов + анонимный). Спейс упал/кончилась квота — переключаемся
    на следующую нейросеть. При полной неудаче — локальная анимация.
    """
    attempt_timeout = float(os.getenv("HF_ATTEMPT_TIMEOUT", "420"))
    specs = list(SPACE_SPECS)
    override = os.getenv("HF_SPACE", "").strip()
    if override and all(s["id"] != override for s in specs):
        specs.insert(0, {"id": override, "kwargs": _wan22_kwargs})
    identities = _hf_identities()
    dead: set[str] = set()  # пулы квоты, которые уже исчерпаны
    errors: list[str] = []
    for spec in specs:
        for ident, tok in identities:
            if ident in dead:
                continue
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(_call_space_sync, spec, image, prompt, out, tok),
                    timeout=attempt_timeout)
                log.info("AI-видео сгенерировал спейс %s (%s)", spec["id"], ident)
                return
            except Exception as e:
                if _is_quota_error(e):
                    dead.add(ident)
                log.warning("Спейс %s (%s) не смог: %s", spec["id"], ident, e)
                errors.append(f"{spec['id']}[{ident}]: {str(e)[:140]}")
    raise AIError("Все бесплатные нейросети недоступны: " + " || ".join(errors))


async def generate_ai_video(image: Path, prompt: str, out_mp4: Path) -> Path:
    provider = os.getenv("AI_PROVIDER", "none").lower()
    log.info("AI-генерация через %s: %s", provider, prompt[:120])
    if provider == "replicate":
        await _via_replicate(image, prompt, out_mp4)
    elif provider == "fal":
        await _via_fal(image, prompt, out_mp4)
    elif provider == "hf":
        timeout = float(os.getenv("AI_TIMEOUT", "1500"))  # реестр спейсов + очереди
        await asyncio.wait_for(_via_hf(image, prompt, out_mp4), timeout=timeout)
    else:
        raise AIError(f"Неизвестный AI_PROVIDER={provider}")
    if not out_mp4.exists() or out_mp4.stat().st_size == 0:
        raise AIError("AI-провайдер вернул пустой файл")
    return out_mp4
