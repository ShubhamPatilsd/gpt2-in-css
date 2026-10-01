#!/usr/bin/env python3
"""R6L: one row per load JSON under R6L/loads/<bundle>/ → R6L/loads/SUMMARY.md (mean ± spread per arm)."""
import json, statistics, sys
from pathlib import Path
root = Path(__file__).resolve().parent / "loads"; rows = []; arms = {}
for j in sorted(root.glob("*/*.json")):
    d = json.loads(j.read_text()); n = d["navInfo"]; m = d["mIdle"]
    css_end = (n.get("css") or {}).get("responseEnd"); fl = n.get("fontsLastEnd")
    r = dict(arm=j.parent.name, run=j.stem, load=d["loadS"], fp=d["firstPaintS"], ready=d["readyS"], idle=d["idleS"], css_end=css_end and css_end / 1000, fonts_end=fl and fl / 1000,
             recalc=m["RecalcStyleCount"], recalc_s=m["RecalcStyleDuration"], layout=m["LayoutCount"], layout_s=m["LayoutDuration"], task_s=m["TaskDuration"], rss=d["rssPeakMB"], dom_i=(n.get("nav") or {}).get("domInteractive"))
    rows.append(r); arms.setdefault(r["arm"], []).append(r)
out = ["| arm | run | load event s | first paint s | Ready s | idle s | css responseEnd s | last font s | domInteractive ms | RecalcStyle n / s | Layout n / s | Task s | RSS peak MB |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|"]
f = lambda v: "—" if v is None else (f"{v:.1f}" if isinstance(v, float) else str(v))
for r in rows:
    out.append(f"| {r['arm']} | {r['run']} | {f(r['load'])} | {f(r['fp'])} | {f(r['ready'])} | {f(r['idle'])} | {f(r['css_end'])} | {f(r['fonts_end'])} | {f(r['dom_i'])} | {r['recalc']} / {r['recalc_s']:.2f} | {r['layout']} / {r['layout_s']:.2f} | {r['task_s']:.1f} | {r['rss']} |")
out += ["", "| arm | n | load event s mean [min…max] | first paint s | Ready s | idle s |", "|---|---:|---|---|---|---|"]
def ms(vals):
    vals = [v for v in vals if v is not None]
    return "—" if not vals else f"{statistics.mean(vals):.1f} [{min(vals):.1f}…{max(vals):.1f}]"
for a, rs in arms.items():
    out.append(f"| {a} | {len(rs)} | {ms([r['load'] for r in rs])} | {ms([r['fp'] for r in rs])} | {ms([r['ready'] for r in rs])} | {ms([r['idle'] for r in rs])} |")
(root / "SUMMARY.md").write_text("\n".join(out) + "\n"); print("\n".join(out))
