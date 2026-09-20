"""Fit the R2E fixture constants from results/hold.jsonl and predict the demo effect.
usage: python3 analyze.py [results/hold.jsonl]"""
import json, sys, statistics as st, collections
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "results/hold.jsonl")
recs = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
by = collections.defaultdict(lambda: collections.defaultdict(list))  # n -> step -> [step records]
for r in recs:
    for s in r["steps"]:
        by[r["n"]][s["name"]].append(s)
med = lambda xs: st.median(xs) if xs else float("nan")
def idle(n, step): return med([s["idle"]["msPerFrame"] for s in by[n][step] if s["idle"]["msPerFrame"] is not None])
def mut(n, step): return med([s["mutateMs"] for s in by[n][step]])
def recalcs(n, step): return med([s["recalcs"] for s in by[n][step]])
def match(n, step, key): return [s["values"][key] for s in by[n][step]] if n else None
N = max(k for k in by if k > 0)

print(f"# R2E pause-and-hold fixture — {len(recs)} trials, pages {sorted(by)}\n")
print("## Per step (page n=%d): mutation main-thread ms, style recalcs, values, idle ms/frame\n" % N)
print("| step | class | in | mutate ms | recalcs | layouts | sample values | expected | match expected | match previous | distinct | idle ms/frame | frames in idle | pending adds (trace) |")
print("|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|")
for name in [s["name"] for s in recs[0]["steps"]]:
    ss = by[N][name]
    v = ss[0]["values"]
    sched = ss[0].get("trace", {}).get("scheduleAnimation")
    print(f"| {name} | {ss[0]['cls'] or '(live)'} | {ss[0]['in']} | {mut(N, name):.1f} | {recalcs(N, name):.0f} | {med([s['layouts'] for s in ss]):.0f} | {v['sample']} | {v['expectedSample']} | {'/'.join(str(x) for x in match(N, name, 'matchExpected'))} | {'/'.join(str(x) for x in match(N, name, 'matchPrevious'))} | {v['distinct']} | {idle(N, name):.3f} | {med([s['idle']['frames'] for s in ss]):.0f} | {sched or ''} |")

print("\n## Idle per-frame cost, page n=0 (no carriers), by step\n")
print("| step | idle ms/frame | frames |")
print("|---|---:|---:|")
for name in [s["name"] for s in recs[0]["steps"]]:
    if 0 in by: print(f"| {name} | {idle(0, name):.3f} | {med([s['idle']['frames'] for s in by[0][name]]):.0f} |")

base = med([idle(0, s) for s in by[0]]) if 0 in by else float("nan")
live = med([idle(N, s) for s in ("live0", "live7", "resume21", "resume33", "resume45", "resume57", "resume69")])
paused = med([idle(N, s) for s in ("paused", "paused-in13", "paused2", "paused3")])
pd_none = idle(N, "pd-none"); pd_display = idle(N, "pd-display"); pd_cv = idle(N, "pd-cv"); d_none = idle(N, "d-none"); d_display = idle(N, "d-display")
per = lambda x: (x - base) / N * 1000  # µs per carrier per frame
print(f"""
## Fitted constants (µs per carrier per frame; base frame with 0 carriers = {base:.3f} ms)

| state | ms/frame (n={N}) | µs per carrier per frame |
|---|---:|---:|
| live (timeline + running animation) | {live:.3f} | {per(live):.2f} |
| paused, timeline attached | {paused:.3f} | {per(paused):.2f} |
| paused + view-timeline:none | {pd_none:.3f} | {per(pd_none):.2f} |
| paused + scroller display:none | {pd_display:.3f} | {per(pd_display):.2f} |
| paused + scroller content-visibility:hidden | {pd_cv:.3f} | {per(pd_cv):.2f} |
| detached (view-timeline:none), not paused | {d_none:.3f} | {per(d_none):.2f} |
| display:none, not paused | {d_display:.3f} | {per(d_display):.2f} |
""")
ordinary = mut(N, "live7")
cycles = {k: mut(N, k) for k in ("resume21", "resume33", "resume45", "resume57", "resume69")}
pause_cost = med([mut(N, k) for k in ("paused", "paused2", "paused3")])
detach_cost = {k: mut(N, k) for k in ("pd-none", "pd-display", "pd-cv")}
print("## Cycle costs (main-thread ms for the whole mutation until quiescent, n=%d)\n" % N)
print(f"ordinary input change while live: {ordinary:.1f} ms ({ordinary / N * 1000:.1f} µs/carrier)")
print(f"pause (attached): {pause_cost:.1f} ms ({pause_cost / N * 1000:.1f} µs/carrier)")
for k, v in detach_cost.items(): print(f"detach after pause [{k}]: {v:.1f} ms ({v / N * 1000:.1f} µs/carrier)")
for k, v in cycles.items(): print(f"resume+re-attach [{k}]: {v:.1f} ms ({v / N * 1000:.1f} µs/carrier; extra over ordinary change {max(0, v - ordinary) / N * 1000:.1f} µs)")
resume_extra = med([max(0, v - ordinary) for v in cycles.values()]) / N * 1000
cycle_us = (pause_cost + med(list(detach_cost.values()))) / N * 1000 + resume_extra
saving_us = per(live) - per(pd_none)
print(f"\nfull off/on cycle per carrier (pause + detach + resume-extra): {cycle_us:.1f} µs; per-frame saving live -> paused-detached: {saving_us:.2f} µs/frame")
print(f"break-even frames off per cycle: {cycle_us / saving_us if saving_us > 0 else float('inf'):.1f}")

# demo prediction (coordinator's shapes): 7,782 compute timelines needed 6 of 7 frames per layer (off 1 frame, 1 cycle per layer, 12 layers);
# 1,570 token-level carriers off 78 of 85 frames, 1 cycle per token.
for label, timelines, frames_off, cycles_per_token in (("compute (off 1 frame/layer)", 7782, 12, 12), ("compute (per-hop, avg off 3 frames/layer)", 7782, 36, 12), ("token-level carriers", 1570, 78, 1)):
    gain = timelines * frames_off * saving_us / 1e6
    cost = timelines * cycles_per_token * cycle_us / 1e6
    print(f"demo {label}: saving {gain:.2f} s/token, toggling cost {cost:.2f} s/token, net {cost - gain:+.2f} s/token")
