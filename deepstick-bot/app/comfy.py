"""Клиент ComfyUI (Kaggle-бэкенд нейрогенерации) + сборка ноутбука Kaggle.

Схема: владелец запускает из бота Kaggle-кернел (notebooks/comfy_kernel.py):
ComfyUI поднимается на бесплатной GPU, наружу выходит cloudflared-туннель,
бот забирает URL из лога Kaggle и ходит в ComfyUI по HTTP. Генерация —
двухстадийная: сначала FLUX.1 Kontext делает из пользовательского фото
чистый стартовый кадр персонажа в выбранном стиле, затем Wan 2.2 TI2V-5B
+ FastWan LoRA оживляет именно этот кадр. Дальше — покадровый маттинг,
как у HF-провайдера.
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
    "morphing, warping, face deformation, changing identity, different person, "
    "face swap, distorted face, bad anatomy, deformed hands, extra fingers, "
    "extra limbs, flickering, jitter, camera shake, zoom, pan, scene change, "
    "low quality, worst quality, blurry, static, still image, deformed, "
    "watermark, text, logo, jpeg artifacts"
)

# Быстрая дистиллированная модель поверх Wan 2.2 TI2V-5B: FastWan LoRA
# (Kijai/WanVideo_comfy). Рекомендованный режим автора воркфлоу: 4-6 шагов,
# CFG 1.0 — вместо 20 шагов/CFG 5 у базовой модели. При CFG 1 негативный
# промпт почти не влияет, поэтому вся защита персонажа — в позитивном
# промпте (см. build_prompt_wan в app/scenarios.py).
FASTWAN_LORA = "Wan2_2_5B_FastWanFullAttn_lora_rank_128_bf16.safetensors"
FASTWAN_REPO_PATH = f"FastWan/{FASTWAN_LORA}"
WAN_UNET = "wan2.2_ti2v_5B_fp16.safetensors"

# Первая стадия: генерация стартового кадра из фото. FLUX.1 Kontext —
# модель редактирования: переносит персонажа в новый стиль/композицию,
# сохраняя лицо, причёску и одежду с референса. FP8 влезает в T4.
FLUX_KONTEXT_UNET = "flux1-dev-kontext_fp8_scaled.safetensors"
FLUX_CLIP_L = "clip_l.safetensors"
FLUX_T5 = "t5xxl_fp8_e4m3fn_scaled.safetensors"
FLUX_VAE = "ae.safetensors"

_TUNNEL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def build_workflow(prompt_text: str, image_name: str, seed: int,
                   width: int = 512, height: int = 512, length: int = 41,
                   steps: int = 6, cfg: float = 1.0, fps: int = 16) -> dict:
    """API-воркфлоу быстрой генерации: Wan 2.2 TI2V-5B + FastWan LoRA.

    41 кадр @16 fps = 2.56 c: влезает в лимит видеостикера (3 c) без обрезки
    хвоста и считается заметно быстрее прежних 49 кадров. Текстовый
    кодировщик держим на CPU: на T4 (16 ГБ) он иначе постоянно свапается
    с UNet в VRAM и съедает больше времени, чем экономит.
    """
    return {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": WAN_UNET,
                         "weight_dtype": "default"}},
        "13": {"class_type": "LoraLoaderModelOnly",
               "inputs": {"model": ["1", 0], "lora_name": FASTWAN_LORA,
                          "strength_model": 1.0}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                         "type": "wan", "device": "cpu"}},
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
               "inputs": {"model": ["13", 0], "shift": 8.0}},
        "8": {"class_type": "KSampler",
              "inputs": {"model": ["12", 0], "seed": seed, "steps": steps,
                         "cfg": cfg, "sampler_name": "uni_pc",
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


def build_image_workflow(prompt_text: str, image_name: str, seed: int,
                         steps: int = 20, guidance: float = 2.5) -> dict:
    """API-воркфлоу первой стадии: фото -> стартовый кадр (FLUX.1 Kontext).

    Официальная схема Kontext: референс масштабируется FluxKontextImageScale,
    кодируется в латент и подмешивается в кондиционинг через ReferenceLatent;
    сэмплинг идёт от латента референса (denoise 1), поэтому композиция и
    персонаж берутся с фото, а промпт задаёт стиль и чистую подачу кадра.
    Текстовые кодировщики — на CPU: на T4 им не хватает VRAM рядом с UNet.
    """
    return {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": FLUX_KONTEXT_UNET,
                         "weight_dtype": "default"}},
        "2": {"class_type": "DualCLIPLoader",
              "inputs": {"clip_name1": FLUX_CLIP_L, "clip_name2": FLUX_T5,
                         "type": "flux", "device": "cpu"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": FLUX_VAE}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "5": {"class_type": "FluxKontextImageScale",
              "inputs": {"image": ["4", 0]}},
        "6": {"class_type": "VAEEncode",
              "inputs": {"pixels": ["5", 0], "vae": ["3", 0]}},
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": prompt_text}},
        "8": {"class_type": "ConditioningZeroOut",
              "inputs": {"conditioning": ["7", 0]}},
        "9": {"class_type": "ReferenceLatent",
              "inputs": {"conditioning": ["7", 0], "latent": ["6", 0]}},
        "10": {"class_type": "FluxGuidance",
               "inputs": {"conditioning": ["9", 0], "guidance": guidance}},
        "11": {"class_type": "KSampler",
               "inputs": {"model": ["1", 0], "seed": seed, "steps": steps,
                          "cfg": 1.0, "sampler_name": "euler",
                          "scheduler": "simple", "positive": ["10", 0],
                          "negative": ["8", 0], "latent_image": ["6", 0],
                          "denoise": 1.0}},
        "12": {"class_type": "VAEDecode",
               "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage",
               "inputs": {"images": ["12", 0],
                          "filename_prefix": "deepstick_frame"}},
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


async def _object_options(base_url: str, node_class: str,
                          input_name: str) -> list:
    """Список доступных значений combo-входа ноды из /object_info."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
        r = await client.get(f"{base_url.rstrip('/')}/object_info/{node_class}")
        r.raise_for_status()
        node = (r.json() or {}).get(node_class) or {}
        spec = ((node.get("input") or {}).get("required") or {}).get(
            input_name) or [[], {}]
        options = spec[0] if isinstance(spec, (list, tuple)) else []
        return list(options or [])


async def comfy_has_fastwan(base_url: str) -> bool:
    """Есть ли в этом ComfyUI FastWan LoRA."""
    try:
        return FASTWAN_LORA in await _object_options(
            base_url, "LoraLoaderModelOnly", "lora_name")
    except Exception:
        return False


async def comfy_pipeline_ready(base_url: str) -> bool:
    """Поднят ли ComfyUI новым кернелом: FLUX Kontext (кадр) + FastWan (видео).

    Старая сессия без этих моделей честно отвергается: иначе воркфлоу упадёт
    уже на /prompt, а пользователь получит тихий откат не по той причине.
    """
    try:
        unets = await _object_options(base_url, "UNETLoader", "unet_name")
        return (WAN_UNET in unets and FLUX_KONTEXT_UNET in unets
                and await comfy_has_fastwan(base_url))
    except Exception:
        return False


def _require_pipeline(ok: bool) -> None:
    if not ok:
        raise RuntimeError(
            "В Kaggle-сессии нет моделей FLUX Kontext/FastWan — это старая "
            "сессия. Останови её в Kaggle и запусти сессию заново из бота.")


async def _free_memory(client: httpx.AsyncClient, base: str) -> None:
    """Выгрузить модели ComfyUI: после FLUX на T4 не хватит места Wan и наоборот."""
    try:
        await client.post(f"{base}/free",
                          json={"unload_models": True, "free_memory": True})
    except Exception:
        pass


def _find_output(hist: dict, suffixes: tuple[str, ...]) -> dict | None:
    for node_out in (hist.get("outputs") or {}).values():
        for key in ("gifs", "videos", "images", "video"):
            for item in node_out.get(key) or []:
                name = item.get("filename") or ""
                if name.lower().endswith(suffixes):
                    return item
    return None


async def _run_workflow(client: httpx.AsyncClient, base: str, photo: Path,
                        workflow: dict, suffixes: tuple[str, ...],
                        deadline: float, label: str) -> dict:
    """Загрузить картинку, отправить воркфлоу и дождаться выходного файла."""
    with open(photo, "rb") as fh:
        r = await client.post(
            f"{base}/upload/image",
            files={"image": (photo.name, fh, "image/png")},
            data={"overwrite": "true"})
    r.raise_for_status()
    # build_workflow/build_image_workflow ждут имя файла именно в LoadImage:
    # вызывающий код подставляет его через workflow — мы делаем это здесь,
    # чтобы не таскать имя через все сигнатуры.
    for node in workflow.values():
        if node.get("class_type") == "LoadImage":
            node["inputs"]["image"] = r.json()["name"]
    r = await client.post(f"{base}/prompt",
                          json={"prompt": workflow,
                                "client_id": uuid.uuid4().hex})
    r.raise_for_status()
    prompt_id = r.json()["prompt_id"]
    while time.monotonic() < deadline:
        await _sleep(10)
        r = await client.get(f"{base}/history/{prompt_id}")
        r.raise_for_status()
        hist = r.json().get(prompt_id) or {}
        status = (hist.get("status") or {}).get("status_str")
        if status == "error":
            raise RuntimeError(f"ComfyUI workflow error: {str(hist)[:300]}")
        file_ref = _find_output(hist, suffixes)
        if file_ref:
            return file_ref
    raise RuntimeError(f"ComfyUI: {label} не появилось за отведённое время")


async def _download_output(client: httpx.AsyncClient, base: str,
                           file_ref: dict, out: Path, label: str) -> None:
    r = await client.get(
        f"{base}/view",
        params={"filename": file_ref["filename"],
                "subfolder": file_ref.get("subfolder", ""),
                "type": file_ref.get("type", "output")})
    r.raise_for_status()
    out.write_bytes(r.content)
    if out.stat().st_size < 10_000:
        raise RuntimeError(f"ComfyUI: подозрительно пустой файл ({label})")


async def comfy_generate_frame(base_url: str, photo: Path, prompt: str,
                               out: Path, timeout_s: float = 900.0) -> None:
    """Стадия 1: сгенерировать стартовый кадр персонажа из фото (Kontext)."""
    base = base_url.rstrip("/")
    deadline = time.monotonic() + timeout_s
    _require_pipeline(await comfy_pipeline_ready(base))
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        wf = build_image_workflow(
            prompt, "placeholder.png", seed=uuid.uuid4().int % (2 ** 31))
        file_ref = await _run_workflow(
            client, base, photo, wf, (".png", ".jpg", ".jpeg", ".webp"),
            deadline, "стартовый кадр")
        await _download_output(client, base, file_ref, out, "стартовый кадр")
        await _free_memory(client, base)  # дальше Wan: освободить VRAM


async def comfy_generate(base_url: str, photo: Path, prompt: str, out: Path,
                         timeout_s: float = 720.0) -> None:
    """Стадия 2: сгенерировать mp4 (FastWan) по стартовому кадру."""
    base = base_url.rstrip("/")
    deadline = time.monotonic() + timeout_s
    _require_pipeline(await comfy_pipeline_ready(base))
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        wf = build_workflow(prompt, "placeholder.png",
                            seed=uuid.uuid4().int % (2 ** 31))
        file_ref = await _run_workflow(
            client, base, photo, wf, (".mp4", ".webm"), deadline, "видео")
        await _download_output(client, base, file_ref, out, "видео")
        await _free_memory(client, base)


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
