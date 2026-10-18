#!/usr/bin/env python3
"""Разбор лога scdet: границы кадров."""
import sys, re, json, os
src = sys.argv[1]
cuts = []
last = None
with open(src, errors="ignore") as f:
    for line in f:
        m = re.search(r"lavfi.scd.time=([0-9.]+)", line)
        if m:
            t = round(float(m.group(1)), 3)
            if last is None or t - last > 0.15:
                cuts.append(t)
                last = t
        m2 = re.search(r"lavfi.scd.score=([0-9.]+)", line)
        if m2 and cuts:
            pass
with open(os.path.join(os.path.dirname(src), "cuts.json"), "w") as f:
    json.dump(cuts, f)
for i, t in enumerate(cuts):
    nxt = cuts[i + 1] if i + 1 < len(cuts) else None
    print(f"{t:8.2f}  {t/60:5.2f}м  {'+' + format(nxt-t, '.2f') + 'с' if nxt else ''}")
print(f"всего склеек: {len(cuts)}")
