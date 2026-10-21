# DeepStick ComfyUI kernel (FLUX Kontext -> Wan 2.2 TI2V-5B + FastWan) — запускается ботом через
# Kaggle API, но можно гонять и руками: Run All, сессия живёт до 12 часов.
# Бот находит адрес туннеля в выходных файлах (tunnel.json) этого ноутбука.

# CELL: 1. Окружение: ComfyUI, модели Wan 2.2, cloudflared
import json
import os
import shutil
import socket
import subprocess
import sys
import time

WORK = "/kaggle/working"
COMFY = os.path.join(WORK, "ComfyUI")


def sh(cmd):
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def wait_for_internet(attempts=8, delay=20):
    """Kaggle без подтверждённого телефона не выпускает сессию в интернет:
    github.com тогда даже не резолвится. Ждём (вдруг DNS моргнул) и падаем
    с понятным маркером, а не с трейсбеком git clone."""
    hosts = ("github.com", "huggingface.co", "pypi.org")
    for attempt in range(1, attempts + 1):
        bad = []
        for host in hosts:
            try:
                socket.getaddrinfo(host, 443)
            except OSError:
                bad.append(host)
        if not bad:
            print("NET OK", flush=True)
            return
        print(f"NET CHECK {attempt}/{attempts}: не резолвятся {bad}",
              flush=True)
        if attempt < attempts:
            time.sleep(delay)
    raise RuntimeError(
        "KAGGLE_NO_INTERNET: сессия Kaggle без интернета "
        "(github.com не резолвится)")


wait_for_internet()
print("PHASE setup: clone ComfyUI", flush=True)
for clone_try in range(1, 4):
    if os.path.isdir(COMFY):
        break
    try:
        sh(f"git clone -q --depth 1 "
           f"https://github.com/comfyanonymous/ComfyUI {COMFY}")
    except subprocess.CalledProcessError:
        shutil.rmtree(COMFY, ignore_errors=True)
        if clone_try == 3:
            raise
        print(f"clone retry {clone_try}/3", flush=True)
        time.sleep(20)
print("PHASE setup: pip requirements", flush=True)
sh(f"{sys.executable} -m pip install -q -r {COMFY}/requirements.txt")

try:
    import torch

    cuda_ok = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if cuda_ok else "-"
    print(f"TORCH {torch.__version__} CUDA={cuda_ok} GPU={gpu_name}",
          flush=True)
except Exception as e:
    raise RuntimeError(f"PyTorch недоступен в сессии Kaggle: {e}") from e
if not cuda_ok:
    raise RuntimeError(
        "Kaggle не дал GPU этой сессии. Включи GPU в ноутбуке и запусти ещё раз.")

print("PHASE setup: download models (Wan/FastWan + FLUX Kontext)", flush=True)
from huggingface_hub import hf_hub_download  # noqa: E402

REPO = "Comfy-Org/Wan_2.2_ComfyUI_Repackaged"
FILES = [
    (REPO, "split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors",
     "models/diffusion_models"),
    (REPO, "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
     "models/text_encoders"),
    (REPO, "split_files/vae/wan2.2_vae.safetensors", "models/vae"),
    # FastWan: дистиллированная LoRA быстрой генерации видео (6 шагов, CFG 1)
    ("Kijai/WanVideo_comfy",
     "FastWan/Wan2_2_5B_FastWanFullAttn_lora_rank_128_bf16.safetensors",
     "models/loras"),
    # FLUX.1 Kontext: первая стадия — стартовый кадр персонажа из фото
    ("Comfy-Org/flux1-kontext-dev_ComfyUI",
     "split_files/diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors",
     "models/diffusion_models"),
    ("Comfy-Org/Lumina_Image_2.0_Repackaged",
     "split_files/vae/ae.safetensors", "models/vae"),
    ("comfyanonymous/flux_text_encoders", "clip_l.safetensors",
     "models/text_encoders"),
    ("comfyanonymous/flux_text_encoders", "t5xxl_fp8_e4m3fn_scaled.safetensors",
     "models/text_encoders"),
]
for repo, repo_path, sub in FILES:
    try:
        src = hf_hub_download(repo, repo_path)
    except Exception:
        src = hf_hub_download(repo, repo_path.split("/", 1)[1])
    dst_dir = os.path.join(COMFY, sub)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(repo_path))
    if os.path.islink(dst) and not os.path.exists(dst):
        os.unlink(dst)  # битая ссылка от прошлого запуска
    if not os.path.exists(dst):
        try:
            os.link(src, dst)
        except OSError:
            try:
                os.symlink(src, dst)
            except OSError:
                shutil.copy(src, dst)
    print("model:", dst, os.path.getsize(dst), flush=True)

print("PHASE setup: cloudflared", flush=True)
CF = os.path.join(WORK, "cloudflared")
if not os.path.exists(CF):
    sh(f"wget -q https://github.com/cloudflare/cloudflared/releases/latest/"
       f"download/cloudflared-linux-amd64 -O {CF} && chmod +x {CF}")
print("DEEPSTICK_ENGINE frame-fastwan-v3", flush=True)
print("SETUP DONE", flush=True)

# CELL: 2. Запуск ComfyUI и туннеля, публикация адреса для бота
import re  # noqa: E402
import urllib.request  # noqa: E402

COMFY_LOG = os.path.join(WORK, "comfy.log")


def tail_text(path, limit=5000):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()[-limit:].strip()
    except Exception as e:
        return f"<не удалось прочитать {path}: {e}>"


comfy_log = open(COMFY_LOG, "wb")
comfy_env = dict(os.environ)
comfy_env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
proc = subprocess.Popen(
    [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", "8188",
     "--disable-auto-launch", "--preview-method", "none"],
    cwd=COMFY, stdout=comfy_log, stderr=subprocess.STDOUT, env=comfy_env)

comfy_ready = False
for _ in range(90):  # ждём ComfyUI до ~7 минут
    try:
        with urllib.request.urlopen(
                "http://127.0.0.1:8188/system_stats", timeout=5) as response:
            response.read(200)
        comfy_ready = True
        break
    except Exception:
        if proc.poll() is not None:
            raise RuntimeError(
                "ComfyUI умер при старте.\n--- comfy.log ---\n"
                + tail_text(COMFY_LOG))
        time.sleep(5)
if not comfy_ready:
    if proc.poll() is None:
        proc.terminate()
    raise RuntimeError(
        "ComfyUI не поднялся за отведённое время.\n--- comfy.log ---\n"
        + tail_text(COMFY_LOG))
print("COMFY UP", flush=True)

tun = subprocess.Popen(
    [CF, "tunnel", "--url", "http://127.0.0.1:8188"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
url = None
cf_lines = []
for line in tun.stdout:
    cf_lines.append(line.rstrip())
    cf_lines = cf_lines[-30:]
    print("cloudflared:", line.rstrip(), flush=True)
    m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
    if m:
        url = m.group(0)
        break
if not url:
    raise RuntimeError(
        "cloudflared не дал адрес туннеля.\n--- cloudflared ---\n"
        + "\n".join(cf_lines))

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
        raise RuntimeError(
            "ComfyUI процесс завершился.\n--- comfy.log ---\n"
            + tail_text(COMFY_LOG))
