#!/usr/bin/env python3
"""Emit markdown tables for P2-trace.md from <label>-summary.json + <label>.json."""
import json, sys
label = sys.argv[1]
S = json.load(open(f"{label}-summary.json")); R = json.load(open(f"{label}.json"))
toks = [t for t in S["tokens"] if isinstance(t["token_index"], int)]
def pct(x, w): return f"{100*x/w:.1f} %"
print(f"### {label}: per-token phase split (ms; % of window wall)\n")
cols = [("wall_ms","wall"),("busy_ms","main-thread busy"),("idle_ms","idle"),("style_ms","style (UpdateLayoutTree)"),("recalcStyle_self_ms","  of which recalcStyle self (no nested GC)"),("layout_ms","layout"),("of_which_text_shaping_ms","  of which text shaping"),("animate_ms","animation servicing (Blink.Animate)"),("prepaint_ms","pre-paint + compositing inputs"),("paint_lifecycle_ms","paint lifecycle (RunPaintLifecyclePhase)"),("of_which_Paint_ms","  of which Paint"),("hittest_ms","hit-test (fake mousemove)"),("other_busy_ms","other busy (unattributed)"),("gc_nested_ms","GC (nested inside the above)")]
hdr = "| phase | " + " | ".join(f"token {t['token_index']}" for t in toks) + " | mean |"
print(hdr); print("|---|" + "---:|" * (len(toks) + 1))
for k, name in cols:
    vals = [t.get(k, 0) or 0 for t in toks]; mean = sum(vals) / len(vals)
    if k == "wall_ms":
        print(f"| {name} | " + " | ".join(f"{v:,.0f}" for v in vals) + f" | {mean:,.0f} |")
    else:
        print(f"| {name} | " + " | ".join(f"{v:,.0f} ({pct(v, t['wall_ms'])})" for v, t in zip(vals, toks)) + f" | {mean:,.0f} ({pct(mean, sum(t['wall_ms'] for t in toks)/len(toks))}) |")
print("| style passes / layouts / frames | " + " | ".join(f"{t['style_count']} / {t['layout_count']} / {t['frames']}" for t in toks) + " | |")
print("| major GCs | " + " | ".join(str(t.get('majorGC_count','?')) for t in toks) + " | |")
print("| token boundary (s after Run) | " + " | ".join(f"{t['end_ms_after_run']/1000:.1f}" for t in toks) + " | |")
print("| handshakes (s after Run) | " + " | ".join("; ".join(f"{h[0]/1000:.1f} {h[1].split(chr(39))[1]}" for h in t['handshakes']) for t in toks) + " | |")
print()
print(f"### {label}: style-pass histogram over the traced generate window ({len(toks)} complete tokens{' + partial' if len(S['tokens'])>len(toks) else ''})\n")
H = S["style_hist_generate"]; tot = sum(h["ms"] for h in H.values()); totn = sum(h["count"] for h in H.values())
print("| elementCount bucket | passes | per token | summed ms | % of style ms | mean ms/pass | min–max ms | µs per element |")
print("|---|---:|---:|---:|---:|---:|---:|---:|")
for k in ("1-9","10-99","100-999","1k-9,999","10k-<50%DOM",">=50%DOM","unknown"):
    if k in H:
        h = H[k]; print(f"| {k} | {h['count']} | {h['count']/len(toks):.1f} | {h['ms']:,.0f} | {pct(h['ms'], tot)} | {h['ms']/h['count']:.1f} | {h['min_ms']:.1f}–{h['max_ms']:.0f} | {h['us_per_element'] if h['us_per_element'] is not None else '–'} |")
print(f"| **total** | {totn} | {totn/len(toks):.0f} | {tot:,.0f} | 100 % | | | |")
print()
print("Recurring passes by exact elementCount (whole window; n = passes, ms = summed):\n")
print("| elementCount | passes | per token | summed ms | mean ms | µs/element |")
print("|---:|---:|---:|---:|---:|---:|")
for ec, n, m in S["style_by_elementCount_top"][:22]:
    print(f"| {ec:,} | {n} | {n/len(toks):.1f} | {m:,.0f} | {m/n:.1f} | {1000*m/n/ec if ec else float('nan'):.1f} |" if ec else f"| {ec} | {n} | {n/len(toks):.1f} | {m:,.0f} | {m/n:.1f} | – |")
print()
# per-token whole-DOM share
print("Whole-DOM (≥50 % of 72,549 elements) passes per token:\n")
print("| token | whole-DOM passes | ms | % of token style | biggest pass (ms, elements) |")
print("|---:|---:|---:|---:|---|")
for t in toks:
    h = t["style_hist"].get(">=50%DOM", [0, 0, 0]); print(f"| {t['token_index']} | {h[0]} | {h[1]:,.0f} | {pct(h[1], t['style_ms'])} | {t['ult_biggest'][0][:2]} |")
print()
if S.get("invalidation_event_names"):
    print(f"### {label}: invalidation tracking (traced window)\n")
    print("| event | reason | count | per token |"); print("|---|---|---:|---:|")
    for evn, reason, n in S["invalidation_by_event_reason"][:18]: print(f"| {evn} | {reason or '(none)'} | {n:,} | {n/len(toks):,.0f} |")
    print("\nStyleInvalidator / ScheduleStyleInvalidation by selector part (per token ≈ count/4):\n")
    print("| event | reason | part | count |"); print("|---|---|---|---:|")
    import re as _re, collections as _c
    grouped = _c.Counter(); shown = 0
    for evn, reason, part, n in S["invalidation_by_event_reason_part"]:
        if not part: continue
        g = _re.sub(r"-\d+$", "-N", part)
        if g != part: grouped[(evn, reason, g)] += n; continue
        print(f"| {evn} | {reason or '(none)'} | `{part}` | {n} |")
    for (evn, reason, g), n in grouped.most_common(): print(f"| {evn} | {reason or '(none)'} | `{g}` (all N, summed) | {n} |")
    print()
# GC
print(f"GC by name (window): {S['gc_by_name'][:8]}, total nested {S['gc_total_ms_generate']:,.0f} ms\n")
# memory
rs = R["rssSamples"]; tRun = R["tRun"]
bounds = [0.0] + [t["end_ms_after_run"] / 1000 for t in toks]
print(f"### {label}: renderer RSS (MB, `ps`, 1 Hz)\n")
print("| interval | min | mean | max |"); print("|---|---:|---:|---:|")
def seg(a, b): return [s["rendererMaxMB"] for s in rs if a <= (s["t"] - tRun) / 1000 < b]
pre = [s["rendererMaxMB"] for s in rs if s["t"] < tRun]; print(f"| launch→Run (load + idle) | {min(pre)} | {sum(pre)//len(pre)} | {max(pre)} |")
for i in range(len(bounds) - 1):
    x = seg(bounds[i], bounds[i+1]); print(f"| token {i+1} ({bounds[i]:.0f}–{bounds[i+1]:.0f} s) | {min(x)} | {sum(x)//len(x)} | {max(x)} |")
rest = seg(bounds[-1], (R["tEndWait"] - tRun) / 1000)
if rest: print(f"| rest of run ({bounds[-1]:.0f}–{(R['tEndWait']-tRun)/1000:.0f} s) | {min(rest)} | {sum(rest)//len(rest)} | {max(rest)} |")
post = [s["rendererMaxMB"] for s in rs if (s["t"] - tRun) / 1000 >= (R["tEndWait"] - tRun) / 1000]
if post: print(f"| after completion (readback) | {min(post)} | {sum(post)//len(post)} | {max(post)} |")
print(f"| browser process peak | | | {max(s['browserMB'] for s in rs)} |"); print(f"| GPU process peak | | | {max(s['gpuMB'] for s in rs)} |")
m0, m1 = R["mBeforeRun"], R["mAfterGen"]
print(f"\nCDP Performance.getMetrics deltas Run→end ({(m1['Timestamp']-m0['Timestamp']):.1f} s wall): RecalcStyleCount +{m1['RecalcStyleCount']-m0['RecalcStyleCount']}, RecalcStyleDuration +{m1['RecalcStyleDuration']-m0['RecalcStyleDuration']:.1f} s, LayoutCount +{m1['LayoutCount']-m0['LayoutCount']}, LayoutDuration +{m1['LayoutDuration']-m0['LayoutDuration']:.1f} s, TaskDuration +{m1['TaskDuration']-m0['TaskDuration']:.1f} s; Nodes {m1['Nodes']}, LayoutObjects {m1['LayoutObjects']}")
lp = S.get("load_phase", {})
print(f"\nLoad phase ({label}): " + json.dumps({k: v for k, v in lp.items() if k not in ('self_top','incl_top')}) + "\nnamed: " + json.dumps(S.get("load_named")) + "\nbig: " + json.dumps(S.get("load_big_events", [])[:12]))
print("nav:", {k: R["navInfo"]["nav"].get(k) for k in ("responseEnd","domInteractive","domContentLoadedEventEnd","domComplete","loadEventEnd")}, {k: v for k, v in R["navInfo"].items() if k != "nav"})
print("timeline:", {k: R.get(k) for k in ("tNav0","tLoad","tIdle","tRun","tEndWait","stopReason","traceBytes","dataLossOccurred")}, "finalState:", json.dumps(R["finalState"].get("captureObserver")), json.dumps(R["finalState"].get("slotProps")))
