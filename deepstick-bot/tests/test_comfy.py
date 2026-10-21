"""Kaggle-ComfyUI: воркфлоу, сборка ноутбука, поиск туннеля."""
import base64
import json

from app.comfy import build_image_workflow, build_notebook, build_workflow, extract_tunnel, find_tunnel_url, format_log_tail, parse_log_blob, parse_sse_payload, pick_kernel


def test_build_workflow_structure():
    wf = build_workflow("a cat dances", "photo.png", seed=42)
    types = {node["class_type"] for node in wf.values()}
    assert {"UNETLoader", "LoraLoaderModelOnly", "CLIPLoader", "VAELoader",
            "LoadImage", "WanImageToVideo", "KSampler", "VAEDecode",
            "CreateVideo", "SaveVideo"} <= types
    assert wf["4"]["inputs"]["image"] == "photo.png"
    assert wf["7"]["inputs"]["start_image"] == ["4", 0]
    assert wf["8"]["inputs"]["latent_image"] == ["7", 2]
    assert wf["11"]["inputs"]["video"] == ["10", 0]


def test_workflow_is_fastwan_fast_and_identity_safe():
    from app.comfy import FASTWAN_LORA

    wf = build_workflow("prompt", "photo.png", seed=1)
    # FastWan LoRA поверх базовой 5B, текстовый кодировщик на CPU.
    assert wf["13"]["inputs"]["lora_name"] == FASTWAN_LORA
    assert wf["13"]["inputs"]["model"] == ["1", 0]
    assert wf["12"]["inputs"]["model"] == ["13", 0]
    assert wf["2"]["inputs"]["device"] == "cpu"
    # Быстрый режим автора LoRA: мало шагов, CFG 1, ролик влезает в 3 c.
    assert wf["8"]["inputs"]["steps"] == 6
    assert wf["8"]["inputs"]["cfg"] == 1.0
    assert wf["7"]["inputs"]["length"] == 41  # 41/16 = 2.56 c < 3 c
    # Негатив нацелен на морфинг/потерю лица, а не generic.
    from app.comfy import NEGATIVE

    assert "changing identity" in NEGATIVE and "morphing" in NEGATIVE


def test_build_image_workflow_structure():
    from app.comfy import QWEN_CLIP, QWEN_EDIT_GGUF, QWEN_LIGHTNING_LORA, QWEN_VAE

    wf = build_image_workflow("make a cartoon portrait", "photo.png", seed=7)
    types = {node["class_type"] for node in wf.values()}
    assert {"UnetLoaderGGUF", "LoraLoaderModelOnly", "ModelSamplingAuraFlow",
            "CFGNorm", "CLIPLoader", "VAELoader", "LoadImage",
            "FluxKontextImageScale", "VAEEncode",
            "TextEncodeQwenImageEditPlus",
            "FluxKontextMultiReferenceLatentMethod",
            "KSampler", "VAEDecode", "SaveImage"} <= types
    assert wf["1"]["inputs"]["unet_name"] == QWEN_EDIT_GGUF
    assert wf["2"]["inputs"]["lora_name"] == QWEN_LIGHTNING_LORA
    assert wf["5"]["inputs"]["clip_name"] == QWEN_CLIP
    assert wf["5"]["inputs"]["type"] == "qwen_image"
    assert wf["6"]["inputs"]["vae_name"] == QWEN_VAE
    assert wf["7"]["inputs"]["image"] == "photo.png"
    # Фото реально подаётся в модель: image1 в оба TextEncode (vision-вход)
    # и VAE-латентом в сэмплер — не только текстом промпта.
    assert wf["10"]["inputs"]["image1"] == ["8", 0]
    assert wf["10"]["inputs"]["prompt"] == "make a cartoon portrait"
    assert wf["11"]["inputs"]["image1"] == ["8", 0]
    assert wf["14"]["inputs"]["latent_image"] == ["9", 0]
    # Lightning-режим: 4 шага, CFG 1.
    assert wf["14"]["inputs"]["steps"] == 4
    assert wf["14"]["inputs"]["cfg"] == 1.0
    assert wf["16"]["inputs"]["images"] == ["15", 0]


def test_build_notebook_cells():
    code = ("# CELL: setup\nimport os\nprint(1)\n"
            "# CELL: run\nwhile True:\n    pass\n")
    nb = json.loads(build_notebook(code))
    assert nb["nbformat"] == 4 and len(nb["cells"]) == 2
    assert [c["id"] for c in nb["cells"]] == ["cell-0", "cell-1"]
    assert "import os" in "".join(nb["cells"][0]["source"])
    assert "while True" in "".join(nb["cells"][1]["source"])


def test_kernel_has_no_internet_marker():
    from pathlib import Path

    code = (Path(__file__).resolve().parent.parent
            / "notebooks" / "comfy_kernel.py").read_text()
    assert "KAGGLE_NO_INTERNET" in code
    assert "wait_for_internet" in code


def test_kernel_downloads_fastwan_lora():
    from pathlib import Path

    from app.comfy import (
        FASTWAN_REPO_PATH,
        QWEN_CLIP,
        QWEN_EDIT_GGUF,
        QWEN_LIGHTNING_LORA,
        QWEN_VAE,
    )

    code = (Path(__file__).resolve().parent.parent
            / "notebooks" / "comfy_kernel.py").read_text()
    assert "Kijai/WanVideo_comfy" in code
    assert FASTWAN_REPO_PATH in code
    assert "models/loras" in code
    # Первая стадия: Qwen-Image-Edit-2511 (GGUF) + Lightning LoRA + VL/VAE.
    assert "unsloth/Qwen-Image-Edit-2511-GGUF" in code
    assert "lightx2v/Qwen-Image-Edit-2511-Lightning" in code
    assert "city96/ComfyUI-GGUF" in code
    assert QWEN_EDIT_GGUF in code
    assert QWEN_LIGHTNING_LORA in code
    assert QWEN_CLIP in code
    assert QWEN_VAE in code
    assert "models/unet" in code
    assert "DEEPSTICK_ENGINE qwenedit-fastwan-v4" in code


def test_find_and_extract_tunnel():
    url = "https://abc-def123.trycloudflare.com"
    assert find_tunnel_url(f"log line {url}/x") == url
    assert find_tunnel_url("ничего нет") is None
    payload = base64.b64encode(json.dumps({"url": url}).encode()).decode()
    out = {"files": [{"fileName": "tunnel.json", "fileData": payload}]}
    assert extract_tunnel(out) == url
    assert extract_tunnel({"log": f"COMFY_URL {url}"}) == url  # noqa: F821
    assert extract_tunnel({"files": []}) is None


def test_extract_tunnel_exclude_and_latest():
    old = "https://old-session.trycloudflare.com"
    new = "https://new-session.trycloudflare.com"
    payload = {"log": f"COMFY_URL {old}\n... later ...\nCOMFY_URL {new}"}
    assert extract_tunnel(payload) == new  # свежий адрес — последний в логе
    assert extract_tunnel(payload, exclude={new}) == old
    assert extract_tunnel(payload, exclude={new, old}) is None


def test_format_log_tail_masks_tunnel_and_ansi():
    raw = ("\x1b[31mPHASE setup\x1b[0m\r\n"
           "COMFY_URL https://secret-name.trycloudflare.com\n"
           "Traceback: boom")
    tail = format_log_tail(raw)
    assert "\x1b" not in tail
    assert "secret-name" not in tail
    assert "<tunnel>.trycloudflare.com" in tail
    assert tail.endswith("Traceback: boom")
    assert format_log_tail("") == ""


def test_pick_kernel_matches_title_generated_slug():
    kernels = [
        {"ref": "vadim129/other", "title": "Other", "id": 1},
        {"ref": "vadim129/deepstick-comfyui-wan-2-2",
         "title": "DeepStick ComfyUI (Wan 2.2)", "id": 42,
         "last_run_time": "2026-10-21T18:00:00"},
    ]
    info = pick_kernel(kernels, "vadim129")
    assert info == {"ref": "vadim129/deepstick-comfyui-wan-2-2",
                    "title": "DeepStick ComfyUI (Wan 2.2)", "id": 42}
    assert pick_kernel([], "vadim129") is None


def test_parse_log_stream_helpers():
    assert parse_sse_payload('{"stream_name":"stdout","data":"abc\\n"}') == "abc\n"
    assert parse_sse_payload("END_OF_LOG") is None
    assert parse_sse_payload("plain line") == "plain line"
    blob = json.dumps([{"data": "one "}, {"data": "two"}, {"x": 1}])
    assert parse_log_blob(blob) == "one two"
    assert parse_log_blob("just text") == "just text"


def test_workflow_sampler_and_matte_cap():
    wf = build_workflow("prompt", "photo.png", seed=1)
    assert wf["8"]["inputs"]["sampler_name"] == "uni_pc"
    from app.matting import sticker_frame_cap

    assert sticker_frame_cap(16) == 46  # 46/16 = 2.875 c < 3 c
    assert sticker_frame_cap(30) == 87
    assert sticker_frame_cap(1) >= 1
