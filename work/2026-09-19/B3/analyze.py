#!/usr/bin/env python3
"""B3 paired analysis: interleaved ref/candidate runs -> bench/paired.md + 'paired' rows in bench/results.md.
usage: analyze.py [--no-append]   (idempotent for paired.md; results.md rows are appended once, guarded by a marker)"""
import json, os, re, statistics, sys
W = "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19"
sys.path.insert(0, f"{W}/B0")
from summarize_run import summarize, EXPECTED
SEQ = [("combined", "paired-ref-1"), ("combined3", "paired-1"), ("combined", "paired-ref-2"), ("R2F", "paired-1"),
       ("combined", "paired-ref-3"), ("combined3", "paired-2"), ("combined", "paired-ref-4"), ("R2F", "paired-2"),
       ("combined", "paired-ref-5"), ("combined3", "paired-3"), ("combined", "paired-ref-6"), ("R2F", "paired-3")]
CANDS = ["combined3", "R2F"]
b0 = open(f"{W}/B0.log.md").read().splitlines()
def loads(bundle, label):
    st = en = None; t0 = t1 = None
    for ln in b0:
        if f"[{bundle}/{label}]" not in ln: continue
        m = re.search(r"load= *([\d.]+)", ln)
        if " START " in ln and m: st = float(m.group(1)); t0 = ln[2:21]
        if " END " in ln and m: en = float(m.group(1)); t1 = ln[2:21]
    return st, en, t0, t1
runs = []
for i, (b, l) in enumerate(SEQ, 1):
    p = f"{W}/bench/runs/{b}/{l}.json"
    if not os.path.exists(p): runs.append({"i": i, "bundle": b, "label": l, "missing": True}); continue
    s = summarize(p); st, en, t0, t1 = loads(b, l)
    runs.append({"i": i, "bundle": b, "label": l, "missing": False, "s": s, "load0": st, "load1": en, "t0": t0, "t1": t1,
                 "median": s["median"], "total": s["total"], "rss": s["rssPeakGenMB"], "rpt": s["cdp"]["recalcsPerToken"], "lpt": s["cdp"]["layoutsPerToken"],
                 "contended": bool(s["contended"]), "ids": s["idsOk"], "per": s["perToken"]})
def f1(x): return "–" if x is None else f"{x:.1f}"
def fs(x): return "–" if x is None else f"{x:+.1f}"
L = ["# Paired confirmation bench (B3, interleaved) — 2026-09-20", "",
     "Why: same-bundle run-to-run drift today (combined 31.3–40.5 s/token depending on background load) is as large as the fixes being measured, so each candidate run is paired with the `combined` reference run immediately before it (same harness, same machine state within ~10 min).",
     "Protocol: `B0/run_bench.sh` unchanged — headless Chrome 153, heap=1, mouseoff, passive, AC required, quiet gate (load < 3, no > 50 % CPU hog) up to 15 min then CONTENDED, 30 s power watchdog, CHROME.lock held only while a run is active. 12 untraced runs in the order ref, combined3, ref, R2F, ref, combined3, ref, R2F, ref, combined3, ref, R2F (ref = `bundles/combined`). Runs: `bench/runs/<bundle>/paired-*`.", "",
     "## Per-run", "",
     "| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | recalcs/tok | layouts/tok | load1 START | load1 END | contended |",
     "|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
for r in runs:
    if r["missing"]: L.append(f"| {r['i']} | {r['bundle']} | {r['label']} | – | MISSING | | | | | | | | | |"); continue
    L.append(f"| {r['i']} | {r['bundle']} | {r['label']} | {(r['t0'] or '?')[11:]} → {(r['t1'] or '?')[11:]} | {r['ids']} | {' '.join(f'{x:.1f}' for x in r['per'])} | {f1(r['median'])} | {f1(r['total'])} | {r['rss']} | {f1(r['rpt'])} | {f1(r['lpt'])} | {f1(r['load0'])} | {f1(r['load1'])} | {'**yes** (' + r['s']['contended'][:60] + ')' if r['contended'] else 'no'} |")
L.append("")
# pairs
pairs = {c: [] for c in CANDS}
for k in range(1, len(runs)):
    r = runs[k]; ref = runs[k - 1]
    if r["bundle"] in CANDS and ref["bundle"] == "combined" and not r["missing"] and not ref["missing"]:
        pairs[r["bundle"]].append({"ref": ref, "cand": r, "dmed": r["median"] - ref["median"], "dtot": r["total"] - ref["total"],
                                   "drpt": (r["rpt"] or 0) - (ref["rpt"] or 0), "dlpt": (r["lpt"] or 0) - (ref["lpt"] or 0), "drss": (r["rss"] or 0) - (ref["rss"] or 0)})
def mr(v): return (statistics.mean(v), min(v), max(v)) if v else (None, None, None)
L += ["## Paired differences (candidate − the ref run immediately before it)", "",
      "| candidate | pair | ref run (median / total) | cand run (median / total) | Δ median s/tok | Δ total s | Δ recalcs/tok | Δ layouts/tok | Δ RSS MB | contended (ref/cand) |",
      "|---|---|---|---|---:|---:|---:|---:|---:|---|"]
summ = {}
for c in CANDS:
    for j, p in enumerate(pairs[c], 1):
        L.append(f"| {c} | {j} | {p['ref']['label']} ({f1(p['ref']['median'])} / {f1(p['ref']['total'])}) | {p['cand']['label']} ({f1(p['cand']['median'])} / {f1(p['cand']['total'])}) | {fs(p['dmed'])} | {fs(p['dtot'])} | {fs(p['drpt'])} | {fs(p['dlpt'])} | {p['drss']:+d} | {'yes' if p['ref']['contended'] else 'no'}/{'yes' if p['cand']['contended'] else 'no'} |")
    if pairs[c]:
        summ[c] = {k: mr([p[k] for p in pairs[c]]) for k in ("dmed", "dtot", "drpt", "dlpt", "drss")}
        s = summ[c]
        L.append(f"| **{c}** | **mean [range], n={len(pairs[c])}** | | | **{fs(s['dmed'][0])} [{fs(s['dmed'][1])} … {fs(s['dmed'][2])}]** | **{fs(s['dtot'][0])} [{fs(s['dtot'][1])} … {fs(s['dtot'][2])}]** | {fs(s['drpt'][0])} [{fs(s['drpt'][1])} … {fs(s['drpt'][2])}] | {fs(s['dlpt'][0])} [{fs(s['dlpt'][1])} … {fs(s['dlpt'][2])}] | {s['drss'][0]:+.0f} | |")
L.append("")
# ref drift
refs = [r for r in runs if r["bundle"] == "combined" and not r["missing"]]
rm = [r["median"] for r in refs]; rt = [r["total"] for r in refs]
adj = [rm[k + 1] - rm[k] for k in range(len(rm) - 1)]
L += ["## Reference drift (the 6 `combined` runs)", ""]
if rm:
    L += [f"medians s/token in run order: {' '.join(f'{x:.1f}' for x in rm)} → min {min(rm):.1f}, max {max(rm):.1f}, range {max(rm)-min(rm):.1f}, mean {statistics.mean(rm):.1f}" + (f", sd {statistics.stdev(rm):.2f}" if len(rm) > 1 else ""),
          f"totals s: {' '.join(f'{x:.1f}' for x in rt)} → range {max(rt)-min(rt):.1f}; adjacent-ref differences (median s/tok): {' '.join(f'{x:+.1f}' for x in adj)} → mean |Δ| {statistics.mean(abs(a) for a in adj) if adj else 0:.1f}, max |Δ| {max((abs(a) for a in adj), default=0):.1f}",
          f"recalcs/tok: {' '.join(f1(r['rpt']) for r in refs)}; layouts/tok: {' '.join(f1(r['lpt']) for r in refs)}; load1 at START: {' '.join(f1(r['load0']) for r in refs)}; contended: {sum(r['contended'] for r in refs)}/{len(refs)}",
          f"Sequential rows for the same bundle for scale: `combined (heap=1)` 30.3 (round 1, legacy pointer), `combined (mouseoff)` 35.1 (today, u2 hit a load spike).", ""]
# verdicts
L += ["## Verdicts", ""]
noise = max((abs(a) for a in adj), default=0.0)
for c in CANDS:
    if not pairs[c]: L.append(f"**{c}**: no complete pairs."); continue
    d = [p["dmed"] for p in pairs[c]]; s = summ[c]
    same_sign = all(x < 0 for x in d) or all(x > 0 for x in d)
    excl0 = same_sign and min(abs(x) for x in d) > 0
    real = excl0 and abs(s["dmed"][0]) > noise
    cont = sum(p["ref"]["contended"] or p["cand"]["contended"] for p in pairs[c])
    verdict = ("REAL effect" if real else ("probably real but within one adjacent-ref swing" if excl0 else "NOT distinguishable from noise"))
    L.append(f"**{c} — {verdict}.** Paired Δ median = {fs(s['dmed'][0])} s/token (range {fs(s['dmed'][1])} … {fs(s['dmed'][2])}, n={len(d)}), Δ total = {fs(s['dtot'][0])} s per 8 tokens (range {fs(s['dtot'][1])} … {fs(s['dtot'][2])}); "
             f"{f'all {len(d)} pairs have the same sign' if same_sign else 'the pairs disagree in sign'} and the paired range {'excludes' if excl0 else 'includes'} zero, against a largest adjacent-ref swing of {noise:.1f} s/token and a ref spread of {max(rm)-min(rm) if rm else 0:.1f} s/token over the 6 ref runs. "
             f"Pass counts move by {fs(s['drpt'][0])} recalcs/token and {fs(s['dlpt'][0])} layouts/token (paired; these are deterministic per bundle, so any non-zero value is structural, not noise). RSS {s['drss'][0]:+.0f} MB. {cont} of {len(d)} pairs had a contended run.")
    L.append("")
open(f"{W}/bench/paired.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
# results.md rows
if "--no-append" not in sys.argv:
    res = open(f"{W}/bench/results.md").read()
    rows = []
    def row(name, rs, notes):
        per_runs = [r["per"] for r in rs if len(r["per"]) == len(EXPECTED)]
        pm = [statistics.median(col) for col in zip(*per_runs)] if per_runs else []
        n = len(pm); sl = None
        if n >= 3:
            xs = range(1, n + 1); mx = (n + 1) / 2; my = sum(pm) / n; sl = sum((x - mx) * (v - my) for x, v in zip(xs, pm)) / sum((x - mx) ** 2 for x in xs)
        stl = [r["s"]["cdp"]["style_pct"] for r in rs if r["s"]["cdp"]["style_pct"] is not None]
        cont = [r["label"] for r in rs if r["contended"]]
        if cont: notes += "; contended runs: " + ",".join(cont)
        return (f"| {name} | {'; '.join(r['ids'] for r in rs)} | {' '.join(f'{x:.1f}' for x in pm)} | {statistics.median(pm):.1f} | {sl:.2f} | {max(r['rss'] or 0 for r in rs)} | – (trace) / {statistics.median(stl):.1f} (CDP) | – | – | {notes} |")
    if refs and f"| combined (paired ref) |" not in res:
        rows.append(row("combined (paired ref)", refs, f"config: heap=1, mouseoff; B3 interleaved reference, {len(refs)} untraced runs alternating with the candidates; medians in run order {' '.join(f'{x:.1f}' for x in rm)}"))
    for c in CANDS:
        rs = [p["cand"] for p in pairs[c]]
        if rs and f"| {c} (paired) |" not in res:
            s = summ[c]
            rows.append(row(f"{c} (paired)", rs, f"config: heap=1, mouseoff; B3 paired vs the ref run immediately before each: Δ median {fs(s['dmed'][0])} s/tok [{fs(s['dmed'][1])} … {fs(s['dmed'][2])}], Δ total {fs(s['dtot'][0])} s [{fs(s['dtot'][1])} … {fs(s['dtot'][2])}], Δ recalcs/tok {fs(s['drpt'][0])}, Δ layouts/tok {fs(s['dlpt'][0])}; see bench/paired.md"))
    if rows:
        with open(f"{W}/bench/results.md", "a") as f: f.write("\n".join(rows) + "\n")
        print("\nAppended to results.md:\n" + "\n".join(rows))
