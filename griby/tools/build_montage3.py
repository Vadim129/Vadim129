# -*- coding: utf-8 -*-
"""Клип «А представь, мы станем грибами» — сборка строго по плану сценария (25 листов × 10 с).

Главное отличие от прежних сборок:
  • порядок = порядок сценария (лист 01 → 25), никаких перескоков туда-обратно;
  • внутри листа берём НЕПРЕРЫВНЫЙ кусок 5 секунд (два плана подряд из одного видео),
    а не нарезку из разных мест: склейка только на границе листа, всего 50 склеек на 4 минуты;
  • девушка — только там, где в песне проигрыш (карта голоса): листы 8–9, 16–19, 24–25
    и по краям 10, 15, 20, 23; держится целыми блоками, без «мельканий»;
  • сюжет по сценарию: утро с грибами → тучи и первые капли → ливень по шляпкам →
    грибница и импульс → солнце и радость → приём → проигрыш (она) → тревога →
    сапоги грибника → красная шляпка на виду → облегчение → солнце → проигрыш (она) →
    сумерки и светляки → грибница → финал (она).

Запуск: python3 griby/tools/build_montage3.py
ENV: OUTDIR (/tmp/out), GITHUB_WORKSPACE — тогда кладём в dist/clip.
"""
import os, subprocess, shutil, time

WORK = "/tmp/mont3"
SEGDIR = f"{WORK}/seg"
OUTDIR = os.environ.get("OUTDIR", "/tmp/out")
SONG_ID = "1yGs88oWAw6TP-EdskGqH41Sjc2m0M309"
SONG = f"{WORK}/song.mp3"
FPS = 24
W, H = 1920, 1080
DUR = 249.48
PLAN_LEN = 5.0          # непрерывный кусок внутри листа

NEW = {
 1:  "1vmOTcrK6H16nCAyayF0OtL4JAOyWLra1",
 6:  "1Nb4rF_Clj3zjqDnwOio4Ui-MwNKwlhcJ",
 7:  "1sgwLUHPEz7pIi2yskRSCNetmlce0iDab",
 8:  "1OiAV92A8sxCKSOPYN1d5EL6lwTaL7dnZ",
 11: "1P07mVelnwDaiT1wHeMvdqG9L015f7opF",
 13: "1yvHhY5i2KoB7ku3EJf-qt05kyZ8eIegk",
 15: "1XQhYbAbOMCws3pzCqRCRopvVi09Da5Uo",
 20: "1Ukpo2mmnsMaYXmaebWXMAqIGuH8q48nx",
}
# начало каждого плана нового видео (0.7/3.1/7.25/11.2 и т. п. — проверено по кадрам)
NEW_PLANS = {
 1:  [0.70, 3.10, 7.25, 11.20],
 6:  [0.90, 4.20, 8.55, 13.45],
 7:  [0.60, 3.50, 6.50, 10.00],
 8:  [2.20, 2.20, 6.85, 10.55],
 11: [0.70, 3.60, 7.00, 12.20],
 13: [0.60, 5.45, 9.60, 12.30],
 15: [4.25, 7.05, 9.70, 12.50],
 20: [1.00, 3.85, 7.60, 11.35],
}
# внутренние склейки самого видео — через них кусок не тянем
NEW_CUTS = {
 1: [3.0, 7.12, 11.12], 6: [4.12, 8.42, 13.29], 7: [3.42, 6.42, 9.92],
 8: [2.12, 6.71, 7.67, 10.46, 11.33], 11: [6.46, 11.92], 13: [5.33, 7.21],
 15: [4.17, 6.96], 20: [],
}

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

# ---- план по листам сценария: (источник, старт в исходнике, длина) ----
# 25 листов × 10 с. Внутри листа — один-два непрерывных куска, склейка только между листами.
SHOTS = [
    # 01 — старт с грибов: поляна, мухомор у берёзы, белый у бревна, солнце
    (("n", 1), 7.20, 3.9), (("n", 1), 3.00, 4.0), (("n", 1), 11.20, 2.1),
    # 02 — небо затягивает, первые капли
    (("o", 2), 2.80, 5.0), (("o", 2), 8.75, 5.0),
    # 03 — ливень по шляпкам: крупно мухомор, крупно белый, вода стекает
    (("o", 3), 2.25, 5.0), (("o", 10), 1.35, 5.0),
    # 04 — разрез земли: грибница, тёплый импульс от мухомора к белому
    (("o", 12), 1.25, 5.0), (("o", 3), 7.60, 5.0),
    # 05 — солнце пробилось: луч на шляпку, росинки
    (("o", 5), 0.90, 5.0), (("n", 15), 7.05, 5.0),
    # 06 — восторг мухомора, поток сигнала по нитям
    (("n", 6), 0.90, 3.2), (("n", 6), 4.20, 4.2), (("n", 6), 8.50, 2.6),
    # 07 — приём: белый гриб отвечает
    (("n", 7), 3.50, 2.9), (("n", 7), 6.50, 3.4), (("o", 5), 5.00, 3.7),
    # 08 — проигрыш: играет соло на крыше
    (("o", 1), 1.10, 5.0), (("o", 1), 9.40, 5.0),
    # 09 — проигрыш: руки на струнах, лицо
    (("n", 8), 2.15, 4.5), (("n", 8), 7.70, 2.7), (("o", 22), 10.10, 2.8),
    # 10 — конец соло → земля дрожит
    (("o", 1), 10.05, 2.5), (("o", 12), 10.00, 2.5), (("o", 12), 5.20, 5.0),
    # 11 — ноги грибника: чёрные сапоги входят в мох
    (("n", 11), 0.65, 4.8), (("n", 11), 6.50, 5.2),
    # 12 — испуг: сапог рядом с красной шляпкой
    (("o", 10), 10.90, 5.0), (("o", 11), 0.90, 5.0),
    # 13 — красная шляпка на виду у сапога
    (("o", 10), 12.40, 4.0), (("o", 6), 5.00, 3.0), (("o", 13), 1.25, 3.0),
    # 14 — сапог уходит, облегчение
    (("o", 14), 0.90, 5.0), (("o", 5), 10.20, 5.0),
    # 15 — припев 3 → в конце появляется она
    (("o", 22), 1.05, 5.5), (("o", 3), 10.30, 3.0), (("o", 16), 1.25, 1.5),
    # 16 — большое соло: играет стоя
    (("o", 21), 5.20, 5.0), (("o", 21), 10.10, 5.0),
    # 17 — крупно гитара и руки
    (("o", 18), 6.30, 5.0), (("o", 23), 5.20, 5.0),
    # 18 — играет у окна
    (("o", 7), 1.25, 5.0), (("o", 20), 0.90, 5.0),
    # 19 — последние аккорды, закат
    (("o", 21), 3.80, 5.0), (("o", 14), 5.00, 5.0),
    # 20 — конец соло → сумерки
    (("o", 15), 1.25, 2.5), (("n", 20), 1.00, 4.6), (("n", 20), 7.60, 3.4),
    # 21 — тихий бридж: два гриба рядом
    (("o", 22), 3.20, 5.0), (("n", 7), 9.95, 5.0),
    # 22 — грибница под землёй, общий пульс
    (("o", 17), 5.00, 3.5), (("o", 12), 9.00, 3.5), (("n", 20), 3.85, 3.0),
    # 23 — финальный припев: два гриба на солнце
    (("o", 22), 2.20, 5.0), (("o", 6), 0.90, 2.5),
    # 24 — она играет, outro
    (("o", 19), 5.00, 5.0), (("o", 1), 5.05, 5.0),
    # 25 — последний кадр: город в закате
    (("n", 8), 11.35, 4.5), (("o", 1), 2.60, 5.02),
]


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


def tail_fix():
    """Последний кусок добирает остаток, чтобы сумма была ровно как песня."""
    total = sum(d for _k, _s, d in SHOTS)
    last = SHOTS[-1]
    SHOTS[-1] = (last[0], last[1], round(last[2] + (DUR - total), 3))


def check_plan():
    total = sum(d for _k, _s, d in SHOTS)
    if abs(total - DUR) > 0.08:
        raise SystemExit(f"длительность {total:.2f} ≠ песня {DUR}")
    if len({(k, round(s, 2)) for k, s, _d in SHOTS}) != len(SHOTS):
        raise SystemExit("повтор куска")
    for (kind, sheet), start, need in SHOTS:
        if kind == "n":
            for c in NEW_CUTS.get(sheet, []):
                if start < c < start + need - 0.05:
                    raise SystemExit(f"кусок n{sheet} {start}–{start+need} пересекает склейку {c}")
        else:
            if start < OLD[sheet][1] + 0.05:
                raise SystemExit(f"кусок o{sheet} начинается на плашке ({start})")


def make_seg(src, start, need, out):
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"fps={FPS},format=yuv420p")
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", src,
        "-an", "-t", f"{need:.3f}", "-vf", vf, "-r", str(FPS),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "15", "-pix_fmt", "yuv420p", out])


def main():
    tail_fix()
    check_plan()
    os.makedirs(SEGDIR, exist_ok=True)
    os.makedirs(OUTDIR, exist_ok=True)

    print(f"кусков {len(SHOTS)}, сумма {sum(d for _k, _s, d in SHOTS):.2f} с", flush=True)
    print("песня...", flush=True)
    dl(SONG_ID, SONG)

    files = {}
    for kind, sheet in {(k[0], k[1]) for k, _s, _d in SHOTS}:
        fid = NEW[sheet] if kind == "n" else OLD[sheet][0]
        files[(kind, sheet)] = dl(fid, f"{WORK}/{kind}{sheet:02d}.mp4")

    segs = []
    t = 0.0
    for i, ((kind, sheet), start, need) in enumerate(SHOTS):
        out = f"{SEGDIR}/{i:03d}.mp4"
        make_seg(files[(kind, sheet)], start, need, out)
        segs.append(out)
        t += need
        if i % 10 == 0 or kind == "o" and sheet in (1,):
            print(f"  {i:02d} · {kind}{sheet:02d} @ {start:5.2f} +{need:4.2f} → {t:6.2f}", flush=True)

    lst = f"{SEGDIR}/list.txt"
    open(lst, "w").write("".join(f"file '{p}'\n" for p in segs))
    video = f"{WORK}/video.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
        "-c", "copy", video])
    print("видео", round(dur(video), 2), "с", flush=True)

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


if __name__ == "__main__":
    main()
