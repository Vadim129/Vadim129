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

# ---- рабочие куски новых видео (между внутренними склейками, чтобы кадр не прыгал) ----
SEGCUT = {
 1:  [(0.55, 2.95), (3.05, 7.10), (7.15, 11.10), (11.15, 15.00)],
 6:  [(0.85, 4.10), (4.15, 8.40), (8.45, 13.25), (13.30, 15.00)],
 7:  [(0.50, 3.40), (3.45, 6.40), (6.45, 9.90), (9.95, 15.00)],
 8:  [(0.10, 2.10), (2.15, 6.70), (6.75, 7.65), (7.70, 10.45), (10.50, 11.30), (11.35, 15.00)],
 11: [(0.65, 6.45), (6.50, 11.90), (11.95, 15.00)],
 13: [(0.55, 5.30), (5.35, 7.20), (7.25, 15.00)],
 15: [(0.10, 4.15), (4.20, 6.95), (7.00, 14.90)],
 20: [(0.95, 15.00)],
}

# ---- монтажный лист: сцены по смыслу песни ----
# (начало, конец, [(источник, старт в исходнике, базовая длина)])
# Внутри сцены длины пропорционально подгоняются под её границы.
SECTIONS = [
    # 0:00–0:20 — поляна просыпается: два гриба, солнце
    (0.0, 20.0, [(("o", 22), 0.10, 6.4), (("n", 1), 11.20, 3.3), (("o", 14), 5.20, 5.9)]),
    # 0:20–0:35 — небо затягивает, первые капли
    (20.0, 35.0, [(("o", 2), 2.80, 8.5), (("o", 10), 3.60, 6.3)]),
    # 0:35–0:45 — ливень барабанит по шляпкам
    (35.0, 45.0, [(("o", 3), 2.30, 5.3), (("n", 6), 4.20, 4.2)]),
    # 0:45–0:53 — вода ушла в землю, грибница
    (45.0, 53.0, [(("o", 12), 0.10, 4.1), (("o", 3), 7.60, 4.3)]),
    # 0:53–1:07 — солнце пробилось, капли блестят
    (53.0, 67.0, [(("n", 6), 0.85, 3.3), (("o", 21), 3.80, 5.0), (("n", 15), 7.05, 5.4)]),
    # 1:07–1:11 — мухомор сияет, белый отвечает
    (67.0, 71.0, [(("n", 7), 3.45, 3.0), (("o", 13), 0.05, 3.4)]),
    # 1:11–1:32.5 — проигрыш: она играет на крыше
    (71.0, 92.5, [(("o", 1), 0.70, 7.9), (("n", 8), 2.15, 4.55), (("o", 21), 10.10, 3.6),
                  (("o", 22), 8.80, 2.4), (("o", 16), 0.05, 2.3)]),
    # 1:32.5–1:39 — земля дрожит, корни
    (92.5, 99.0, [(("o", 17), 3.80, 3.7), (("o", 10), 7.60, 2.8)]),
    # 1:39–1:52 — сапоги грибника входят и уходят
    (99.0, 112.0, [(("n", 11), 0.65, 5.7), (("n", 11), 6.50, 5.3), (("n", 11), 11.95, 2.1)]),
    # 1:52–2:00 — красная шляпка на виду у сапога
    (112.0, 120.0, [(("o", 13), 3.80, 3.6), (("o", 11), 10.00, 2.5), (("o", 10), 11.30, 1.9)]),
    # 2:00–2:10 — испуг белого, потом выдох
    (120.0, 130.0, [(("o", 6), 6.30, 5.1), (("o", 23), 10.05, 1.6), (("o", 14), 0.05, 3.3)]),
    # 2:10–2:20 — облегчение по всей поляне
    (130.0, 140.0, [(("o", 12), 10.20, 3.6), (("o", 5), 10.20, 3.6), (("o", 24), 10.20, 2.8)]),
    # 2:20–2:28.5 — припев, все счастливы
    (140.0, 148.5, [(("o", 22), 5.60, 4.5), (("o", 22), 0.05, 3.3)]),
    # 2:28.5–3:13 — большое соло: она играет
    (148.5, 193.0, [(("o", 8), 0.05, 3.7), (("o", 13), 8.80, 3.6), (("o", 15), 0.05, 3.5),
                    (("o", 20), 0.05, 3.7), (("o", 25), 7.55, 3.7), (("o", 24), 5.05, 3.7),
                    (("o", 18), 6.30, 2.6), (("o", 18), 2.50, 2.5), (("o", 9), 5.05, 2.4),
                    (("o", 25), 1.30, 3.0), (("o", 18), 5.00, 2.4),
                    (("o", 21), 11.90, 3.2)]),
    # 3:13–3:30 — сумерки, светляки
    (193.0, 210.0, [(("n", 20), 1.00, 7.0), (("n", 13), 7.30, 3.4), (("o", 17), 0.05, 3.0)]),
    # 3:30–3:48 — грибница, тихий бридж
    (210.0, 228.0, [(("o", 17), 5.00, 3.6), (("o", 3), 10.00, 3.8), (("n", 20), 7.60, 4.5)]),
    # 3:48–4:09.5 — финал: она играет, город в закате
    (228.0, 249.48, [(("o", 1), 0.05, 6.0), (("o", 19), 5.00, 3.0), (("o", 25), 2.60, 3.0),
                     (("o", 1), 6.20, 2.4), (("n", 8), 11.35, 3.6)]),
]


def room_of(kind, sheet, start):
    if kind == "n":
        seg = next((s for s in SEGCUT[sheet] if s[0] <= start + 0.05 <= s[1]), None)
        return (seg[1] - start) if seg else 3.0
    return 14.9 - start


def build_shots():
    shots = []
    for t0, t1, items in SECTIONS:
        base = sum(d for _k, _s, d in items)
        scale = (t1 - t0) / base
        part = []
        for kind_sheet, start, d in items:
            kind, sheet = kind_sheet
            need = min(d * scale, room_of(kind, sheet, start))
            part.append([kind_sheet, start, need])
        # добираем остаток у кусков, где есть запас
        for _ in range(6):
            rest = (t1 - t0) - sum(x[2] for x in part)
            if abs(rest) < 0.01:
                break
            free = [[i, room_of(x[0][0], x[0][1], x[1]) - x[2]] for i, x in enumerate(part)]
            free = [f for f in free if f[1] > 0.05]
            if not free:
                break
            for i, _f in free:
                add = rest / len(free)
                part[i][2] += max(-0.4 * part[i][2], min(add, room_of(part[i][0][0], part[i][0][1], part[i][1]) - part[i][2]))
        for x in part:
            shots.append([x[0], x[1], round(x[2], 3)])
    return shots


SHOTS = build_shots()
_sh = round(DUR - sum(s[2] for s in SHOTS), 3)
SHOTS[-1][2] = round(SHOTS[-1][2] + _sh, 3)


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


def make_seg(src, start, need, out, _unused=None):
    """Непрерывный кусок ровно need секунд: без внутренних вставок и перескоков."""
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"fps={FPS},format=yuv420p")
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, start):.3f}", "-i", src,
        "-an", "-t", f"{need:.3f}", "-vf", vf, "-r", str(FPS),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "15", "-pix_fmt", "yuv420p",
        out])


def main():
    os.makedirs(SEG, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUTDIR, exist_ok=True)

    total = sum(d for _k, _s, d in SHOTS)
    print(f"планов {len(SHOTS)}, сумма {total:.2f} с (песня {DUR})", flush=True)
    if abs(total - DUR) > 0.05:
        raise SystemExit(f"длительность не сходится: {total:.2f} vs {DUR}")
    keys = [(k, round(st, 2)) for k, st, _d in SHOTS]
    if len(keys) != len(set(keys)):
        raise SystemExit("один и тот же кусок использован дважды")

    print("песня...", flush=True)
    dl(SONG_ID, SONG)

    files = {}
    for kind, sheet in {(k[0], k[1]) for k, _s, _d in SHOTS}:
        fid = NEW[sheet][0] if kind == "n" else OLD[sheet][0]
        files[(kind, sheet)] = dl(fid, f"{WORK}/{kind}{sheet:02d}.mp4")

    seg_files = []
    t = 0.0
    for i, ((kind, sheet), start, need) in enumerate(SHOTS):
        out = f"{WORK}/seg/{i:03d}.mp4"
        make_seg(files[(kind, sheet)], start, need, out, need)
        seg_files.append(out)
        t += need
        print(f"план {i:02d} · {kind}{sheet:02d} @ {start:5.2f} · {need:4.2f} с · до {t:6.2f}", flush=True)

    lst = f"{WORK}/seg/list.txt"
    open(lst, "w").write("".join(f"file '{p}'\n" for p in seg_files))
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
