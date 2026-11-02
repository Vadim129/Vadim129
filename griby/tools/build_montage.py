# -*- coding: utf-8 -*-
"""Монтаж нового клипа «Грибы» — только отдельные листы, готовый клип не используется.

Источники:
  NEW — 8 новых видео из папки 1_EkUemxa8HkGlCKZlvmgr6z_dXOfB3IJ (по 4 плана);
  OLD — прежние листы (по одному видео на лист), из них вырезается плашка раскадровки.

Раскладка: 100 планов по 2,5 с = 250 с, песня 249,48 с.
Девушка — только в проигрышах (планы 28–35, 59–66, 72–76, 91–94).

Запуск: python3 griby/tools/build_montage.py
ENV: OUTDIR (по умолчанию /tmp/out), CI_PUSH=1 — выложить в dist/clip.
"""
import os, subprocess, shutil, time

WORK = "/tmp/mont"
SEG = f"{WORK}/seg"
OUTDIR = os.environ.get("OUTDIR", "/tmp/out")
SONG_ID = "1yGs88oWAw6TP-EdskGqH41Sjc2m0M309"
SONG = f"{WORK}/song.mp3"
FPS = 24
PLAN = 2.5
W, H = 1920, 1080

# новые видео: ключ -> (имя, id, [(начало плана, длина до монтажа)])
NEW = {
 1:  ("f0VN9QjMFcSkR0rtTpdEL", "1vmOTcrK6H16nCAyayF0OtL4JAOyWLra1",
      [(0.70, 2.50), (3.10, 2.50), (7.25, 2.50), (11.20, 2.50)]),
 6:  ("kX5obf3AGLatfXUagc3H0", "1Nb4rF_Clj3zjqDnwOio4Ui-MwNKwlhcJ",
      [(0.90, 2.50), (4.20, 2.50), (8.55, 2.50), (13.45, 1.50)]),
 7:  ("NufkuE7vFAeAC021gNTpL", "1sgwLUHPEz7pIi2yskRSCNetmlce0iDab",
      [(0.60, 2.50), (3.50, 2.50), (6.50, 2.50), (10.00, 2.50)]),
 8:  ("mKxIEpfacxh0sND8Es1sl", "1OiAV92A8sxCKSOPYN1d5EL6lwTaL7dnZ",
      [(2.20, 2.50), (2.20, 2.50), (6.85, 2.50), (10.55, 2.50)]),
 11: ("8BLLEMQyKBkcPlVAFRaF8", "1P07mVelnwDaiT1wHeMvdqG9L015f7opF",
      [(0.70, 2.50), (3.60, 2.50), (7.00, 2.50), (12.20, 2.50)]),
 13: ("8DYwVTdzvn6wSFa6S_glq", "1yvHhY5i2KoB7ku3EJf-qt05kyZ8eIegk",
      [(0.60, 2.50), (5.45, 2.50), (9.60, 2.50), (12.30, 2.50)]),
 15: ("HEeIW78FoDki-0Jye1ork", "1XQhYbAbOMCws3pzCqRCRopvVi09Da5Uo",
      [(4.25, 2.50), (7.05, 2.50), (9.70, 2.50), (12.50, 2.50)]),
 20: ("XhiGFhEiqHTJRzVc7F84e", "1Ukpo2mmnsMaYXmaebWXMAqIGuH8q48nx",
      [(1.00, 2.50), (3.85, 2.50), (7.60, 2.50), (11.35, 2.50)]),
}

# прежние листы: номер -> (id, конец плашки)
OLD = {
 1:  ("1xQg1Zs9JmK_SXWJJ6N81QS2TN6L6En7I", 1.00),
 2:  ("1IG8uh6X8pFbll89OdLko4c8IsYxW0BNH", 2.70),
 3:  ("1sFxgfV-gxxwDpBGttTss_0lCXA_bWkmU", 2.20),
 4:  ("1xKSQHngEV8AXlIYbw8REYMrEtE5Hl7KM", 2.20),
 5:  ("1RahvyOH7XCzfOrgSD6xCqA8V0KVRy7gY", 0.75),
 6:  ("1SQVBwqXelxFiugw_FIWamiJrFeH29r4U", 0.75),
 8:  ("1j844GV49Tvr53w--GZwus8RhLvrhIxzt", 1.15),
 9:  ("1x5-KyYiLE76Sfjv3W7uQx0AvGkvhgz-e", 1.25),
 10: ("1L5YC98k_PScdnL9pd34sLAmtHZ3Q1CDD", 1.15),
 11: ("1oGcKLNOpGij9XxplNkl6BIrCHYwdqVTa", 0.75),
 12: ("1JBsetIB8E3YIEDBbnzO_ddRc6Jcm5hL_", 1.15),
 13: ("1lFequNcvZ-THJ1V8zLIUiGRuVeY5CIWp", 1.15),
 14: ("1cHRwTpuZ6uKTFQ0PXrEu85yiSamt55gY", 0.75),
 15: ("1MRjdKoagVmHxjowN8qWub71jB3YwVHA8", 1.15),
 16: ("1lFl2xpK3TLthrNQ9KYPrmAvfD4UCcD7t", 1.15),
 17: ("1MMACeM4Qd3botfvAwZLHTEVIuKoFG9mI", 1.15),
 18: ("1tsRP8_zUsuGBLJ_03TZx4WJy0gdzbh7x", 1.15),
 19: ("1BTidkt4h9kC_LwXck54JpJd2HWoIZxBH", 0.75),
 20: ("189A4WWTn7-bAxvCsvefrvnZ6feysfbID", 0.75),
 21: ("1UAYNvuc5c409XKARI4E4mFXzTBRkKEz3", 1.25),
 22: ("1xgl60UaJrYBI83o-9TyTFOnni1NiFx2d", 0.95),
 23: ("1ZbztiB7TkkQgZq7yY7apCW7A6n5Bvm1w", 3.50),
 24: ("1EG-HZjDyfMhvmCXIHeD7OuaVehkjazpd", 2.70),
 25: ("1yzkIByu1lOdGE7u4cM7sQ-srdL8QCdLH", 0.90),
}

# --- раскадровка клипа: 100 планов ---
# ("n", лист, номер плана) — новый лист;  ("o", лист, номер плана) — прежний лист
PLAN_TABLE = (
    # 0:00–1:10 — сразу грибы, утро и свет
    [("n", 1, 1), ("n", 1, 2), ("n", 1, 3), ("n", 1, 4)] +
    [("o", 5, k) for k in (1, 2, 3, 4)] +
    [("o", 3, k) for k in (1, 2, 3, 4)] +
    [("o", 12, k) for k in (1, 2, 3, 4)] +
    [("o", 14, k) for k in (1, 2, 3, 4)] +
    [("n", 6, k) for k in (1, 2, 3, 4)] +
    [("n", 7, k) for k in (1, 2, 3, 4)] +
    # 1:10–1:30 — проигрыш 1, девушка играет молча
    [("n", 8, 1), ("n", 8, 2), ("n", 8, 3),
     ("o", 1, 1), ("o", 13, 3), ("o", 6, 4), ("o", 18, 1), ("o", 23, 4)] +
    # 1:30–2:00 — тревога и ноги грибника
    [("o", 10, 1), ("o", 10, 2), ("o", 10, 4), ("o", 11, 1)] +
    [("n", 11, 1), ("n", 11, 2), ("n", 11, 3), ("n", 11, 4)] +
    [("o", 11, 2), ("o", 10, 3), ("o", 9, 3), ("o", 9, 4)] +
    # 2:00–2:30 — ветер, свет
    [("n", 13, k) for k in (1, 2, 3, 4)] +
    [("n", 15, k) for k in (1, 2, 3, 4)] +
    [("o", 21, 1), ("o", 16, 2), ("o", 8, 3)] +
    # 2:30–2:50 — большое соло, девушка
    [("o", 1, 2), ("o", 4, 1), ("o", 4, 2), ("o", 15, 1),
     ("o", 15, 2), ("o", 17, 4), ("o", 19, 2), ("o", 19, 3)] +
    # 2:50–3:00 — лес и грибница
    [("o", 22, 1), ("o", 17, 2), ("o", 20, 4), ("o", 24, 1), ("o", 25, 3)] +
    # 3:00–3:10 — девушка, конец соло
    [("o", 20, 1), ("o", 21, 4), ("o", 22, 2), ("o", 24, 2), ("o", 25, 1)] +
    # 3:10–3:50 — сумерки, живность, грибница
    [("n", 20, k) for k in (1, 2, 3, 4)] +
    [("o", 21, 2), ("o", 9, 1), ("o", 2, 3), ("o", 23, 1), ("o", 23, 3),
     ("o", 8, 2), ("o", 9, 2), ("o", 18, 3), ("o", 19, 1), ("o", 25, 4)] +
    # 3:50–4:09 — финал
    [("o", 16, 1), ("o", 22, 3), ("o", 24, 3), ("o", 25, 2), ("o", 20, 2),
     ("o", 24, 4), ("o", 2, 4), ("o", 23, 2), ("o", 21, 3)]
)


def sh(cmd, timeout=900):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]}: {(r.stderr or '')[-400:]}")
    return r


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def dl(fid, path):
    if os.path.exists(path) and os.path.getsize(path) > 300000:
        return path
    for _ in range(3):
        r = subprocess.run(["gdown", fid, "-O", path], capture_output=True, text=True)
        if os.path.exists(path) and os.path.getsize(path) > 300000:
            return path
        time.sleep(3)
    raise RuntimeError(f"не скачался {fid}")


def fit_filter(stretch):
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    if stretch:
        vf = f"setpts=(PTS-STARTPTS)*{stretch:.5f}," + vf
    return vf + f",fps={FPS},format=yuv420p"


def make_seg(src, start, take, out, stretch=None):
    vf = fit_filter(stretch)
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, start):.3f}", "-i", src,
        "-an", "-t", f"{take:.3f}", "-vf", vf, "-r", str(FPS),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "15", "-pix_fmt", "yuv420p",
        "-t", f"{PLAN:.3f}", out])


def main():
    os.makedirs(SEG, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUTDIR, exist_ok=True)

    print("песня...", flush=True)
    dl(SONG_ID, SONG)

    files = {}
    for k, (name, fid, _plans) in NEW.items():
        files[("n", k)] = dl(fid, f"{WORK}/new_{k:02d}.mp4")
    for k, (fid, _plate) in OLD.items():
        files[("o", k)] = dl(fid, f"{WORK}/old_{k:02d}.mp4")

    seen = set()
    segs = []
    for i, (kind, sheet, plan) in enumerate(PLAN_TABLE):
        key = (kind, sheet, plan)
        if key in seen:
            raise SystemExit(f"план повторяется: {key}")
        seen.add(key)
        src = files[(kind, sheet)]
        out = f"{SEG}/{i:03d}.mp4"
        if kind == "n":
            start, take = NEW[sheet][2][plan - 1]
            stretch = (PLAN / take) if take < PLAN - 0.02 else None
            make_seg(src, start, take, out, stretch)
        else:
            plate = OLD[sheet][1]
            span = (15.0 - plate) / 4.0
            start = plate + (plan - 1) * span + 0.06
            take = min(PLAN, span - 0.10)
            stretch = (PLAN / take) if take < PLAN - 0.02 else None
            make_seg(src, start, take, out, stretch)
        segs.append(out)
        if i % 10 == 0:
            print(f"план {i:03d} · {kind}{sheet}-{plan}", flush=True)

    lst = f"{SEG}/list.txt"
    open(lst, "w").write("".join(f"file '{p}'\n" for p in segs))
    video = f"{WORK}/video.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
        "-c", "copy", video])

    song_len = dur(SONG)
    total = min(dur(video), song_len)
    print("видео", round(dur(video), 2), "песня", round(song_len, 2), flush=True)

    out = f"{OUTDIR}/КЛИП_Грибы_1080p_новый.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", SONG,
        "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
        "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-af", f"afade=t=out:st={total-2.0:.2f}:d=2.0",
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
        "-t", f"{total:.2f}", "-movflags", "+faststart", out])
    print("готово:", out, round(os.path.getsize(out) / 1e6, 1), "МБ", flush=True)

    # лёгкая версия под Drive: до 99 МБ
    light = f"{OUTDIR}/КЛИП_Грибы_1080p_новый_диск.mp4"
    for crf in (26, 28, 30, 33):
        sh(["ffmpeg", "-v", "error", "-y", "-i", out, "-c:v", "libx264",
            "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", light])
        mb = os.path.getsize(light) / 1e6
        print(f"диск crf{crf}: {mb:.1f} МБ", flush=True)
        if mb < 95:
            break
    shutil.copy(light, f"{WORK}/disk.mp4")

    ws = os.environ.get("GITHUB_WORKSPACE")
    if ws:
        d = f"{ws}/dist/clip"
        os.makedirs(d, exist_ok=True)
        shutil.copy(light, f"{d}/КЛИП_Грибы_1080p_новый.mp4")
        print("в dist/clip:", round(os.path.getsize(f'{d}/КЛИП_Грибы_1080p_новый.mp4') / 1e6, 1), "МБ")


if __name__ == "__main__":
    main()
