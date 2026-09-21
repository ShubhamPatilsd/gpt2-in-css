#!/usr/bin/env python3
"""R4D: side-by-side per-token curve of two bench_native.mjs JSON runs (before, after)."""
import json, sys, bisect
def load(p):
    R = json.load(open(p)); ev = R.get("tokenEvents", [])
    per = {e["k"]: e["tokenSeconds"] for e in ev}
    ms = sorted(R.get("metricSamples", []), key=lambda s: s["tResp"]); mt = [s["tResp"] for s in ms]
    def m_at(t):
        i = bisect.bisect_left(mt, t); return ms[min(i, len(ms) - 1)] if ms else {}
    style = {}; lay = {}; prev = m_at(R["tRun"])
    for e in ev:
        m = m_at(e["tResp"]); style[e["k"]] = (m.get("RecalcStyleDuration", 0) - prev.get("RecalcStyleDuration", 0)); lay[e["k"]] = (m.get("LayoutDuration", 0) - prev.get("LayoutDuration", 0)); prev = m
    rs = [s["rendererMaxMB"] for s in R.get("rssSamples", []) if "rendererMaxMB" in s]
    return dict(per=per, style=style, lay=lay, total=(R["tEndWait"] - R["tRun"]) / 1000, n=len(ev), rss=max(rs) if rs else None, ids=R.get("finalState", {}).get("slotProps", {}))
A, B = load(sys.argv[1]), load(sys.argv[2])
ks = sorted(set(A["per"]) | set(B["per"]))
print("| k | before s | after s | Δ | before style/layout s | after style/layout s |")
print("|---:|---:|---:|---:|---|---|")
for k in ks:
    a, b = A["per"].get(k), B["per"].get(k)
    d = f"{b - a:+.1f}" if a is not None and b is not None else ""
    print(f"| {k} | {a if a is None else f'{a:.1f}'} | {b if b is None else f'{b:.1f}'} | {d} | {A['style'].get(k,0):.1f}/{A['lay'].get(k,0):.1f} | {B['style'].get(k,0):.1f}/{B['lay'].get(k,0):.1f} |")
def fit(d):
    xs = [k for k in sorted(d) if k >= 2]; ys = [d[k] for k in xs]; n = len(xs)
    if n < 3: return (0, 0)
    mx = sum(xs) / n; my = sum(ys) / n; b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs); return my - b * mx, b
for lab, R in (("before", A), ("after", B)):
    a, b = fit(R["per"]); sa, sb = fit(R["style"]); la, lb = fit(R["lay"])
    print(f"{lab}: {R['n']} tokens, total {R['total']:.1f} s, fit(k>=2) {a:.1f} + {b:.3f}·k; style {sa:.1f} + {sb:.3f}·k; layout {la:.1f} + {lb:.3f}·k; RSS peak {R['rss']} MB")
