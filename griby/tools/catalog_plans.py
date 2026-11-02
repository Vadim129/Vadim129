# -*- coding: utf-8 -*-
"""Каталог кадров прежних листов: по видео на лист, кадр каждые 1,25 с (12 кадров на 15 с).

Нужен, чтобы выбирать планы по фактическому содержимому, а не по номеру.
Кладёт JPEG в ci/mont/cat/oNN/fXX.jpg (ffmpeg ставит нумерацию с 1).
"""
import os, subprocess, importlib.util

spec = importlib.util.spec_from_file_location("bm", "griby/tools/build_montage.py")
bm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bm)

WORK = "/tmp/mont"
OUT = "ci/mont/cat"
os.makedirs(WORK, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def dl(fid, path):
    if os.path.exists(path) and os.path.getsize(path) > 300000:
        return True
    for _ in range(3):
        r = subprocess.run(["gdown", fid, "-O", path], capture_output=True, text=True)
        if os.path.exists(path) and os.path.getsize(path) > 300000:
            return True
        print("retry", fid, (r.stderr or "")[-200:], flush=True)
    print("НЕ СКАЧАЛСЯ", fid, flush=True)
    return False


for k in sorted(bm.OLD):
    fid, _plate = bm.OLD[k]
    src = f"{WORK}/old_{k:02d}.mp4"
    d = f"{OUT}/o{k:02d}"
    os.makedirs(d, exist_ok=True)
    if not dl(fid, src):
        continue
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src,
                    "-vf", "fps=1/1.25,scale=300:-2", "-q:v", "5",
                    f"{d}/f%02d.jpg"], check=False)
    print("лист", k, "кадров", len(os.listdir(d)), flush=True)
