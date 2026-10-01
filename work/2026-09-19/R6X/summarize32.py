#!/usr/bin/env python3
"""R4C: per-token table for a capacity-32 bench_native.mjs run: seconds per token, ids vs the 32 reference ids, RecalcStyle/Layout counts
and durations per token (from the 1 Hz Performance.getMetrics samples, nearest sample at/after each token capture), RSS per token, slope fit."""
import json, sys, statistics, bisect
# R4M: reference ids from a JSON file (R4C/reference_ids_32.json for the default Hello prompt, R4P/reference_ids_32_40.json for prompt 40); key freeRunningReference
_ref = json.load(open(sys.argv[2] if len(sys.argv) > 2 else "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4C/reference_ids_32.json"))
REF = _ref.get("freeRunningReference") or _ref["teacherForcedReference"]
R = json.load(open(sys.argv[1]))
cap = R.get("capacity", 32); ev = R.get("tokenEvents", []); tRun, tEnd = R["tRun"], R["tEndWait"]
ms = sorted(R.get("metricSamples", []), key=lambda s: s["tResp"]); mt = [s["tResp"] for s in ms]
rs = sorted([s for s in R.get("rssSamples", []) if "rendererMaxMB" in s], key=lambda s: s["t"]); rt = [s["t"] for s in rs]
def m_at(t):  # first metrics sample at/after t (counters are monotone; the sample may lag while the main thread is busy)
    i = bisect.bisect_left(mt, t); return ms[min(i, len(ms) - 1)] if ms else {}
def rss_between(a, b):
    i, j = bisect.bisect_left(rt, a), bisect.bisect_right(rt, b); seg = rs[i:j]
    return (max(s["rendererMaxMB"] for s in seg) if seg else None, seg[-1]["rendererMaxMB"] if seg else None)
slot = (R.get("finalState") or {}).get("slotProps") or {}
ids = []
for i in range(1, cap + 1):
    v = slot.get(f"--saved-token-{i}")
    try: ids.append(int(float(v)))
    except Exception: ids.append(None)
ok = sum(1 for a, b in zip(ids, REF) if a == b)
print(f"# {R.get('label')} — {len(ev)}/{cap} tokens, stopReason={R.get('stopReason')}, trigger={R.get('trigger')}, heapFlag={R.get('heapFlag')}, load {round((R['tLoad']-R['tNav0'])/1000,1)} s, Run at {round((tRun-R['tNav0'])/1000,1)} s after nav\n")
print(f"ids {ok}/{cap} vs reference ({sys.argv[2] if len(sys.argv) > 2 else 'R4C/reference_ids_32.json'}; prompt token {R.get('promptToken') or 'default 15496'}); ids={ids}")
mis = [i + 1 for i, (a, b) in enumerate(zip(ids, REF)) if a != b]
print(f"first mismatching position: {mis[0] if mis else None}; mismatches at {mis}\n")
print("| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |")
print("|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|")
prev_t = tRun; prev_m = m_at(tRun); rows = []
for e in ev:
    m = m_at(e["tResp"]); d = lambda k: (m.get(k, 0) or 0) - (prev_m.get(k, 0) or 0)
    rmax, rend = rss_between(prev_t, e["tResp"])
    k = e["k"]; row = dict(k=k, s=e["tokenSeconds"], cum=e["sinceRun"] / 1000, id=ids[k - 1], ok=ids[k - 1] == REF[k - 1], recalc=d("RecalcStyleCount"), layout=d("LayoutCount"), style=d("RecalcStyleDuration"), lay=d("LayoutDuration"), task=d("TaskDuration"), rmax=rmax, rend=rend)
    rows.append(row)
    print(f"| {k} | {row['s']:.1f} | {row['cum']:.0f} | {row['id']} | {'Y' if row['ok'] else 'N'} | {row['recalc']} | {row['layout']} | {row['style']:.1f} | {row['lay']:.1f} | {row['task']:.1f} | {rmax} | {rend} |")
    prev_t, prev_m = e["tResp"], m
per = [r["s"] for r in rows]
def fit(xs, ys):
    n = len(xs); mx = sum(xs) / n; my = sum(ys) / n; sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx; a = my - b * mx
    res = [y - (a + b * x) for x, y in zip(xs, ys)]; return a, b, (sum(r * r for r in res) / max(1, n - 2)) ** 0.5
if len(per) >= 3:
    xs = [r["k"] for r in rows]
    a, b, se = fit(xs, per); print(f"\nlinear fit s/token = {a:.2f} + {b:.3f}·k  (rmse {se:.2f}); tokens 2..{len(per)}: ", end="")
    a2, b2, se2 = fit(xs[1:], per[1:]); print(f"{a2:.2f} + {b2:.3f}·k (rmse {se2:.2f})")
    for key, lab in (("recalc", "RecalcStyleCount"), ("layout", "LayoutCount"), ("style", "RecalcStyleDuration s"), ("lay", "LayoutDuration s"), ("task", "TaskDuration s")):
        ys = [r[key] for r in rows[1:]]; a3, b3, se3 = fit(xs[1:], ys); print(f"  {lab}: {a3:.2f} + {b3:.3f}·k (rmse {se3:.2f})")
    print(f"\ntotal {(tEnd - tRun)/1000:.1f} s for {len(per)} tokens; median {statistics.median(per):.1f}; first {per[0]:.1f}; last {per[-1]:.1f}; min {min(per):.1f}; max {max(per):.1f}")
    print(f"RSS peak during generation {max(r['rmax'] for r in rows if r['rmax'])} MB; before run {rss_between(0, tRun)[1]} MB; at end {rows[-1]['rend']} MB")
m0, m1 = R.get("mBeforeRun") or {}, R.get("mAfterGen") or {}
d = lambda k: (m1.get(k, 0) or 0) - (m0.get(k, 0) or 0)
print(f"whole-run CDP deltas: RecalcStyleCount {d('RecalcStyleCount')}, LayoutCount {d('LayoutCount')}, RecalcStyleDuration {d('RecalcStyleDuration'):.1f} s, LayoutDuration {d('LayoutDuration'):.1f} s, TaskDuration {d('TaskDuration'):.1f} s, Nodes {m1.get('Nodes')}")
