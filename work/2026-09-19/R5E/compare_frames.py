#!/usr/bin/env python3
"""Side-by-side per-pass element counts of two run_bundle.mjs light traces (frames.md from frames.py).
usage: compare_frames.py <ref-run-dir> <cand-run-dir>"""
import re, sys, collections
def load(run):
    rows = []
    for line in open(f"{run}/frames.md"):
        m = re.match(r"\| (\d+) \| (\d+) \| (\d+) \| ([^|]*)\| ([^|]*)\| ([^|]*)\| ([^|]*)\|", line)
        if not m: continue
        passes = [(int(a), int(b)) for a, b in re.findall(r"(\d+):(\d+)", m.group(4))]
        layouts = [(a, int(b)) for a, b in re.findall(r"(\d+|\?):(\d+)", m.group(5))]
        tok = m.group(7).strip()
        rows.append((int(m.group(1)), int(m.group(3)), passes, layouts, None if tok == "None" else int(tok)))
    return rows
ref, cand = load(sys.argv[1]), load(sys.argv[2])
def summary(rows, label):
    per = collections.defaultdict(lambda: [0, 0, 0, 0, 0, 0])  # frames, passes, elements, style ms, layouts, layout ms
    hist = collections.Counter(); ms = collections.Counter()
    for fi, dur, passes, layouts, tok in rows:
        if tok is None: continue
        p = per[tok]; p[0] += 1; p[1] += len(passes); p[2] += sum(e for e, _ in passes); p[3] += sum(t for _, t in passes); p[4] += len(layouts); p[5] += sum(t for _, t in layouts)
        for e, t in passes: hist[e] += 1; ms[e] += t
    print(f"\n{label}: per token: frames / UpdateLayoutTree / elements restyled / style ms / layouts / layout ms")
    for k in sorted(per): print(f"  token {k}: {per[k][0]} / {per[k][1]} / {per[k][2]} / {per[k][3]} / {per[k][4]} / {per[k][5]}")
    tot = [sum(v[i] for v in per.values()) for i in range(6)]
    print(f"  total : {tot[0]} / {tot[1]} / {tot[2]} / {tot[3]} / {tot[4]} / {tot[5]}")
    return hist, ms, tot
h1, m1, t1 = summary(ref, "REF " + sys.argv[1].split("/")[-1]); h2, m2, t2 = summary(cand, "CAND " + sys.argv[2].split("/")[-1])
print("\nrecurring pass sizes (elementCount: passes ref/cand, summed ms ref/cand):")
keys = sorted(set(h1) | set(h2), key=lambda k: -(m1[k] + m2[k]))
for k in keys[:40]: print(f"  {k:6d}: {h1[k]:4d}/{h2[k]:4d}   {m1[k]:6d}/{m2[k]:6d} ms")
print(f"\nelements restyled total ref {t1[2]} cand {t2[2]} (delta {t2[2]-t1[2]}); style ms {t1[3]} -> {t2[3]}; layout ms {t1[5]} -> {t2[5]}; frames {t1[0]} -> {t2[0]}")
