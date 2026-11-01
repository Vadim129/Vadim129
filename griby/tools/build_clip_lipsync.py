# -*- coding: utf-8 -*-
"""Полный пайплайн клипа в GitHub Actions (CPU):
1) качает клипы пользователя и песню с Google Drive,
2) режет на 25 слотов по 10 с (без кусков с раскадровкой),
3) на слотах с лицом прогоняет Wav2Lip по точному куску песни (реальный липсинк),
4) собирает финал 1920x1080 с растворениями и полным звуком.

Запуск: python3 griby/tools/build_clip_lipsync.py
Переменные окружения: SMOKE=1 (быстрый тест: 2 слота), SKIP_LIPSYNC=1.
"""
import os, sys, glob, json, shutil, subprocess, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../griby
WORK = os.environ.get("WORK", "/tmp/clipwork")
SRC = f"{WORK}/src"
SEG = f"{WORK}/segs"
CKPT = f"{WORK}/wav2lip"
OUTDIR = os.environ.get("OUTDIR", "/tmp/out")
SONG = f"{WORK}/song.mp3"
SMOKE = os.environ.get("SMOKE") == "1"
SKIP_LIPSYNC = os.environ.get("SKIP_LIPSYNC") == "1"

DRIVE_IDS = {
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
# чистые куски клипов (без плашки раскадровки), проверено покадрово
CLEAN = {
 1: [(0.30, 15.0)], 2: [(2.55, 15.0)], 3: [(4.10, 15.0)], 4: [(2.40, 12.75)],
 5: [(0.35, 15.0)], 6: [(0.35, 15.0)], 7: [(1.00, 9.30), (9.70, 11.10)],
 8: [(1.00, 15.0)], 9: [(1.20, 15.0)], 10: [(1.00, 15.0)], 11: [(0.60, 15.0)],
 12: [(0.80, 15.0)], 13: [(0.60, 15.0)], 14: [(0.60, 15.0)], 15: [(5.75, 15.0)],
 16: [(0.60, 15.0)], 17: [(1.35, 3.75), (5.35, 8.95)], 18: [(0.75, 15.0)],
 19: [(0.40, 15.0)], 20: [(0.55, 3.75), (9.75, 15.0)], 21: [(1.00, 15.0)],
 22: [(0.55, 8.10), (10.15, 15.0)], 23: [(3.15, 4.75), (5.75, 15.0)],
 24: [(2.55, 15.0)], 25: [(3.00, 14.90)],
}
# слоты, где в кадре её лицо (для липсинка)
FACE = {1, 4, 6, 7, 8, 9, 13, 14, 15, 16, 18, 19, 20, 21, 22, 23, 24, 25}
DUR = 249.48
DISS = 0.30
FPS = 25


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def log(*a):
    print(*a, flush=True)
    if os.environ.get("CI_PUSH") == "1":
        try:
            with open("/tmp/ci_progress.txt", "a") as f:
                f.write(" ".join(str(x) for x in a) + "\n")
            ws = os.environ.get("GITHUB_WORKSPACE")
            if ws:
                shutil.copy("/tmp/ci_progress.txt", f"{ws}/ci/progress.txt")
                pv = os.path.join(WORK, "preview")
                if os.path.isdir(pv):
                    shutil.copytree(pv, f"{ws}/ci/preview", dirs_exist_ok=True)
                subprocess.run(["git", "add", "-A", "ci"], cwd=ws, capture_output=True)
                subprocess.run(["git", "-c", "user.name=ci-bot", "-c", "user.email=ci@bot.local",
                                "commit", "-q", "-m", "ci: прогресс"], cwd=ws, capture_output=True)
                subprocess.run(["git", "push", "-q", "origin", "HEAD:arena/7213a08a-vadim129"],
                               cwd=ws, capture_output=True)
        except Exception as e:
            print("progress push fail:", e, flush=True)


def build_edl():
    edl = []
    for n in range(1, 26):
        d = 10.0 if n < 25 else round(DUR - 240.0, 3)
        need, pieces = d, []
        for s0, s1 in CLEAN[n]:
            if need <= 0.3:
                break
            room = (s1 - s0) - 0.10
            if room < 0.8:
                continue
            take = round(min(need, room), 3)
            pieces.append([round(s0 + 0.05, 3), take])
            need = round(need - take, 3)
        total = sum(p[1] for p in pieces)
        edl.append(dict(sheet=n, clip=CLIPS[n], pieces=pieces, dur=d,
                        speed=round(max(total / d, 0.85), 4)))
    return edl


def download():
    os.makedirs(SRC, exist_ok=True)
    if not os.path.exists(SONG) or os.path.getsize(SONG) < 1_000_000:
        rc, out = sh(["gdown", SONG_ID, "-O", SONG])
        assert os.path.exists(SONG), "песня не скачалась\n" + out[-800:]
    missing = [k for k in CLIPS.values() if not os.path.exists(f"{SRC}/{k}_alligator.mp4")]
    log(f"не хватает клипов: {len(missing)}")

    def fetch(k):
        dst = f"{SRC}/{k}_alligator.mp4"
        fid = DRIVE_IDS[k]
        tries = [
            ["gdown", fid, "-O", dst],
            ["curl", "-sL", "--retry", "2", "-o", dst,
             f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t"],
            ["curl", "-sL", "--retry", "2", "-o", dst, f"https://drive.google.com/uc?export=download&id={fid}"],
            ["gdown", "--fuzzy", f"https://drive.google.com/uc?id={fid}", "-O", dst],
        ]
        for cmd in tries:
            sh(cmd)
            if os.path.exists(dst) and os.path.getsize(dst) > 200000:
                with open(dst, "rb") as f:
                    head = f.read(12)
                if head[4:8] == b"ftyp":     # это mp4, а не html-страница
                    return True
                os.remove(dst)
        return False

    for k in missing:
        okk = False
        for attempt in range(2):
            if fetch(k):
                okk = True
                log("докачан:", k)
                break
            time.sleep(4)
        if not okk:
            log("НЕ скачался:", k, "— возьму соседний клип")
    valid = 0
    for f in glob.glob(f"{SRC}/*_alligator.mp4"):
        if os.path.getsize(f) > 200000:
            with open(f, "rb") as fh:
                if fh.read(12)[4:8] == b"ftyp":
                    valid += 1
    got = valid
    log(f"клипов на месте: {got}/25")
    return got


def cut_slots(edl):
    os.makedirs(SEG, exist_ok=True)
    todo = edl[:2] if SMOKE else edl
    def have(clip):
        p = f"{SRC}/{clip}_alligator.mp4"
        return os.path.exists(p) and os.path.getsize(p) > 200000

    def sub_clip(sheet):
        for d in (1, -1, 2, -2, 3, -3):
            n2 = sheet + d
            if 1 <= n2 <= 25 and have(CLIPS[n2]):
                return CLIPS[n2], CLEAN[n2]
        return s["clip"], s["pieces"]

    for i, s in enumerate(todo):
        t0 = round(10.0 * i, 3)
        clip, ranges = (s["clip"], s["pieces"]) if have(s["clip"]) else sub_clip(s["sheet"])
        if not have(s["clip"]):
            log(f"лист {s['sheet']:02d}: клипа нет, подставлен {clip[:10]}")
            ranges, acc = [], 0.0
            row = max(1.0, 15.0 / max(len(ranges) or 1, 1))
            need = s["dur"] + 1.0
            st = 0.5
            while need > 0.5:
                take = min(need, 15.0 - st - 0.1)
                if take <= 0.5:
                    break
                ranges.append((st, take))
                st += take + 0.05
                need -= take
        parts = []
        for k, (st, take) in enumerate(ranges):
            out = f"{SEG}/s{i:02d}_p{k}.mp4"
            rc, msg = sh(["ffmpeg", "-y", "-ss", str(st), "-t", str(take),
                          "-i", f"{SRC}/{clip}_alligator.mp4", "-an",
                          "-vf", f"fps={FPS},scale=-2:1080:flags=lanczos", "-c:v", "libx264",
                          "-crf", "16", "-preset", "veryfast", out])
            assert rc == 0, msg[-800:]
            parts.append(out)
        raw = parts[0]
        if len(parts) > 1:
            lst = f"{SEG}/s{i:02d}.txt"
            open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
            raw = f"{SEG}/s{i:02d}_raw.mp4"
            sh(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", raw])
        full = f"{SEG}/full{i:02d}.mp4"
        rc, msg = sh(["ffmpeg", "-y", "-i", raw, "-vf",
                      f"setpts=(PTS-STARTPTS)/{s['speed']:.4f},fps={FPS},"
                      "tpad=stop_mode=clone:stop_duration=1.0",
                      "-t", f"{s['dur'] + 0.6:.2f}", "-an", "-c:v", "libx264",
                      "-crf", "16", "-preset", "veryfast", full])
        assert rc == 0, msg[-800:]
        # вход для липсинка: нативная высота источника (клипы и так ~720p) — быстро и без потери качества
        rc, msg = sh(["ffmpeg", "-y", "-i", full, "-vf",
                      "scale=-2:'min(720,ih)':flags=lanczos", "-an", "-c:v", "libx264",
                      "-crf", "16", "-preset", "veryfast", f"{SEG}/s{i:02d}.mp4"])
        assert rc == 0, msg[-800:]
        rc, msg = sh(["ffmpeg", "-y", "-ss", f"{t0:.3f}", "-t", f"{s['dur']:.3f}", "-i", SONG,
                      "-ar", "16000", "-ac", "1", f"{SEG}/a{i:02d}.wav"])
        assert rc == 0, msg[-800:]
        log(f"слот {i+1:02d} (лист {s['sheet']:02d}) нарезан")
    return len(todo)


def singing_ranges(i, slot):
    """Отрезки, где есть её лицо И звучит голос — только их и синхронизируем."""
    import cv2, numpy as np, wave, struct, math
    src = f"{SEG}/s{i:02d}.mp4"
    dur = slot["dur"] + 0.5
    # --- лицо: каскад Хаара по кадрам 4/с
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(1, int(round(fps / 4)))
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    face_t, idx = [], 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if idx % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                h, w = frame.shape[:2]
                small = cv2.resize(frame, (w // 2, h // 2))
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                faces = casc.detectMultiScale(gray, 1.15, 5, minSize=(28, 28))
                big = [f for f in faces if f[2] >= 34]        # крупное лицо = человек, не гриб
                if big:
                    face_t.append(idx / fps)
        idx += 1
    cap.release()
    # --- голос: узкополосная энергия 300–3400 Гц по аудио слота
    wav = f"{SEG}/a{i:02d}.wav"
    with wave.open(wav, "rb") as wf:
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    x = np.array(struct.unpack("<%dh" % (len(raw) // 2), raw), dtype=np.float32) / 32768.0
    win = int(0.05 * sr) or 1
    n = len(x) // win
    e = np.array([np.sqrt(np.mean(x[k * win:(k + 1) * win] ** 2)) for k in range(n)])
    if len(e) == 0:
        return []
    thr = max(np.percentile(e, 40), 0.01)
    voc = e > thr
    # сглаживание 3 окна
    k = np.ones(3) / 3
    voc = np.convolve(voc.astype(float), k, mode="same") > 0.5
    def voc_at(t):
        j = min(len(voc) - 1, max(0, int(t / 0.05)))
        return bool(voc[j])
    if not face_t:
        return []
    # --- объединяем: лицо есть и голос есть
    good = [t for t in face_t if voc_at(t)]
    if not good:
        return []
    good.sort()
    ranges, a = [], good[0]
    for t in good[1:]:
        if t - a > 1.2:
            ranges.append((max(0.0, a - 0.25), min(dur, t + 0.25)))
            a = t
    ranges.append((max(0.0, a - 0.25), min(dur, good[-1] + 0.25)))
    # минимум 0.8 с, склейка близких
    out = []
    for r in ranges:
        if r[1] - r[0] < 0.8:
            continue
        if out and r[0] - out[-1][1] < 0.4:
            out[-1] = (out[-1][0], r[1])
        else:
            out.append(r)
    return out


def lipsync(edl, n_slots):
    import concurrent.futures as cf
    ok_cnt, fail, total_sync = 0, [], 0.0
    os.makedirs(f"{WORK}/preview", exist_ok=True)

    def snap(i, src, out):
        try:
            jpg = f"{WORK}/preview/slot{i+1:02d}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "3", "-i", src,
                            "-ss", "3", "-i", out, "-filter_complex",
                            "[0:v]scale=420:-2,setsar=1[a];[1:v]scale=420:-2,setsar=1[b];[a][b]hstack",
                            "-frames:v", "1", "-q:v", "4", jpg], capture_output=True, timeout=120)
            return os.path.exists(jpg)
        except Exception:
            return False

    # 1) какие слоты вообще нужны — только где лицо и голос
    plan = {}
    for i in range(n_slots):
        if SKIP_LIPSYNC:
            break
        if edl[i]["sheet"] not in FACE:
            continue
        r = singing_ranges(i, edl[i])
        if r:
            plan[i] = r
            total_sync += sum(b - a for a, b in r)
    log(f"поющих отрезков: {sum(len(v) for v in plan.values())} в {len(plan)} слотах, "
        f"всего {total_sync:.1f} с видео")

    # 2) слоты без пения — как есть
    for i in range(n_slots):
        if i not in plan:
            shutil.copy(f"{SEG}/full{i:02d}.mp4", f"{SEG}/sync{i:02d}.mp4")

    # 3) задачи: (слот, отрезок)
    tasks = [(i, k, a, b) for i, rs in plan.items() for k, (a, b) in enumerate(rs)]

    def work(task):
        i, k, a, b = task
        seg_in = f"{SEG}/cut{i:02d}_{k}.mp4"
        seg_wav = f"{SEG}/cut{i:02d}_{k}.wav"
        seg_out = f"{SEG}/cut{i:02d}_{k}_sync.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b-a:.3f}",
                        "-i", f"{SEG}/s{i:02d}.mp4", "-an", "-c:v", "libx264", "-crf", "16",
                        "-preset", "veryfast", seg_in], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b-a:.3f}",
                        "-i", f"{SEG}/a{i:02d}.wav", seg_wav], check=True)
        env = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
        base = ["python3", "inference.py", "--checkpoint_path", f"{CKPT}/checkpoints/wav2lip_gan.pth",
                "--face", seg_in, "--audio", seg_wav, "--outfile", seg_out,
                "--pads", "0", "12", "0", "0", "--resize_factor", "1",
                "--face_det_batch_size", "4", "--wav2lip_batch_size", "16"]
        t = time.time()
        for extra in ([], ["--nosmooth"]):
            subprocess.run(base + extra, cwd=CKPT, capture_output=True, text=True, env=env)
            if os.path.exists(seg_out) and os.path.getsize(seg_out) > 20000:
                return task, time.time() - t, True
        return task, time.time() - t, False

    made = {}
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        for task, dt, okk in ex.map(work, tasks):
            i, k, a, b = task
            made[(i, k)] = okk
            log(f"слот {i+1:02d} отрезок {k+1} ({a:.1f}–{b:.1f} с): "
                f"{'липсинк ок' if okk else 'НЕ УДАЛСЯ'} за {dt:.0f}с")

    # 4) сборка слота обратно: синхронизированные отрезки + оригинал между ними
    for i, rs in plan.items():
        parts, cur = [], 0.0
        for k, (a, b) in enumerate(rs):
            if a - cur > 0.05:
                p = f"{SEG}/keep{i:02d}_{k}.mp4"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{cur:.3f}", "-t", f"{a-cur:.3f}",
                                "-i", f"{SEG}/full{i:02d}.mp4", "-an", "-c:v", "libx264", "-crf", "16",
                                "-preset", "veryfast", p], check=True)
                parts.append(p)
            src_seg = f"{SEG}/cut{i:02d}_{k}_sync.mp4" if made.get((i, k)) else None
            if src_seg is None:
                p = f"{SEG}/orig{i:02d}_{k}.mp4"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b-a:.3f}",
                                "-i", f"{SEG}/full{i:02d}.mp4", "-an", "-c:v", "libx264", "-crf", "16",
                                "-preset", "veryfast", p], check=True)
                parts.append(p)
                if made.get((i, k)) is False:
                    fail.append(i + 1)
            else:
                parts.append(src_seg)
                if (i, k) in made:
                    ok_cnt += 1
            cur = b
        if cur < edl[i]["dur"] + 0.4:
            p = f"{SEG}/keep{i:02d}_end.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{cur:.3f}", "-i", f"{SEG}/full{i:02d}.mp4",
                            "-an", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", p], check=True)
            parts.append(p)
        lst = f"{SEG}/cat{i:02d}.txt"
        open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                        "-c", "copy", f"{SEG}/sync{i:02d}.mp4"], check=True)
        snap(i, f"{SEG}/full{i:02d}.mp4", f"{SEG}/sync{i:02d}.mp4")
    log(f"липсинк: отрезков синхронизировано {ok_cnt}, не удалось {len(fail)} {fail}")
    return ok_cnt


def assemble(edl, n_slots):
    os.makedirs(OUTDIR, exist_ok=True)
    N = n_slots
    T = [0.0]
    for s in edl[:N]:
        T.append(T[-1] + s["dur"])
    for i in range(N):
        rc, msg = sh(["ffmpeg", "-y", "-i", f"{SEG}/sync{i:02d}.mp4", "-vf",
                      "fps=24,scale=1920:1080:force_original_aspect_ratio=increase,"
                      "crop=1920:1080,setsar=1,unsharp=5:5:0.35:5:5:0.0,"
                      "tpad=stop_mode=clone:stop_duration=1.0",
                      "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "16",
                      f"{SEG}/f{i:02d}.mp4"])
        assert rc == 0, msg[-800:]
        log(f"нормализация {i+1:02d}/{N}")
    blocks = [(1, N + 1)] if N <= 6 else [(1, 7), (7, 13), (13, 19), (19, N + 1)]
    parts = []
    for ci, (a, b) in enumerate(blocks):
        ins = []
        for k in range(a - 1, b - 1):
            ins += ["-i", f"{SEG}/f{k:02d}.mp4"]
        fc, prev = [], "[0:v]"
        for k in range(a, b - 1):
            off = (T[k] - T[a - 1]) - DISS
            fc.append(f"{prev}[{k-a+1}:v]xfade=transition=fade:duration={DISS}:offset={off:.3f}[v{k}]")
            prev = f"[v{k}]"
        dur_blk = round(T[b - 1] - T[a - 1], 3)
        if ci == 0:
            fc.append(f"{prev}fade=t=out:st={max(dur_blk-0.18,0):.3f}:d=0.18,format=yuv420p[v]")
        elif ci == len(blocks) - 1:
            fc.append(f"{prev}fade=t=in:st=0:d=0.18,fade=t=out:st={max(dur_blk-1.6,0):.3f}:d=1.6,format=yuv420p[v]")
        else:
            fc.append(f"{prev}fade=t=in:st=0:d=0.18,fade=t=out:st={max(dur_blk-0.18,0):.3f}:d=0.18,format=yuv420p[v]")
        part = f"{WORK}/prt{ci}.mp4"
        rc, msg = sh(["ffmpeg", "-v", "error", "-y"] + ins + ["-filter_complex", ";".join(fc),
                      "-map", "[v]", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                      "-pix_fmt", "yuv420p", "-r", "24", "-an", "-t", f"{dur_blk:.3f}", part])
        assert rc == 0, msg[-1500:]
        parts.append(part)
        log(f"блок {ci+1}/{len(blocks)} собран")
    lst = f"{WORK}/parts.txt"
    open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    out = f"{OUTDIR}/КЛИП_Грибы_липсинк_1080p.mp4"
    total = round(T[N], 3)
    rc, msg = sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", SONG,
                  "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                  "-ar", "48000", "-af", "afade=t=out:st=247.2:d=2.2",
                  "-movflags", "+faststart", "-t", f"{total:.3f}", out])
    assert rc == 0, msg[-1500:]
    log("ГОТОВО:", out, round(os.path.getsize(out) / 1e6, 1), "МБ")
    return out


def main():
    t0 = time.time()
    os.makedirs(WORK, exist_ok=True)
    edl = build_edl()
    log("слотов:", len(edl), "| сумма:", round(sum(s["dur"] for s in edl), 2), "с")
    got = download()
    if got < 10:
        raise SystemExit("мало клипов, дальше нет смысла")
    n = cut_slots(edl)
    if not os.path.isdir(CKPT):
        raise SystemExit("Wav2Lip не установлен — проверь шаг установки")
    lipsync(edl, n)
    out = assemble(edl, n)
    log(f"всего {time.time()-t0:.0f} с")


if __name__ == "__main__":
    main()
