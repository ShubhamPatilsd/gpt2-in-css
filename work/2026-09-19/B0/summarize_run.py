#!/usr/bin/env python3
"""Summarize one bench run JSON (from bench_native.mjs): per-token s, median, slope, RSS peak, ids, CDP shares."""
import json, sys, statistics
EXPECTED = [11, 314, 1101, 7926, 11, 475, 314, 1101]

def summarize(path):
    R = json.load(open(path))
    cap = R.get("capacity", 8)
    ev = R.get("tokenEvents", [])
    per = [e["tokenSeconds"] for e in ev]
    tRun, tEnd = R["tRun"], R["tEndWait"]
    total = (tEnd - tRun) / 1000
    slot = (R.get("finalState") or {}).get("slotProps") or {}
    ids = []
    for i in range(1, cap + 1):
        v = slot.get(f"--saved-token-{i}")
        try: ids.append(int(float(v)))
        except Exception: ids.append(None)
    ok = sum(1 for a, b in zip(ids, EXPECTED) if a == b)
    m0, m1 = R.get("mBeforeRun") or {}, R.get("mAfterGen") or {}
    d = lambda k: (m1.get(k, 0) or 0) - (m0.get(k, 0) or 0)
    wall = (m1.get("Timestamp", 0) or 0) - (m0.get("Timestamp", 0) or 0)
    style_s, layout_s, task_s = d("RecalcStyleDuration"), d("LayoutDuration"), d("TaskDuration")
    gen_rss = [s.get("rendererMaxMB", 0) for s in R.get("rssSamples", []) if tRun <= s["t"] <= tEnd + 3000]
    all_rss = [s.get("rendererMaxMB", 0) for s in R.get("rssSamples", [])]
    slope = None
    if len(per) >= 3:
        n = len(per); xs = list(range(1, n + 1)); mx = sum(xs) / n; my = sum(per) / n
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, per)) / sum((x - mx) ** 2 for x in xs)
    out = {
        "label": R.get("label"), "heapFlag": R.get("heapFlag"), "traced": bool(R.get("tracePath")), "stopReason": R.get("stopReason"),
        "loadMs": round(R["tLoad"] - R["tNav0"]), "runAtMs": round(tRun - R["tNav0"]),
        "tokens": len(per), "perToken": [round(x, 1) for x in per], "median": round(statistics.median(per), 1) if per else None,
        "mean": round(sum(per) / len(per), 1) if per else None, "slope": round(slope, 2) if slope is not None else None,
        "total": round(total, 1), "ids": ids, "idsOk": f"{ok}/{cap}", "expected": EXPECTED,
        "rssPeakGenMB": max(gen_rss) if gen_rss else None, "rssPeakAllMB": max(all_rss) if all_rss else None,
        "cdp": {"wall": round(wall, 1), "style_s": round(style_s, 1), "layout_s": round(layout_s, 1), "task_s": round(task_s, 1),
                "style_pct": round(100 * style_s / wall, 1) if wall else None, "layout_pct": round(100 * layout_s / wall, 1) if wall else None,
                "recalcs": d("RecalcStyleCount"), "layouts": d("LayoutCount"),
                "recalcsPerToken": round(d("RecalcStyleCount") / len(per), 1) if per else None, "layoutsPerToken": round(d("LayoutCount") / len(per), 1) if per else None},
        "replyLatencyMaxMs": max((e["replyLatencyMs"] for e in ev), default=None),
        "contended": open(path[:-5] + ".contended").read().strip() if __import__("os").path.exists(path[:-5] + ".contended") else "",
    }
    return out

if __name__ == "__main__":
    o = summarize(sys.argv[1])
    if "--oneline" in sys.argv:
        print(f"tokens={o['tokens']} ids={o['idsOk']} per={o['perToken']} median={o['median']} slope={o['slope']} total={o['total']} rssPeak={o['rssPeakGenMB']}MB style%={o['cdp']['style_pct']} recalc/tok={o['cdp']['recalcsPerToken']} stop={o['stopReason']}" + (f" CONTENDED({o['contended']})" if o['contended'] else ''))
    else:
        print(json.dumps(o, indent=1))
