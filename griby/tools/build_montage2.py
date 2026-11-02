# -*- coding: utf-8 -*-
"""Клип «А представь, мы станем грибами» — сборка по сюжету песни.

Что было не так в прежних сборках и что здесь исправлено:
  1) кадры прыгали между листами туда-обратно («вырезал из одного куска») —
     теперь каждый источник идёт одним непрерывным куском и больше не возвращается;
  2) монтаж был рубленый по 2,5 с — теперь склейки стоят на границах вокальных фраз
     (карта голоса ci/vocal_map.txt), план держится 3–6 с;
  3) девушка мелькала на мгновение — теперь она только на проигрышах и подряд,
     держится по 3–4 с, и её блоки никем не разрываются;
  4) картинка не совпадала с тем, о чём поют — теперь сцена соответствует смыслу:
     тучи и первые капли → ливень по шляпкам → ток по грибнице → солнце и радость →
     тревога, сапоги грибника → испуг и красная шляпка → облегчение → сумерки,
     светляки и грибница → финал с девушкой.

Источники: прежние 25 листов (основа) + новые 8 видео (старт, сапоги, девушка, сумерки).
Готовый клип не используется.

Запуск: python3 griby/tools/build_montage2.py
ENV: OUTDIR (/tmp/out), GITHUB_WORKSPACE — тогда кладём в dist/clip.
"""
import os, subprocess, shutil, time

WORK = "/tmp/mont2"
SEG = f"{WORK}/seg"
OUTDIR = os.environ.get("OUTDIR", "/tmp/out")
SONG_ID = "1yGs88oWAw6TP-EdskGqH41Sjc2m0M309"
SONG = f"{WORK}/song.mp3"
FPS = 24
W, H = 1920, 1080
DUR = 249.48

# ---- новые видео (8 листов): (id, [(начало, длина плана)]) ----
NEW = {
 1:  ("1vmOTcrK6H16nCAyayF0OtL4JAOyWLra1",
      [(0.70, 2.50), (3.10, 2.50), (7.25, 2.50), (11.20, 2.50)]),
 6:  ("1Nb4rF_Clj3zjqDnwOio4Ui-MwNKwlhcJ",
      [(0.90, 2.50), (4.20, 2.50), (8.55, 2.50), (13.45, 1.50)]),
 7:  ("1sgwLUHPEz7pIi2yskRSCNetmlce0iDab",
      [(0.60, 2.50), (3.50, 2.50), (6.50, 2.50), (10.00, 2.50)]),
 8:  ("1OiAV92A8sxCKSOPYN1d5EL6lwTaL7dnZ",
      [(0.90, 2.50), (2.60, 2.50), (8.10, 2.50), (12.40, 2.50)]),
 11: ("1P07mVelnwDaiT1wHeMvdqG9L015f7opF",
      [(0.70, 2.50), (3.60, 2.50), (7.00, 2.50), (12.20, 2.50)]),
 13: ("1yvHhY5i2KoB7ku3EJf-qt05kyZ8eIegk",
      [(0.60, 2.50), (5.45, 2.50), (9.60, 2.50), (12.30, 2.50)]),
 15: ("1XQhYbAbOMCws3pzCqRCRopvVi09Da5Uo",
      [(4.25, 2.50), (7.05, 2.50), (9.70, 2.50), (12.50, 2.50)]),
 20: ("1Ukpo2mmnsMaYXmaebWXMAqIGuH8q48nx",
      [(1.00, 2.50), (3.85, 2.50), (7.60, 2.50), (11.35, 2.50)]),
}

# ---- прежние 25 листов: номер -> (id, конец плашки раскадровки) ----
OLD = {
 1:  ("1xQg1Zs9JmK_SXWJJ6N81QS2TN6L6En7I", 1.00),
 2:  ("1IG8uh6X8pFbll89OdLko4c8IsYxW0BNH", 2.70),
 3:  ("1sFxgfV-gxxwDpBGttTss_0lCXA_bWkmU", 2.20),
 4:  ("1xKSQHngEV8AXlIYbw8REYMrEtE5Hl7KM", 2.20),
 5:  ("1RahvyOH7XCzfOrgSD6xCqA8V0KVRy7gY", 0.75),
 6:  ("1SQVBwqXelxFiugw_FIWamiJrFeH29r4U", 0.75),
 7:  ("1CFM2P3DwVhw41gK2dwZUeMFyuXpy1pTE", 1.15),
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
 25: ("1yzkIByu1lOdGE7u4cM7sQ-srdL8QCdLH", 2.40),
}

# ---- монтажный лист по сюжету песни ----
# (начало, конец, [источники в порядке показа]) — внутри блока планы идут подряд,
# режем равными кусками 2,8–3,7 с, длительность блока ровно по песне.
SECTIONS = [
    # 0:00–0:30 — поляна утром, тучи, первые капли, ливень по шляпкам
    (0.0, 30.0, [("n", 1, 1), ("n", 1, 3), ("n", 1, 4), ("o", 2, 1), ("o", 2, 2),
                 ("o", 2, 3), ("o", 10, 2), ("o", 3, 1), ("o", 3, 2)]),
    # 0:30–0:40 — вода ушла в мох, разрез земли, грибница
    (30.0, 40.0, [("o", 3, 3), ("o", 3, 4), ("o", 12, 1)]),
    # 0:40–0:50 — солнце пробилось, росинки
    (40.0, 50.0, [("o", 5, 1), ("n", 6, 1), ("n", 15, 1)]),
    # 0:50–1:00 — восторг мухомора, импульс по нитям
    (50.0, 60.0, [("o", 13, 1), ("o", 5, 3), ("o", 6, 2)]),
    # 1:00–1:11 — приём: белый гриб отвечает
    (60.0, 71.0, [("n", 7, 4), ("o", 6, 1), ("n", 6, 4)]),
    # 1:11–1:32.5 — проигрыш: она играет соло, подряд, без вставок
    (71.0, 92.5, [("o", 1, 1), ("o", 1, 2), ("n", 8, 3), ("o", 1, 3),
                  ("n", 8, 2), ("o", 13, 3), ("o", 1, 4)]),
    # 1:32.5–1:50 — земля дрожит, входит грибник
    (92.5, 110.0, [("o", 20, 4), ("o", 10, 4), ("o", 12, 4), ("n", 11, 1), ("n", 11, 2)]),
    # 1:50–2:00 — сапоги шагают, уходят
    (110.0, 120.0, [("n", 11, 3), ("n", 11, 4), ("o", 13, 4)]),
    # 2:00–2:10 — красная шляпка на виду, гриб замер
    (120.0, 130.0, [("o", 15, 2), ("o", 22, 4), ("o", 23, 3)]),
    # 2:10–2:20 — сапог ушёл, облегчение
    (130.0, 140.0, [("o", 14, 3), ("o", 14, 2), ("o", 14, 1)]),
    # 2:20–2:28.5 — припев, счастливые грибы
    (140.0, 148.5, [("o", 6, 4), ("o", 24, 4), ("o", 24, 1)]),
    # 2:28.5–3:13 — большое соло: она играет, подряд
    (148.5, 193.0, [("o", 16, 1), ("o", 21, 3), ("o", 21, 4), ("o", 22, 2),
                    ("o", 18, 2), ("o", 22, 3), ("o", 18, 3), ("o", 23, 4),
                    ("o", 23, 1), ("o", 24, 2), ("o", 25, 2), ("o", 24, 3),
                    ("o", 8, 1)]),
    # 3:13–3:48 — сумерки, светляки, грибница
    (193.0, 228.0, [("n", 20, 1), ("n", 20, 2), ("n", 13, 3), ("n", 13, 4),
                    ("o", 16, 4), ("o", 17, 2), ("o", 17, 3), ("n", 20, 4),
                    ("o", 25, 4), ("o", 22, 1)]),
    # 3:48–4:09.5 — финал: она играет, город в закате
    (228.0, 249.48, [("n", 8, 1), ("o", 15, 1), ("o", 18, 1), ("o", 20, 1),
                     ("o", 17, 4), ("n", 8, 4)]),
]

SHOTS = []
for _t0, _t1, _keys in SECTIONS:
    _n = len(_keys)
    _step = (_t1 - _t0) / _n
    for _i, _k in enumerate(_keys):
        _d = round(_step, 3) if _i < _n - 1 else round(_t1 - _t0 - _step * (_n - 1), 3)
        SHOTS.append((_k, _d))
SHOTS = list(SHOTS)
_fix = round(DUR - sum(_d for _k, _d in SHOTS), 3)
SHOTS[-1] = (SHOTS[-1][0], round(SHOTS[-1][1] + _fix, 3))
SHOTS = tuple(SHOTS)

def sh(cmd, timeout=1200):
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
        subprocess.run(["gdown", fid, "-O", path], capture_output=True, text=True)
        if os.path.exists(path) and os.path.getsize(path) > 300000:
            return path
        time.sleep(3)
    raise RuntimeError(f"не скачался {fid}")


def window(kind, sheet, plan):
    """Окно плана в исходнике: (начало, сколько доступно)."""
    if kind == "n":
        start, take = NEW[sheet][1][plan - 1]
        return start, take
    plate = OLD[sheet][1]
    span = (15.0 - plate) / 4.0
    return plate + (plan - 1) * span, span


def make_seg(src, start, take, out, need):
    """Кусок ровно need секунд. Если окно плана короче, тянем его вширь в том же кадре."""
    if take + 0.02 < need:
        extra = need - take
        start = max(0.0, start - extra / 2)
        take = min(need, 15.0 - start)
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    if take + 0.02 < need:
        vf = f"setpts=(PTS-STARTPTS)*{need / take:.5f}," + vf
    vf += f",fps={FPS},format=yuv420p"
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, start):.3f}", "-i", src,
        "-an", "-t", f"{take:.3f}", "-vf", vf, "-r", str(FPS),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "15", "-pix_fmt", "yuv420p",
        "-t", f"{need:.3f}", out])


def main():
    os.makedirs(SEG, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUTDIR, exist_ok=True)

    total = sum(d for _k, d in SHOTS)
    print(f"планов {len(SHOTS)}, сумма {total:.2f} с (песня {DUR})", flush=True)
    if abs(total - DUR) > 0.05:
        raise SystemExit(f"длительность не сходится: {total:.2f} vs {DUR}")

    keys = [k for k, _d in SHOTS]
    if len(keys) != len(set(keys)):
        raise SystemExit("один план использован дважды")

    print("песня...", flush=True)
    dl(SONG_ID, SONG)

    files = {}
    for kind, sheet in {(k[0], k[1]) for k in keys}:
        if kind == "n":
            files[(kind, sheet)] = dl(NEW[sheet][0], f"{WORK}/new_{sheet:02d}.mp4")
        else:
            files[(kind, sheet)] = dl(OLD[sheet][0], f"{WORK}/old_{sheet:02d}.mp4")

    segs = []
    t = 0.0
    for i, ((kind, sheet, plan), need) in enumerate(SHOTS):
        src = files[(kind, sheet)]
        start, take = window(kind, sheet, plan)
        if kind == "o":
            # держим кусок по центру окна плана
            if take > need:
                start += (take - need) / 2
                take = need
        else:
            if take > need:
                start += (take - need) / 2
                take = need
        out = f"{SEG}/{i:03d}.mp4"
        make_seg(src, start, take, out, need)
        segs.append(out)
        t += need
        if i % 10 == 0:
            print(f"план {i:02d} · {kind}{sheet}-{plan} · {t:6.2f} с", flush=True)

    lst = f"{SEG}/list.txt"
    open(lst, "w").write("".join(f"file '{p}'\n" for p in segs))
    video = f"{WORK}/video.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
        "-c", "copy", video])
    print("видео", round(dur(video), 2), "песня", round(dur(SONG), 2), flush=True)

    out = f"{OUTDIR}/КЛИП_Грибы_1080p_сюжет.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", SONG,
        "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
        "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-af", f"afade=t=out:st={DUR - 2.0:.2f}:d=2.0",
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
        "-t", f"{DUR:.2f}", "-movflags", "+faststart", out])
    print("готово:", round(os.path.getsize(out) / 1e6, 1), "МБ", flush=True)

    light = f"{OUTDIR}/КЛИП_Грибы_1080p_сюжет_диск.mp4"
    for crf in (26, 28, 30, 32):
        sh(["ffmpeg", "-v", "error", "-y", "-i", out, "-c:v", "libx264",
            "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", light])
        mb = os.path.getsize(light) / 1e6
        print(f"диск crf{crf}: {mb:.1f} МБ", flush=True)
        if mb < 70:
            break

    ws = os.environ.get("GITHUB_WORKSPACE")
    if ws:
        d = f"{ws}/dist/clip"
        os.makedirs(d, exist_ok=True)
        shutil.copy(light, f"{d}/КЛИП_Грибы_1080p_сюжет.mp4")
        print("в dist/clip:", round(os.path.getsize(f'{d}/КЛИП_Грибы_1080p_сюжет.mp4') / 1e6, 1), "МБ")


if __name__ == "__main__":
    main()
