#!/usr/bin/env python3
"""R3L: per-variant trace anatomy of the traced mutation (all trials): style passes (elementCount:ms), Layout, the
paint lifecycle (`LocalFrameView::RunPaintLifecyclePhase` incl/self, PrePaint), the animate step
(`WebFrameWidgetImpl::BeginMainFrame`), Animation async start/end counts, frames, and main-thread busy ms.
usage: analyze.py <results-dir> <traces-dir> [out.md]"""
import glob, gzip, json, os, sys
from collections import Counter, defaultdict
from statistics import median

res, traces = sys.argv[1], sys.argv[2]
out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(res, "anatomy.md")
rows = defaultdict(list)
for path in sorted(glob.glob(os.path.join(traces, "*.trace.json.gz"))):
    d = json.load(gzip.open(path, "rt"))
    ev, meta = d["traceEvents"], d["metadata"]
    lo, hi = meta["windowStartUs"], meta["windowEndUs"]
    cnt = Counter((e.get("pid"), e.get("tid")) for e in ev if e.get("name") == "UpdateLayoutTree" and e.get("ph") == "X")
    if not cnt:
        continue
    (PID, TID), _ = cnt.most_common(1)[0]
    X = [e for e in ev if e.get("pid") == PID and e.get("tid") == TID and e.get("ph") == "X" and lo <= e["ts"] <= hi]
    X.sort(key=lambda e: (e["ts"], -e.get("dur", 0)))
    def total(name):
        return sum(e.get("dur", 0) for e in X if e["name"] == name) / 1000
    def self_ms(name):
        s = 0
        for e in X:
            if e["name"] != name:
                continue
            a, b = e["ts"], e["ts"] + e.get("dur", 0)
            kids = [k for k in X if k is not e and a <= k["ts"] and k["ts"] + k.get("dur", 0) <= b]
            # direct children only: drop kids nested in other kids
            direct = []
            for k in sorted(kids, key=lambda k: (k["ts"], -k.get("dur", 0))):
                if not direct or k["ts"] >= direct[-1]["ts"] + direct[-1].get("dur", 0):
                    direct.append(k)
            s += e.get("dur", 0) - sum(k.get("dur", 0) for k in direct)
        return s / 1000
    passes = []
    for e in X:
        if e["name"] == "UpdateLayoutTree":
            a = e.get("args") or {}
            ec = a.get("elementCount", (a.get("endData") or {}).get("elementCount", -1))
            passes.append(f"{ec}:{e.get('dur', 0) / 1000:.1f}")
    anim = [e for e in ev if e.get("pid") == PID and e.get("name") == "Animation" and e.get("ph") in ("b", "e") and lo <= e["ts"] <= hi]
    frames = sum(1 for e in X if e["name"] == "ProxyMain::BeginMainFrame")
    top = [e for e in X if e.get("cat", "").find("toplevel") >= 0 or e["name"] in ("ThreadControllerImpl::RunTask", "MessageLoop::RunTask")]
    busy = sum(e.get("dur", 0) for e in top) / 1000
    rows[meta["variant"]].append({
        "trial": meta["trial"], "passes": passes, "ult": total("UpdateLayoutTree"), "layout": total("Layout"),
        "plc_incl": total("LocalFrameView::RunPaintLifecyclePhase"), "plc_self": self_ms("LocalFrameView::RunPaintLifecyclePhase"),
        "prepaint": total("PrePaint"), "animate": total("WebFrameWidgetImpl::BeginMainFrame"),
        "anim_b": sum(1 for e in anim if e["ph"] == "b"), "anim_e": sum(1 for e in anim if e["ph"] == "e"),
        "frames": frames, "busy": busy})
lines = ["# R3L fixture anatomy (traced mutation window; all trials)", "",
         "| variant | trial | style passes (elements:ms) | ULT ms | Layout ms | PrePaint ms | PaintLifecycle incl / self ms | animate step ms | Animation b / e | frames | busy ms |",
         "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
summary = ["", "## Medians", "", "| variant | ULT ms | Layout ms | PrePaint ms | PaintLifecycle self ms | animate ms | Animation b / e | frames | busy ms |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
for v, rs in rows.items():
    for r in sorted(rs, key=lambda r: r["trial"]):
        lines.append(f"| {v} | {r['trial']} | {' '.join(r['passes'])} | {r['ult']:.1f} | {r['layout']:.1f} | {r['prepaint']:.1f} | {r['plc_incl']:.1f} / {r['plc_self']:.1f} | {r['animate']:.1f} | {r['anim_b']} / {r['anim_e']} | {r['frames']} | {r['busy']:.1f} |")
    m = lambda k: median(r[k] for r in rs)
    summary.append(f"| {v} | {m('ult'):.1f} | {m('layout'):.1f} | {m('prepaint'):.1f} | {m('plc_self'):.1f} | {m('animate'):.1f} | {int(m('anim_b'))} / {int(m('anim_e'))} | {int(m('frames'))} | {m('busy'):.1f} |")
open(out, "w").write("\n".join(lines + summary) + "\n")
print("\n".join(summary))
