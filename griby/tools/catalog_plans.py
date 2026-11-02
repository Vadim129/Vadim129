# -*- coding: utf-8 -*-
"""Точный каталог планов: кадр ровно в середине каждого плана (те же формулы, что в сборке).

ci/mont/cat2/oNN_pM.jpg — прежний лист NN, план M; ci/mont/cat2/nNN_pM.jpg — новый лист.
"""
import os, subprocess, importlib.util

spec = importlib.util.spec_from_file_location("bm", "griby/tools/build_montage.py")
bm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bm)

WORK = "/tmp/mont"
OUT = "ci/mont/cat2"
os.makedirs(WORK, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def dl(fid, path):
    if os.path.exists(path) and os.path.getsize(path) > 300000:
        return True
    for _ in range(3):
        r = subprocess.run(["gdown", fid, "-O", path], capture_output=True, text=True)
        if os.path.exists(path) and os.path.getsize(path) > 300000:
            return True
        print("retry", fid, (r.stderr or "")[-150:], flush=True)
    print("НЕ СКАЧАЛСЯ", fid, flush=True)
    return False


def grab(src, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", src,
                    "-frames:v", "1", "-vf", "scale=340:-2", "-q:v", "4", out], check=False)


for k in sorted(bm.OLD):
    fid, plate = bm.OLD[k]
    src = f"{WORK}/old_{k:02d}.mp4"
    if not dl(fid, src):
        continue
    span = (15.0 - plate) / 4.0
    for p in range(1, 5):
        t = plate + (p - 1) * span + 0.06 + 1.25
        grab(src, t, f"{OUT}/o{k:02d}_p{p}.jpg")
    print("прежний", k, flush=True)

for k, (name, fid, plans) in bm.NEW.items():
    src = f"{WORK}/new_{k:02d}.mp4"
    if not dl(fid, src):
        continue
    for p, (start, take) in enumerate(plans, 1):
        t = max(0.0, start) + min(take, bm.PLAN) / 2
        grab(src, t, f"{OUT}/n{k:02d}_p{p}.jpg")
    print("новый", k, flush=True)
