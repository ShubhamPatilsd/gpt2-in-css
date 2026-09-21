#!/usr/bin/env python3
"""R4W: per-token wall / style / layout / RSS for up to N bench_native.mjs runs side by side, with linear fits (k>=2) and
the R4V memory-state law fit time = a + b*k + c*RSS_GB per run. usage: compare3.py label=path.json [label=path.json ...]"""
import json, sys, bisect
import numpy as np
def load(p):
    R = json.load(open(p)); ev = R["tokenEvents"]; tRun = R["tRun"]
    ms = sorted(R["metricSamples"], key=lambda s: s["tResp"]); mt = [s["tResp"] for s in ms]
    def m_at(t):
        i = bisect.bisect_left(mt, t); return ms[min(i, len(ms) - 1)]
    rs = R["rssSamples"]; rt = np.array([s["t"] for s in rs]); rv = np.array([s["rendererMaxMB"] for s in rs])
    rows = []; prev = m_at(tRun); t_prev = tRun
    for e in ev:
        t = e["tResp"]; m = m_at(t)
        sel = (rt > t_prev) & (rt <= t)
        rows.append(dict(k=e["k"], s=e["tokenSeconds"], style=m["RecalcStyleDuration"] - prev["RecalcStyleDuration"],
                         lay=m["LayoutDuration"] - prev["LayoutDuration"], rss_mean=float(rv[sel].mean()) if sel.any() else float("nan"),
                         rss_max=float(rv[sel].max()) if sel.any() else float("nan")))
        prev, t_prev = m, t
    total = (R["tEndWait"] - R["tRun"]) / 1000
    return rows, total, R
runs = [(a.split("=", 1)[0], load(a.split("=", 1)[1])) for a in sys.argv[1:]]
K = max(len(r[1][0]) for r in runs)
hdr = "| k | " + " | ".join(f"{n} s (sty/lay) RSSmean MB" for n, _ in runs) + " |"
print(hdr); print("|---:|" + "|".join("---" for _ in runs) + "|")
for k in range(1, K + 1):
    cells = []
    for n, (rows, total, R) in runs:
        r = next((x for x in rows if x["k"] == k), None)
        cells.append(f"{r['s']:.1f} ({r['style']:.1f}/{r['lay']:.1f}) {r['rss_mean']:.0f}" if r else "—")
    print(f"| {k} | " + " | ".join(cells) + " |")
for n, (rows, total, R) in runs:
    k = np.array([r["k"] for r in rows if r["k"] >= 2], float); s = np.array([r["s"] for r in rows if r["k"] >= 2])
    st = np.array([r["style"] for r in rows if r["k"] >= 2]); la = np.array([r["lay"] for r in rows if r["k"] >= 2]); rss = np.array([r["rss_mean"] for r in rows if r["k"] >= 2]) / 1024
    fit = lambda y: np.polyfit(k, y, 1)
    b, a = fit(s); bs, as_ = fit(st); bl, al = fit(la)
    X = np.column_stack([np.ones_like(k), k, rss]); coef, *_ = np.linalg.lstsq(X, s, rcond=None); res = s - X @ coef
    res1 = s - np.polyval([b, a], k)
    print(f"\n[{n}] {len(rows)} tokens, total {total:.1f} s; fit(k>=2) wall {a:.2f} + {b:.3f}·k (rmse {res1.std():.2f}); style {as_:.2f} + {bs:.3f}·k; layout {al:.2f} + {bl:.3f}·k;"
          f" RSS mean {np.nanmean(rss)*1024:.0f} MB (min {np.nanmin(rss)*1024:.0f}, max {np.nanmax([r['rss_max'] for r in rows]):.0f});"
          f" law wall = {coef[0]:.2f} + {coef[1]:.3f}·k + {coef[2]:.2f}·RSS_GB (rmse {res.std():.2f}); corr(resid_k, RSS) = {np.corrcoef(res1, rss)[0,1]:.2f}")
