#!/usr/bin/env python3
"""Aggregate the protocol runs of one bundle: 3 untraced run JSONs (+ optional traced summary) -> results.md row + detail md.
usage: aggregate.py <row-name> <detail.md> <run1.json> [run2.json run3.json ...] [--trace <label>-summary.json] [--notes "..."]
"""
import json, sys, statistics, os
sys.path.insert(0, os.path.dirname(__file__))
from summarize_run import summarize, EXPECTED

args = sys.argv[1:]
notes = ""; trace = None
if "--notes" in args: i = args.index("--notes"); notes = args[i + 1]; del args[i:i + 2]
if "--trace" in args: i = args.index("--trace"); trace = args[i + 1]; del args[i:i + 2]
name, detail_path, runs = args[0], args[1], args[2:]
S = [summarize(p) for p in runs]
cap = len(EXPECTED)
per_runs = [s["perToken"] for s in S if len(s["perToken"]) == cap]
per_med = [round(statistics.median(col), 1) for col in zip(*per_runs)] if per_runs else []
def slope(y):
    n = len(y); xs = range(1, n + 1); mx = (n + 1) / 2; my = sum(y) / n
    return sum((x - mx) * (v - my) for x, v in zip(xs, y)) / sum((x - mx) ** 2 for x in xs)
median = round(statistics.median(per_med), 1) if per_med else None
sl = round(slope(per_med), 2) if len(per_med) >= 3 else None
rss = max((s["rssPeakGenMB"] or 0) for s in S)
ids_ok = all(s["idsOk"] == f"{cap}/{cap}" for s in S)
ids_str = "; ".join(s["idsOk"] for s in S)
style_cdp = [s["cdp"]["style_pct"] for s in S if s["cdp"]["style_pct"] is not None]
T = json.load(open(trace)) if trace and os.path.exists(trace) else None
frames = wholedom = style_tr = passes = None; hist_lines = []
if T:
    toks = [t for t in T["tokens"] if isinstance(t["token_index"], int)]
    if toks:
        frames = round(sum(t["frames"] for t in toks) / len(toks), 1)
        wholedom = round(sum(t["style_hist"].get(">=50%DOM", [0, 0, 0])[0] for t in toks) / len(toks), 1)
        style_tr = round(100 * sum(t["style_ms"] for t in toks) / sum(t["wall_ms"] for t in toks), 1)
        passes = round(sum(t["style_count"] for t in toks) / len(toks), 1)
    H = T["style_hist_generate"]; tot = sum(h["ms"] for h in H.values()) or 1
    hist_lines.append("| elementCount bucket | passes | per token | summed ms | % of style | mean ms/pass | µs/element |")
    hist_lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for k in ("1-9", "10-99", "100-999", "1k-9,999", "10k-<50%DOM", ">=50%DOM", "unknown"):
        if k in H:
            h = H[k]; hist_lines.append(f"| {k} | {h['count']} | {h['count']/max(1,len(toks)):.1f} | {h['ms']:,.0f} | {100*h['ms']/tot:.1f} % | {h['ms']/h['count']:.1f} | {h['us_per_element'] if h['us_per_element'] is not None else '–'} |")
    hist_lines.append("")
    hist_lines.append("Top recurring passes by exact elementCount (n, per token, summed ms, mean ms):")
    hist_lines.append("")
    hist_lines.append("| elementCount | passes | per token | summed ms | mean ms |")
    hist_lines.append("|---:|---:|---:|---:|---:|")
    for ec, n, m in T["style_by_elementCount_top"][:20]:
        hist_lines.append(f"| {ec:,} | {n} | {n/max(1,len(toks)):.1f} | {m:,.0f} | {m/n:.1f} |")
status = "" if ids_ok else " **FAILED ids**"
cont = [s["label"] for s in S if s.get("contended")]
if cont: notes = (notes + "; " if notes else "") + "contended runs: " + ",".join(cont)
per_str = " ".join(f"{x:.1f}" for x in per_med) if per_med else "n/a"
row = (f"| {name}{status} | {ids_str} | {per_str} | {median} | {sl} | {rss} | "
       f"{style_tr if style_tr is not None else '–'} (trace) / {round(statistics.median(style_cdp),1) if style_cdp else '–'} (CDP) | "
       f"{frames if frames is not None else '–'} | {wholedom if wholedom is not None else '–'} | {notes} |")
print(row)
L = [f"# {name}", "", f"Runs: {', '.join(os.path.basename(p) for p in runs)}" + (f"; trace summary {os.path.basename(trace)}" if trace else ""), "",
     "| run | heap flag | tokens | ids | per-token s (1–8) | median | slope | total s | load ms | RSS peak MB | CDP style % | CDP layout % | recalcs/tok | layouts/tok | reply latency max ms |",
     "|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
for s, p in zip(S, runs):
    L.append(f"| {s['label']} | {s['heapFlag']} | {s['tokens']} | {s['idsOk']} {s['ids']} | {' '.join(f'{x:.1f}' for x in s['perToken'])} | {s['median']} | {s['slope']} | {s['total']} | {s['loadMs']} | {s['rssPeakGenMB']} | {s['cdp']['style_pct']} | {s['cdp']['layout_pct']} | {s['cdp']['recalcsPerToken']} | {s['cdp']['layoutsPerToken']} | {s['replyLatencyMaxMs']} |")
L += ["", f"Per-token median across untraced runs: {per_str}; median {median} s; slope {sl} s/token/token; RSS peak {rss} MB.", ""]
if T:
    L += [f"## Light trace ({os.path.basename(trace)})", "", f"Complete traced tokens: {[t['token_index'] for t in toks]}; style {style_tr} % of wall; {passes} style passes/token; {frames} frames/token; {wholedom} whole-DOM (≥50 % of DOM) passes/token; GC nested total {T.get('gc_total_ms_generate')} ms over the traced window.", ""]
    L += ["### Style-pass histogram (traced generate window)", ""] + hist_lines + [""]
    L += ["### Per-token phase split (from the trace)", "", "| token | wall s | style % | layout % | animate % | prepaint % | paint lifecycle % | hit-test % | GC nested % | passes | layouts | frames | whole-DOM passes |", "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for t in toks:
        w = t["wall_ms"] or 1
        L.append(f"| {t['token_index']} | {w/1000:.1f} | {100*t['style_ms']/w:.1f} | {100*t['layout_ms']/w:.1f} | {100*t['animate_ms']/w:.1f} | {100*t['prepaint_ms']/w:.1f} | {100*t['paint_lifecycle_ms']/w:.1f} | {100*t['hittest_ms']/w:.1f} | {100*t['gc_nested_ms']/w:.1f} | {t['style_count']} | {t['layout_count']} | {t['frames']} | {t['style_hist'].get('>=50%DOM',[0])[0]} |")
    L.append("")
if notes: L += ["Notes: " + notes, ""]
open(detail_path, "w").write("\n".join(L))
