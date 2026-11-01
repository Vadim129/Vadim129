# -*- coding: utf-8 -*-
"""Клип «А представь, мы станем грибами» — сборка по планам раскадровки + липсинк.

Ключевая идея: каждый лист раскадровки = 10 с песни = 4 плана по 2,5 с.
Значит каждый план в клипе обязан длиться ровно 2,5 с и начинаться точно на свою строку.
Липсинк (Wav2Lip) применяется ТОЛЬКО к планам, где она поёт — они перечислены в SING
и взяты строго по промтам листов (Промпт_лист_NN.txt с Google Drive).

Запуск: python3 griby/tools/build_clip.py
ENV: SMOKE=1 — только листы 1–2 (проверка), SKIP_LIPSYNC=1 — без липсинка.
"""
import os, sys, glob, json, shutil, subprocess, time

WORK = os.environ.get("WORK", "/tmp/clipwork")
SRC = f"{WORK}/src"
SEG = f"{WORK}/segs"
CKPT = f"{WORK}/wav2lip"
OUTDIR = os.environ.get("OUTDIR", "/tmp/out")
SONG = f"{WORK}/song.mp3"
SMOKE = os.environ.get("SMOKE") == "1"
SKIP_LIPSYNC = os.environ.get("SKIP_LIPSYNC") == "1"

DUR = 249.48
SHEET = 10.0            # секунд песни на лист
PLAN_OUT = 2.5          # секунд в клипе на план
FPS = 24

SONG_ID = "1yGs88oWAw6TP-EdskGqH41Sjc2m0M309"
CLIPS = {
 1: "b7g6AO-SsLyl-1HMYHR94", 2: "F05dTWcv-J38JotcdOFkb", 3: "vsjhjHwbk2iBp2-wO3uDy",
 4: "C6CS0iMi2wicpnbJKPiYO", 5: "6-Y17BE-dYXXB1xv-UHeV", 6: "jGxBAGohUw_Ynz1OIMuw4",
 7: "I70IjbuFvOxoNIawdpEby", 8: "C0yjn0ycpc6AMvTAspvYu", 9: "AUg40zILdpFzNqpplCA6X",
 10: "Tkejtv3_jGQzXLlkKKlSS", 11: "BKa1owgsawSmdNkTLPhQI", 12: "nnleYkMHWXzHGxiL843vL",
 13: "0TmK7dfF4nHyXvB22iQB7", 14: "vpW18Vw_2FhtJ2SU34tiy", 15: "8u5YqxnHC4V3kGAkquqLT",
 16: "lNr9rOsborrH_CNtKZ0J9", 17: "2d3CTKgfZfxudUO9_ohp4", 18: "5YlImGBwtmVVl4VrApLcA",
 19: "TWxeljKSqtHQ2efheHfn9", 20: "mNttoqYxIhAJcGavJJ784", 21: "4_QcHFF_-7DT9UXBk8BGo",
 22: "55-m8In0chfWOHjS4T30j", 23: "qQA9zjJ_TIIxYuxwFUDUO", 24: "ODrVP7atbvsNrlkRo7jbt",
 25: "wNcHdwJ6NWgoaa34-C5Hr",
}
DRIVE = {
 "b7g6AO-SsLyl-1HMYHR94": "1xQg1Zs9JmK_SXWJJ6N81QS2TN6L6En7I",
 "F05dTWcv-J38JotcdOFkb": "1IG8uh6X8pFbll89OdLko4c8IsYx0WBNH",
 "vsjhjHwbk2iBp2-wO3uDy": "1sFxgfV-gxxwDpBGttTss_0lCXA_bWkmU",
 "C6CS0iMi2wicpnbJKPiYO": "1xKSQHngEV8AXlIYbw8REYMrEtE5Hl7KM",
 "6-Y17BE-dYXXB1xv-UHeV": "1RahvyOH7XCzfOrgSD6xCqA8V0KVRy7gY",
 "jGxBAGohUw_Ynz1OIMuw4": "1SQVBwqXelxFiugw_FIWamiJrFeH29r4U",
 "I70IjbuFvOxoNIawdpEby": "1CFM2P3DwVhw41gK2dwZUeMFyuXpy1pTE",
 "C0yjn0ycpc6AMvTAspvYu": "1j844GV49Tvr53w--GZwus8RhLvrhIxzt",
 "AUg40zILdpFzNqpplCA6X": "1x5-KyYiLE76Sfjv3W7uQx0AvGkvhgz-e",
 "Tkejtv3_jGQzXLlkKKlSS": "1L5YC98k_PScdnL9pd34sLAmtHZ3Q1CDD",
 "BKa1owgsawSmdNkTLPhQI": "1oGcKLNOpGij9XxplNkl6BIrCHYwdqVTa",
 "nnleYkMHWXzHGxiL843vL": "1JBsetIB8E3YIEDBbnzO_ddRc6Jcm5hL_",
 "0TmK7dfF4nHyXvB22iQB7": "1lFequNcvZ-THJ1V8zLIUiGRuVeY5CIWp",
 "vpW18Vw_2FhtJ2SU34tiy": "1cHRwTpuZ6uKTFQ0PXrEu85yiSamt55gY",
 "8u5YqxnHC4V3kGAkquqLT": "1MRjdKoagVmHxjowN8qWub71jB3YwVHA8",
 "lNr9rOsborrH_CNtKZ0J9": "1lFl2xpK3TLthrNQ9KYPrmAvfD4UCcD7t",
 "2d3CTKgfZfxudUO9_ohp4": "1MMACeM4Qd3botfvAwZLHTEVIuKoFG9mI",
 "5YlImGBwtmVVl4VrApLcA": "1tsRP8_zUsuGBLJ_03TZx4WJy0gdzbh7x",
 "TWxeljKSqtHQ2efheHfn9": "1BTidkt4h9kC_LwXck54JpJd2HWoIZxBH",
 "mNttoqYxIhAJcGavJJ784": "189A4WWTn7-bAxvCsvefrvnZ6feysfbID",
 "4_QcHFF_-7DT9UXBk8BGo": "1UAYNvuc5c409XKARI4E4mFXzTBRkKEz3",
 "55-m8In0chfWOHjS4T30j": "1xgl60UaJrYBI83o-9TyTFOnni1NiFx2d",
 "qQA9zjJ_TIIxYuxwFUDUO": "1ZbztiB7TkkQgZq7yY7apCW7A6n5Bvm1w",
 "ODrVP7atbvsNrlkRo7jbt": "1EG-HZjDyfMhvmCXIHeD7OuaVehkjazpd",
 "wNcHdwJ6NWgoaa34-C5Hr": "1yzkIByu1lOdGE7u4cM7sQ-srdL8QCdLH",
}
# конец плашки раскадровки в каждом клипе (сек) — проверено покадрово
PLATE = {1: 1.00, 2: 2.70, 3: 2.20, 4: 2.20, 5: 0.75, 6: 0.75, 7: 1.15, 8: 1.15,
         9: 1.25, 10: 1.15, 11: 0.75, 12: 1.15, 13: 1.15, 14: 0.75, 15: 1.15,
         16: 1.15, 17: 1.15, 18: 1.15, 19: 0.75, 20: 0.75, 21: 1.25, 22: 0.95,
         23: 3.50, 24: 2.70, 25: 0.90}
# планы, где она поёт В КАДРЕ — вычитано построчно из промтов листов (Drive 03_Промпты_видео):
# 1-2 «играет и поёт в камеру» · 6-4 «с электрогитарой поёт» · 7-1 «она поёт» ·
# 7-3 «лицо крупно, поёт в камеру» · 13-3 «поёт и бьёт по струнам» · 15-1 «поёт в камеру у перил» ·
# 19-4 «тихо поёт» · 20-1 «поёт полушёпотом» · 21-4 «лицо в профиль, поёт» · 23-1 «у окна поёт» ·
# всё остальное — грибы, ноги, город, игра без вокала: липсинк не трогаем.
SING = {(1, 2), (6, 4), (7, 1), (7, 3), (13, 3),
        (15, 1), (19, 4), (20, 1), (21, 4), (23, 1)}
XFADE = 0.20
USE = {}   # лист -> чей клип использовать


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} fail: {(r.stderr or '')[-500:]}")
    return r


def push_ci(msg="ci: прогресс"):
    ws = os.environ.get("GITHUB_WORKSPACE")
    if not ws:
        return
    br = os.environ.get("GITHUB_REF_NAME", "arena/7213a08a-vadim129")
    for _ in range(8):
        subprocess.run(["git", "fetch", "-q", "origin", br], cwd=ws, capture_output=True)
        subprocess.run(["git", "reset", "-q", "--mixed", "FETCH_HEAD"], cwd=ws, capture_output=True)
        subprocess.run(["git", "add", "-A", "ci"], cwd=ws, capture_output=True)
        subprocess.run(["git", "-c", "user.name=ci-bot", "-c", "user.email=ci@bot.local",
                        "commit", "-q", "-m", msg], cwd=ws, capture_output=True)
        r = subprocess.run(["git", "push", "-q", "origin", f"HEAD:{br}"], cwd=ws, capture_output=True)
        if r.returncode == 0:
            return True
        time.sleep(3)
    return False


def log(*a):
    print(*a, flush=True)
    if os.environ.get("CI_PUSH") != "1":
        return
    try:
        with open("/tmp/ci_progress.txt", "a") as f:
            f.write(" ".join(str(x) for x in a) + "\n")
        ws = os.environ.get("GITHUB_WORKSPACE")
        if ws:
            os.makedirs(f"{ws}/ci", exist_ok=True)
            shutil.copy("/tmp/ci_progress.txt", f"{ws}/ci/progress.txt")
            pv = f"{WORK}/preview"
            if os.path.isdir(pv):
                shutil.copytree(pv, f"{ws}/ci/preview", dirs_exist_ok=True)
            push_ci("ci: прогресс")
    except Exception as e:
        print("progress fail:", e, flush=True)


def plan_span(sheet):
    """длительность одного плана в исходном клипе (после плашки)"""
    return (15.0 - PLATE[sheet]) / 4.0


def download():
    os.makedirs(SRC, exist_ok=True)
    if not os.path.exists(SONG) or os.path.getsize(SONG) < 1_000_000:
        sh(["gdown", SONG_ID, "-O", SONG])
    want = [CLIPS[n] for n in CLIPS]

    def ok(p):
        if not (os.path.exists(p) and os.path.getsize(p) > 200000):
            return False
        with open(p, "rb") as f:
            return f.read(12)[4:8] == b"ftyp"

    miss = [k for k in want if not ok(f"{SRC}/{k}_alligator.mp4")]
    log(f"нужно докачать клипов: {len(miss)}")
    for k in miss:
        dst = f"{SRC}/{k}_alligator.mp4"
        fid = DRIVE[k]
        for cmd in (["gdown", fid, "-O", dst],
                    ["curl", "-sL", "--retry", "2", "-o", dst,
                     f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t"],
                    ["curl", "-sL", "--retry", "2", "-o", dst,
                     f"https://drive.google.com/uc?id={fid}&export=download"],
                    ["curl", "-sLk", "--retry", "2", "-o", dst,
                     f"https://docs.google.com/uc?export=download&id={fid}"]):
            try:
                sh(cmd)
            except Exception:
                pass
            if ok(dst):
                break
        if not ok(dst):
            log("НЕ скачался:", k)
    got = sum(1 for k in want if ok(f"{SRC}/{k}_alligator.mp4"))
    log(f"клипов на месте: {got}/25")
    lines = []
    for n in CLIPS:
        f = f"{SRC}/{CLIPS[n]}_alligator.mp4"
        if ok(f):
            lines.append(f"лист {n:02d}: {os.path.getsize(f)/1e6:.1f} МБ")
    lines.append(f"песня: {dur(SONG):.2f} с, {os.path.getsize(SONG)/1e6:.1f} МБ")
    ws = os.environ.get("GITHUB_WORKSPACE")
    if ws:
        os.makedirs(f"{ws}/ci", exist_ok=True)
        open(f"{ws}/ci/manifest.txt", "w").write("\n".join(lines) + "\n")
    os.makedirs(f"{WORK}/preview", exist_ok=True)
    for n in (1, 7, 13, 25):
        f = f"{SRC}/{CLIPS[n]}_alligator.mp4"
        if ok(f):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{PLATE[n]+6:.2f}",
                            "-i", f, "-frames:v", "1", "-vf", "scale=640:-2",
                            f"{WORK}/preview/src_{n:02d}.jpg"], capture_output=True)
    log("манифест и кадры-образцы готовы")
    # подстановка: лист без своего клипа берёт ближайший скачанный (только его видео)
    have = [n for n in CLIPS if ok(f"{SRC}/{CLIPS[n]}_alligator.mp4")]
    for n in CLIPS:
        if n in have:
            continue
        near = min(have, key=lambda m: abs(m - n))
        USE[n] = near
        log(f"лист {n:02d}: клип не скачался → беру видео листа {near:02d}")
    return got


def cut_plan(sheet, k, out, quality="16"):
    """сырой отрезок плана k (1..4) из клипа листа, приведённый к 2.5 с"""
    src_n = USE.get(sheet, sheet)
    span = plan_span(src_n)
    st = PLATE[src_n] + (k - 1) * span + 0.12
    take = span - 0.24
    speed = take / PLAN_OUT
    vf = (f"setpts=(PTS-STARTPTS)/{speed:.4f},fps={FPS},"
          "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,"
          "unsharp=5:5:0.35:5:5:0.0")
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{st:.3f}", "-t", f"{take:.3f}",
        "-i", f"{SRC}/{CLIPS[src_n]}_alligator.mp4", "-vf", vf, "-an",
        "-c:v", "libx264", "-crf", quality, "-preset", "veryfast",
        "-t", f"{PLAN_OUT:.3f}", out])
    return out


def cut_audio(sheet, k, out):
    st = (sheet - 1) * SHEET + (k - 1) * PLAN_OUT
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{st:.3f}", "-t", f"{PLAN_OUT:.3f}",
        "-i", SONG, "-ar", "16000", "-ac", "1", out])
    return out


def lipsync_plan(sheet, k, vin, ain, out):
    env = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    base = ["python3", "inference.py",
            "--checkpoint_path", f"{CKPT}/checkpoints/wav2lip_gan.pth",
            "--face", vin, "--audio", ain, "--outfile", out,
            "--face_det_batch_size", "4", "--wav2lip_batch_size", "16"]
    # перебор настроек: чем дальше, тем «грубее» поиск лица
    variants = [(["--pads", "0", "12", "0", "0", "--resize_factor", "1"], "pads12 rf1"),
                (["--pads", "0", "12", "0", "0", "--resize_factor", "2"], "pads12 rf2"),
                (["--pads", "0", "20", "0", "0", "--resize_factor", "2", "--nosmooth"], "pads20 rf2 nosmooth"),
                (["--pads", "10", "25", "10", "10", "--resize_factor", "2", "--static"], "pads25 rf2 static")]
    t = time.time()
    err = ""
    for extra, name in variants:
        if os.path.exists(out):
            os.remove(out)
        r = subprocess.run(base + extra, cwd=CKPT, capture_output=True, text=True, env=env)
        if os.path.exists(out) and os.path.getsize(out) > 20000:
            log(f"   ({name})")
            return True, time.time() - t
        tail = (r.stderr or r.stdout or "").strip().splitlines()
        err = " | ".join(tail[-3:])[:300]
    log(f"   причины: {err}")
    return False, time.time() - t


def build():
    os.makedirs(SEG, exist_ok=True)
    os.makedirs(f"{WORK}/preview", exist_ok=True)
    sheets = [1, 2] if SMOKE else list(range(1, 26))
    tasks = []
    for n in sheets:
        for k in range(1, 5):
            raw = f"{SEG}/p{n:02d}_{k}.mp4"
            cut_plan(n, k, raw)
            need_sync = (n, k) in SING and not SKIP_LIPSYNC
            tasks.append((n, k, raw, need_sync))
        log(f"лист {n:02d}: 4 плана нарезаны")

    import concurrent.futures as cf
    todo = [t for t in tasks if t[3]]
    log(f"планов с пением: {len(todo)} → липсинк")

    def work(t):
        n, k, raw, _ = t
        ain = cut_audio(n, k, f"{SEG}/p{n:02d}_{k}.wav")
        out = f"{SEG}/p{n:02d}_{k}_sync.mp4"
        okk, dt = lipsync_plan(n, k, raw, ain, out)
        return n, k, okk, dt

    if todo:
        with cf.ThreadPoolExecutor(max_workers=3) as ex:
            for n, k, okk, dt in ex.map(work, todo):
                log(f"лист {n:02d} план {k}: {'липсинк ок' if okk else 'НЕ УДАЛСЯ'} за {dt:.0f}с")

    # превью: кадр с лицом до/после
    for n, k, okk in [(t[0], t[1], True) for t in todo]:
        try:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1.2",
                            "-i", f"{SEG}/p{n:02d}_{k}.mp4", "-ss", "1.2",
                            "-i", f"{SEG}/p{n:02d}_{k}_sync.mp4", "-filter_complex",
                            "[0:v]scale=420:-2,setsar=1[a];[1:v]scale=420:-2,setsar=1[b];[a][b]hstack",
                            "-frames:v", "1", "-q:v", "4", f"{WORK}/preview/s{n:02d}_p{k}.jpg"],
                           capture_output=True, timeout=120)
        except Exception:
            pass

    # слоты: 4 плана + мягкие переходы «через чёрное» — таймлайн не сдвигается
    slots = []
    for n in sheets:
        parts = []
        for k in range(1, 5):
            synced = f"{SEG}/p{n:02d}_{k}_sync.mp4"
            if (n, k) in SING and os.path.exists(synced) and os.path.getsize(synced) > 20000:
                parts.append(synced)
            else:
                parts.append(f"{SEG}/p{n:02d}_{k}.mp4")
        slot = f"{SEG}/slot{n:02d}.mp4"
        make_slot(n, parts, slot, sheets)
        slots.append(slot)
        log(f"слот {n:02d} собран")
    return slots


def dur(p):
    import re
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        pass
    r = subprocess.run(["ffmpeg", "-i", p], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        return 0.0
    h, mi, sec = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(sec)


def make_slot(n, parts, out, sheets):
    ins = []
    for p in parts:
        ins += ["-i", p]
    fc = []
    for i in range(4):
        vf = "setsar=1,fps=24"
        if not (n == 1 and i == 0):
            vf += ",fade=t=in:st=0:d=0.10"
        if not (n == max(sheets) and i == 3):
            vf += f",fade=t=out:st={PLAN_OUT-0.10:.2f}:d=0.10"
        fc.append(f"[{i}:v]{vf}[a{i}]")
    fc.append("".join(f"[a{i}]" for i in range(4)) + "concat=n=4:v=1:a=0[v]")
    sh(["ffmpeg", "-v", "error", "-y"] + ins +
       ["-filter_complex", ";".join(fc), "-map", "[v]", "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "14",
        "-pix_fmt", "yuv420p", "-r", "24", out])
    return out


def assemble(slots):
    os.makedirs(OUTDIR, exist_ok=True)
    lst = f"{SEG}/all.txt"
    open(lst, "w").write("".join(f"file '{p}'\n" for p in slots))
    video = f"{SEG}/video_only.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
        "-c", "copy", video])
    D = dur(video)
    DUR = dur(SONG)
    total = min(D, DUR)
    out = f"{OUTDIR}/КЛИП_Грибы_1080p.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", SONG,
        "-map", "0:v", "-map", "1:a", "-c:v", "copy",
        "-af", f"afade=t=out:st={total-2.0:.2f}:d=2.0",
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
        "-t", f"{total:.3f}", "-movflags", "+faststart", out])
    log("ГОТОВО:", out, round(os.path.getsize(out) / 1e6, 1), "МБ",
        "видео", round(D, 2), "песня", round(DUR, 2))
    # версия под Диск: 1080p, но вес < 95 МБ (ограничение загрузки)
    ws = os.environ.get("GITHUB_WORKSPACE")
    if ws:
        light_dir = f"{ws}/dist/clip"
        os.makedirs(light_dir, exist_ok=True)
        light = f"{light_dir}/КЛИП_Грибы_1080p.mp4"
        for crf in (24, 27, 30, 33):
            sh(["ffmpeg", "-v", "error", "-y", "-i", out,
                "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
                "-pix_fmt", "yuv420p", "-r", "24", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", light])
            mb = os.path.getsize(light) / 1e6
            log(f"диск-версия crf{crf}: {mb:.1f} МБ")
            if mb < 95:
                break
        log("диск-версия готова:", light)
    return out


def main():
    t0 = time.time()
    os.makedirs(WORK, exist_ok=True)
    if download() < 10:
        raise SystemExit("мало клипов")
    if not os.path.isdir(CKPT) and not SKIP_LIPSYNC:
        raise SystemExit("Wav2Lip не установлен")
    slots = build()
    assemble(slots)
    log(f"время {time.time()-t0:.0f} с")


if __name__ == "__main__":
    main()
