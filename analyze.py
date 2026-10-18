# Per-heading stats: for each mark, use the samples from 0.5 s to 5.5 s after it
import csv, statistics as s, sys
rows = [(float(r["t"]), int(r["angle_cdeg"])) for r in csv.DictReader(open("data/rotation.csv")) if r["angle_cdeg"]]
marks = [(float(t), h) for t, h in csv.reader(open("data/marks.csv"))]
base = None
for t0, h in marks:
    w = [c for t, c in rows if t0 + 0.5 <= t <= t0 + 5.5]
    if not w: print(f"{h:>5}°  (no samples yet)"); continue
    m = s.mean(w) / 100
    base = m if base is None else base
    print(f"{h:>5}°  n={len(w):3}  mean={m:.3f}°  sd={s.pstdev(w)/100:.3f}°  Δ vs first={m-base:+.3f}°")
