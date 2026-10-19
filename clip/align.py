#!/usr/bin/env python3
"""Выравнивание текста песни по распознанным словам (Vosk).

На входе — слова с таймкодами из ASR (/tmp/asr_words.json) и канонический
текст. Для каждого прохода делается монотонное выравнивание (DP) слов
текста на распознанные слова; получаются тайминги каждого слова, а из них —
строк. Результат: clip/timing.json.
"""
import difflib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "clip")
ASR = "/tmp/asr_words.json"

# найденные по распознаванию границы проходов (сек)
PASSES = [(23.0, 96.0), (109.5, 183.0)]


def norm(w):
    w = w.lower().replace("ё", "е")
    w = re.sub(r"[^а-яa-z0-9]", "", w)
    return w


def sim(a, b):
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a.startswith(b) or b.startswith(a):
        return 0.92
    r = difflib.SequenceMatcher(None, a, b).ratio()
    if len(a) > 3 and len(b) > 3 and a[:3] == b[:3]:
        r = max(r, 0.78)
    return r


def load_lyrics():
    lines = []
    for raw in open(os.path.join(OUT, "lyrics.txt"), encoding="utf-8"):
        t = raw.strip()
        if not t or t.startswith("#TITLE|"):
            continue
        lines.append(t)
    return lines


def align(lyric_words, asr_words):
    """DP: минимизируем суммарную стоимость (несовпадение + пропуски)."""
    n, m = len(lyric_words), len(asr_words)
    INF = 1e9
    D = [[INF] * (m + 1) for _ in range(n + 1)]
    B = [[None] * (m + 1) for _ in range(n + 1)]
    D[0][0] = 0.0
    SKIP_A = 0.45        # лишнее слово в распознавании (вставка)
    SKIP_L = 0.95        # слово текста не распознано
    for i in range(n + 1):
        for j in range(m + 1):
            if D[i][j] >= INF:
                continue
            if i < n and j < m:
                c = 1.0 - sim(lyric_words[i], asr_words[j])
                v = D[i][j] + c * 1.6
                if v < D[i + 1][j + 1]:
                    D[i + 1][j + 1] = v
                    B[i + 1][j + 1] = ("m", i, j)
            if i < n:
                v = D[i][j] + SKIP_L
                if v < D[i + 1][j]:
                    D[i + 1][j] = v
                    B[i + 1][j] = ("l", i, j)
            if j < m:
                v = D[i][j] + SKIP_A
                if v < D[i][j + 1]:
                    D[i][j + 1] = v
                    B[i][j + 1] = ("a", i, j)
    # обратный проход
    i, j = n, m
    pairs = []
    while i or j:
        op, pi, pj = B[i][j]
        if op == "m":
            pairs.append((pi, pj))
            i, j = pi, pj
        elif op == "l":
            i = pi
        else:
            j = pj
    pairs.reverse()
    return pairs


def build_pass(lines, words, win):
    asr = [w for w in words if win[0] <= w["start"] <= win[1]]
    lyric = []
    index = []
    for li, line in enumerate(lines):
        for w in line.split():
            index.append((li, w))
            lyric.append(norm(w))
    pairs = align(lyric, [norm(w["word"]) for w in asr])
    # тайминги слов
    starts = [None] * len(lyric)
    ends = [None] * len(lyric)
    for li, ai in pairs:
        starts[li] = asr[ai]["start"]
        ends[li] = asr[ai]["end"]
    # интерполяция пропусков
    known = [k for k in range(len(lyric)) if starts[k] is not None]
    for k in range(len(lyric)):
        if starts[k] is not None:
            continue
        prev = max([x for x in known if x < k], default=None)
        nxt = min([x for x in known if x > k], default=None)
        if prev is None and nxt is None:
            starts[k] = ends[k] = win[0]
        elif prev is None:
            step = (starts[nxt] - win[0]) / (nxt - k + 1)
            starts[k] = win[0] + step * (k - 0 + 1) * 0 + step * (k + 1)
            ends[k] = starts[k] + 0.18
        elif nxt is None:
            starts[k] = ends[prev] + 0.12 * (k - prev)
            ends[k] = starts[k] + 0.18
        else:
            span = starts[nxt] - ends[prev]
            f = (k - prev) / (nxt - prev)
            starts[k] = ends[prev] + span * f * 0.9
            ends[k] = ends[prev] + span * (f + 0.1)
    # строки
    cues = []
    for li, line in enumerate(lines):
        idx = [k for k in range(len(lyric)) if index[k][0] == li]
        if not idx:
            continue
        ws = [{"w": line.split()[n], "t0": round(starts[k], 3),
               "t1": round(max(ends[k], starts[k] + 0.12), 3)}
              for n, k in enumerate(idx)]
        cues.append({"t0": ws[0]["t0"], "t1": ws[-1]["t1"],
                     "text": line, "words": ws})
    # подрежем концы строк
    for a, b in zip(cues, cues[1:]):
        if a["t1"] > b["t0"] - 0.02:
            a["t1"] = round(b["t0"] - 0.02, 3)
            a["words"][-1]["t1"] = a["t1"]
    matched = len(pairs) / len(lyric)
    return cues, matched


TAILS = {
    0: [("Пока журчит вода в фонтане с дельфином", 87.10, 90.16),
        ("Пока журчит вода в фонтане с дельфином", 90.21, 93.87),
        ("В фонтане с дельфином", 94.71, 96.10)],
    1: [("Пока журчит вода в фонтане с дельфином", 174.37, 180.34),
        ("В фонтане с дельфином", 180.48, 183.30),
        ("Йау, Сыктывкар Underground", 184.38, 186.40)],
}
INTRO = ("Komi Crime Underground · 2×2 Records", 2.50, 12.30)


def add_words(text, t0, t1):
    parts = text.split()
    weights = [max(1, sum(1 for ch in w if ch in "аеёиоуыэюяАЕЁИОУЫЭЮЯ")) for w in parts]
    total = sum(weights)
    out, t = [], t0
    for w, k in zip(parts, weights):
        d = (t1 - t0) * k / total
        out.append({"w": w, "t0": round(t, 3), "t1": round(t + d, 3)})
        t += d
    return out


def main():
    words = json.load(open(ASR, encoding="utf-8"))
    lines = load_lyrics()
    passes = []
    stats = []
    for k, win in enumerate(PASSES):
        cues, matched = build_pass(lines, words, win)
        # последняя строка в каждом проходе поётся несколько раз — берём точные
        # границы из распознавания, а не одну длинную строку
        cues = cues[:-1]
        for text, a, b in TAILS[k]:
            cues.append({"t0": a, "t1": b, "text": text,
                         "words": add_words(text, a, b)})
        passes.append(cues)
        stats.append((k, matched, cues[0]["t0"], cues[-1]["t1"]))
    data = {"intro": {"t0": INTRO[1], "t1": INTRO[2], "text": INTRO[0],
                      "words": add_words(INTRO[0], INTRO[1], INTRO[2])},
            "passes": passes}
    json.dump(data, open(os.path.join(OUT, "timing.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for k, m, a, b in stats:
        print(f"проход {k+1}: совпало {m*100:.0f}% слов, {a:.1f}–{b:.1f}, "
              f"строк {len(passes[k])}")
    print("всего строк:", sum(len(p) for p in passes))


if __name__ == "__main__":
    main()
