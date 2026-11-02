# -*- coding: utf-8 -*-
"""Пробник новых видео с Google Drive: качает, снимает кадры, клеит контактные листы.

В песочнице Drive недоступен, а в Actions — доступен. Поэтому пробу запускает CI,
а результат (кадры + index.txt) коммитится в ci/probe/ и оттуда читается глазами.

Запуск: python3 griby/tools/probe_new.py
ENV: NEW_IDS — через запятую id новых видео (по умолчанию — папка 1_EkUem...).
"""
import os, subprocess, json, re, sys

OUT = os.environ.get("PROBE_OUT", "ci/probe")
IN = "/tmp/in"

NEW = [
    ("1Ukpo2mmnsMaYXmaebWXMAqIGuH8q48nx", "XhiGFhEiqHTJRzVc7F84e"),
    ("1XQhYbAbOMCws3pzCqRCRopvVi09Da5Uo", "HEeIW78FoDki-0Jye1ork"),
    ("1yvHhY5i2KoB7ku3EJf-qt05kyZ8eIegk", "8DYwVTdzvn6wSFa6S_glq"),
    ("1P07mVelnwDaiT1wHeMvdqG9L015f7opF", "8BLLEMQyKBkcPlVAFRaF8"),
    ("1OiAV92A8sxCKSOPYN1d5EL6lwTaL7dnZ", "mKxIEpfacxh0sND8Es1sl"),
    ("1XbP6SZ-lCZyT1TYcnN6CIMQZFnnfw75u", "jIv4nY07zi60EbVp7FUGl"),
    ("1sgwLUHPEz7pIi2yskRSCNetmlce0iDab", "NufkuE7vFAeAC021gNTpL"),
    ("1Nb4rF_Clj3zjqDnwOio4Ui-MwNKwlhcJ", "kX5obf3AGLatfXUagc3H0"),
    ("1vmOTcrK6H16nCAyayF0OtL4JAOyWLra1", "f0VN9QjMFcSkR0rtTpdEL"),
    ("1CG6wRsnrjK6xNgxFG6ZGTxrHhEj0hmqW", "-Atx8XK0lcO1Jh8Bl0ear"),
    ("1Ls-pWGv1O34ZGgk1ZgQR6XH_f77GZzD1", "1erA77oqUZM0GMhl0ogxl"),
]


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FAIL", cmd[0], (r.stderr or "")[-300:], flush=True)
    return r


def dur(p):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", p])
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def wh(p):
    r = sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
            "stream=width,height,r_frame_rate", "-of", "csv=p=0", p])
    return r.stdout.strip()


def scenes(p):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", p, "-vf",
                        "select='gt(scene,0.30)',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    ts = re.findall(r"pts_time:([0-9.]+)", r.stderr)
    out = []
    for t in ts:
        t = round(float(t), 2)
        if not out or t - out[-1] > 0.4:
            out.append(t)
    return out


def frames(p, name, d):
    os.makedirs(f"{OUT}/f", exist_ok=True)
    files = []
    for i, frac in enumerate((0.06, 0.30, 0.55, 0.80, 0.95)):
        t = max(0.2, d * frac)
        f = f"{OUT}/f/{name}_{i}.jpg"
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", p,
            "-frames:v", "1", "-vf", "scale=420:-2", "-q:v", "4", f])
        if os.path.exists(f):
            files.append((f, t))
    return files


def sheet(name, files):
    from PIL import Image, ImageDraw
    ims = [Image.open(f).convert("RGB") for f, _ in files]
    if not ims:
        return
    w = max(i.width for i in ims)
    h = sum(i.height for i in ims) + 6 * (len(ims) + 1)
    s = Image.new("RGB", (w + 12, h), (16, 16, 18))
    d = ImageDraw.Draw(s)
    y = 6
    for (f, t), im in zip(files, ims):
        s.paste(im, (6, y))
        d.rectangle([6, y, 6 + 150, y + 20], fill=(0, 0, 0))
        d.text((10, y + 5), f"{name}  {t:.1f}s", fill=(255, 255, 0))
        y += im.height + 6
    s.save(f"{OUT}/{name}.jpg", quality=88)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(IN, exist_ok=True)
    idx = []
    for fid, name in NEW:
        p = f"{IN}/{name}.mp4"
        if not (os.path.exists(p) and os.path.getsize(p) > 500000):
            r = sh(["gdown", fid, "-O", p])
            if not (os.path.exists(p) and os.path.getsize(p) > 500000):
                idx.append(f"{name}\tНЕ СКАЧАЛСЯ\t{fid}")
                continue
        d = dur(p)
        files = frames(p, name, d)
        sheet(name, files)
        sc = scenes(p) if d > 2 else []
        idx.append(f"{name}\t{d:.2f}с\t{wh(p)}\t{os.path.getsize(p)//1024}КБ\t"
                   f"склейки: {sc}\t{fid}")
        print(name, round(d, 2), sc, flush=True)
    open(f"{OUT}/index.txt", "w").write("\n".join(idx) + "\n")
    print("\n".join(idx))


if __name__ == "__main__":
    main()
