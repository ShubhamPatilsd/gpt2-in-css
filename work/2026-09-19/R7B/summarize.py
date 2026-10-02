#!/usr/bin/env python3
"""R7B (= R6X/summarize32.py generalised): per-token table for a bench_native.mjs run vs a reference JSON whose freeRunningReference
lists the expected --saved-token-e per epoch (-1 on skipped prefill epochs) up to stopEpoch (default = len). Slots beyond the stop
must be unset (-1). usage: summarize.py <run.json> <reference.json>"""
import json, sys, statistics, bisect
_ref = json.load(open(sys.argv[2]))
REF = _ref.get("freeRunningReference") or _ref["teacherForcedReference"]
STOP = int(_ref.get("stopEpoch") or len(REF))
N = int(_ref.get("promptTokenCount") or 1)
R = json.load(open(sys.argv[1]))
cap = R.get("capacity", 32); ev = R.get("tokenEvents", []); tRun, tEnd = R["tRun"], R["tEndWait"]
ms = sorted(R.get("metricSamples", []), key=lambda s: s["tResp"]); mt = [s["tResp"] for s in ms]
rs = sorted([s for s in R.get("rssSamples", []) if "rendererMaxMB" in s], key=lambda s: s["t"]); rt = [s["t"] for s in rs]
def m_at(t):
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
exp = REF[:STOP]
ok = sum(1 for a, b in zip(ids, exp) if a == b)
beyond = [ids[i] for i in range(STOP, cap) if ids[i] not in (None, -1)]
print(f"# {R.get('label')} — {len(ev)}/{STOP} tokens captured (capacity {cap}), stopReason={R.get('stopReason')}, trigger={R.get('trigger')}, load {round((R['tLoad']-R['tNav0'])/1000,1)} s, Run at {round((tRun-R['tNav0'])/1000,1)} s after nav; seed {R.get('seedPick')} T {R.get('tempPick')}\n")
print(f"ids {ok}/{STOP} vs reference ({sys.argv[2]}; prompt tokens {N}, prefill epochs 1..{N-1} expected -1); ids={ids[:STOP]}; slots beyond the stop set: {beyond}")
new_ok = sum(1 for i in range(N - 1, STOP) if ids[i] == exp[i]); print(f"NEW tokens {new_ok}/{STOP - N + 1} identical")
mis = [i + 1 for i, (a, b) in enumerate(zip(ids, exp)) if a != b]
print(f"first mismatching epoch: {mis[0] if mis else None}; mismatches at {mis}\n")
r7b = (R.get("finalState") or {}).get("r7b") or {}
print(f"r7b state: {json.dumps(r7b)[:700]}\n")
print("| epoch | kind | s/epoch | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB | RSS at capture |")
print("|---:|---|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|")
prev_t = tRun; prev_m = m_at(tRun); rows = []
for e in ev:
    m = m_at(e["tResp"]); d = lambda k: (m.get(k, 0) or 0) - (prev_m.get(k, 0) or 0)
    rmax, rend = rss_between(prev_t, e["tResp"])
    k = e["k"]; kind = "prefill(skip)" if k < N else f"new {k - N + 1}"
    row = dict(k=k, kind=kind, s=e["tokenSeconds"], cum=e["sinceRun"] / 1000, id=ids[k - 1], ok=ids[k - 1] == (exp[k - 1] if k <= STOP else None), recalc=d("RecalcStyleCount"), layout=d("LayoutCount"), style=d("RecalcStyleDuration"), lay=d("LayoutDuration"), task=d("TaskDuration"), rmax=rmax, rend=rend)
    rows.append(row)
    print(f"| {k} | {kind} | {row['s']:.1f} | {row['cum']:.0f} | {row['id']} | {'Y' if row['ok'] else 'N'} | {row['recalc']} | {row['layout']} | {row['style']:.1f} | {row['lay']:.1f} | {row['task']:.1f} | {rmax} | {rend} |")
    prev_t, prev_m = e["tResp"], m
per = [r["s"] for r in rows]
if len(per) >= 3:
    new = [r for r in rows if r["k"] >= N]; pre = [r for r in rows if r["k"] < N]
    if pre: print(f"\nprefill epochs 1..{N-1}: {[round(r['s'],1) for r in pre]} s (mean {statistics.mean(r['s'] for r in pre):.1f})")
    xs = [r["k"] for r in new]; ys = [r["s"] for r in new]
    def fit(xs, ys):
        n = len(xs); mx = sum(xs) / n; my = sum(ys) / n; sxx = sum((x - mx) ** 2 for x in xs) or 1
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx; a = my - b * mx
        res = [y - (a + b * x) for x, y in zip(xs, ys)]; return a, b, (sum(r * r for r in res) / max(1, n - 2)) ** 0.5
    if len(xs) >= 3:
        a, b, se = fit(xs[1:], ys[1:]); print(f"new-token epochs {xs[1]}..{xs[-1]}: s/epoch = {a:.2f} + {b:.3f}·epoch (rmse {se:.2f})")
    print(f"total {(tEnd - tRun)/1000:.1f} s for {len(per)} epochs; median {statistics.median(per):.1f}; first {per[0]:.1f}; last {per[-1]:.1f}; min {min(per):.1f}; max {max(per):.1f}")
    print(f"RSS peak during generation {max(r['rmax'] for r in rows if r['rmax'])} MB; before run {rss_between(0, tRun)[1]} MB; at end {rows[-1]['rend']} MB")
m0, m1 = R.get("mBeforeRun") or {}, R.get("mAfterGen") or {}
d = lambda k: (m1.get(k, 0) or 0) - (m0.get(k, 0) or 0)
print(f"whole-run CDP deltas: RecalcStyleCount {d('RecalcStyleCount')}, LayoutCount {d('LayoutCount')}, RecalcStyleDuration {d('RecalcStyleDuration'):.1f} s, LayoutDuration {d('LayoutDuration'):.1f} s, TaskDuration {d('TaskDuration'):.1f} s, Nodes {m1.get('Nodes')}")
