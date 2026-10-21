# DeepStick ComfyUI kernel (Wan 2.2 TI2V-5B) — запускается ботом через
# Kaggle API, но можно гонять и руками: Run All, сессия живёт до 12 часов.
# Бот находит адрес туннеля в выходных файлах (tunnel.json) этого ноутбука.

# CELL: 1. Окружение: ComfyUI, модели Wan 2.2, cloudflared
import json
import os
import shutil
import subprocess
import sys
import time

WORK = "/kaggle/working"
COMFY = os.path.join(WORK, "ComfyUI")


def sh(cmd):
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


if not os.path.isdir(COMFY):
    sh(f"git clone -q https://github.com/comfyanonymous/ComfyUI {COMFY}")
sh(f"{sys.executable} -m pip install -q -r {COMFY}/requirements.txt")

from huggingface_hub import hf_hub_download  # noqa: E402

REPO = "Comfy-Org/Wan_2.2_ComfyUI_Repackaged"
FILES = [
    ("split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors",
     "models/diffusion_models"),
    ("split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
     "models/text_encoders"),
    ("split_files/vae/wan2.2_vae.safetensors", "models/vae"),
]
for repo_path, sub in FILES:
    try:
        src = hf_hub_download(REPO, repo_path)
    except Exception:
        src = hf_hub_download(REPO, repo_path.split("/", 1)[1])
    dst_dir = os.path.join(COMFY, sub)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(repo_path))
    if not os.path.exists(dst):
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy(src, dst)
    print("model:", dst, flush=True)

CF = os.path.join(WORK, "cloudflared")
if not os.path.exists(CF):
    sh(f"wget -q https://github.com/cloudflare/cloudflared/releases/latest/"
       f"download/cloudflared-linux-amd64 -O {CF} && chmod +x {CF}")
print("SETUP DONE", flush=True)

# CELL: 2. Запуск ComfyUI и туннеля, публикация адреса для бота
import re  # noqa: E402
import urllib.request  # noqa: E402

comfy_log = open(os.path.join(WORK, "comfy.log"), "wb")
proc = subprocess.Popen(
    [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", "8188",
     "--disable-auto-launch", "--preview-method", "none"],
    cwd=COMFY, stdout=comfy_log, stderr=subprocess.STDOUT)

for _ in range(90):  # ждём ComfyUI до ~7 минут
    try:
        urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=5)
        break
    except Exception:
        if proc.poll() is not None:
            raise RuntimeError("ComfyUI умер при старте, смотри comfy.log")
        time.sleep(5)
print("COMFY UP", flush=True)

tun = subprocess.Popen(
    [CF, "tunnel", "--url", "http://127.0.0.1:8188"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
url = None
for line in tun.stdout:
    print("cloudflared:", line.rstrip(), flush=True)
    m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
    if m:
        url = m.group(0)
        break
if not url:
    raise RuntimeError("cloudflared не дал адрес туннеля")

with open(os.path.join(WORK, "tunnel.json"), "w") as fh:
    json.dump({"url": url, "ts": time.time()}, fh)
print("COMFY_URL", url, flush=True)

# CELL: 3. Держим сессию живой (Kaggle убьёт её максимум через 12 часов)
while True:
    time.sleep(240)
    try:
        urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=10)
        print("alive", time.strftime("%H:%M:%S"), flush=True)
    except Exception as e:
        print("comfy ping failed:", e, flush=True)
    if proc.poll() is not None:
        raise RuntimeError("ComfyUI процесс завершился")
