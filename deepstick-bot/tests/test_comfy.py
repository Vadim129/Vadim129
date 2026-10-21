"""Kaggle-ComfyUI: воркфлоу, сборка ноутбука, поиск туннеля."""
import base64
import json

from app.comfy import build_notebook, build_workflow, extract_tunnel, find_tunnel_url, pick_kernel


def test_build_workflow_structure():
    wf = build_workflow("a cat dances", "photo.png", seed=42)
    types = {node["class_type"] for node in wf.values()}
    assert {"UNETLoader", "CLIPLoader", "VAELoader", "LoadImage",
            "WanImageToVideo", "KSampler", "VAEDecode",
            "CreateVideo", "SaveVideo"} <= types
    assert wf["4"]["inputs"]["image"] == "photo.png"
    assert wf["7"]["inputs"]["start_image"] == ["4", 0]
    assert wf["8"]["inputs"]["latent_image"] == ["7", 2]
    assert wf["11"]["inputs"]["video"] == ["10", 0]


def test_build_notebook_cells():
    code = ("# CELL: setup\nimport os\nprint(1)\n"
            "# CELL: run\nwhile True:\n    pass\n")
    nb = json.loads(build_notebook(code))
    assert nb["nbformat"] == 4 and len(nb["cells"]) == 2
    assert "import os" in "".join(nb["cells"][0]["source"])
    assert "while True" in "".join(nb["cells"][1]["source"])


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
