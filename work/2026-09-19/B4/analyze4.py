#!/usr/bin/env python3
"""B4 round-3 paired analysis: interleaved R2F-ref / candidate runs -> bench/paired-round3.md (regenerated for every candidate that
has paired4-* runs) + one '<cand> (paired vs R2F)' row appended to bench/results.md per candidate named on the command line (guarded).
usage: analyze4.py [--no-append] [cand ...]   (no cands: regenerate paired-round3.md only for all candidates found)"""
import glob, json, os, re, statistics, sys
W = "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19"
sys.path.insert(0, f"{W}/B0")
from summarize_run import summarize, EXPECTED
REF = "R2F"
ORDER = ["R3F", "R3L", "combined4"]
args = [a for a in sys.argv[1:] if not a.startswith("--")]
found = sorted({os.path.basename(os.path.dirname(p)) for p in glob.glob(f"{W}/bench/runs/*/paired4-[0-9]*.json")} - {REF},
               key=lambda c: (ORDER.index(c) if c in ORDER else 99, c))
b0 = open(f"{W}/B0.log.md").read().splitlines()
def loads(bundle, label):
    st = en = None; t0 = t1 = None
    for ln in b0:
        if f"[{bundle}/{label}]" not in ln: continue
        m = re.search(r"load= *([\d.]+)", ln)
        if " START " in ln and m: st = float(m.group(1)); t0 = ln[2:21]
        if " END " in ln and m: en = float(m.group(1)); t1 = ln[2:21]
    return st, en, t0, t1
def load_run(b, l, i):
    p = f"{W}/bench/runs/{b}/{l}.json"
    if not os.path.exists(p): return {"i": i, "bundle": b, "label": l, "missing": True}
    s = summarize(p); st, en, t0, t1 = loads(b, l)
    return {"i": i, "bundle": b, "label": l, "missing": False, "s": s, "load0": st, "load1": en, "t0": t0, "t1": t1,
            "median": s["median"], "total": s["total"], "rss": s["rssPeakGenMB"], "rpt": s["cdp"]["recalcsPerToken"], "lpt": s["cdp"]["layoutsPerToken"],
            "contended": bool(s["contended"]), "ids": s["idsOk"], "per": s["perToken"]}
def f1(x): return "–" if x is None else f"{x:.1f}"
def fs(x): return "–" if x is None else f"{x:+.1f}"
def mr(v): return (statistics.mean(v), min(v), max(v)) if v else (None, None, None)
L = ["# Round-3 paired bench (B4, interleaved vs R2F) — 2026-09-20", "",
     "Why: same-bundle run-to-run drift today exceeds the effect sizes under test, so each candidate run is paired with a `R2F` reference run taken immediately before it (same harness, same machine state within ~10 min); the statistic is the paired difference.",
     "Protocol: `B0/run_bench.sh` unchanged — headless Chrome 153, heap=1, mouseoff, passive, AC required, quiet gate (load < 3, no > 50 % CPU hog) up to 15 min then CONTENDED, 30 s power watchdog, CHROME.lock held only while a run is active. Per candidate: ref, cand, ref, cand, ref, cand (3 pairs; combined4: 4 pairs), untraced. Runs: `bench/runs/R2F/paired4-ref-<cand>-<k>`, `bench/runs/<cand>/paired4-<k>`.", ""]
results = {}
for cand in found:
    np_ = 4 if cand == "combined4" else 3
    runs = []; i = 0
    for k in range(1, np_ + 1):
        i += 1; runs.append(load_run(REF, f"paired4-ref-{cand}-{k}", i))
        i += 1; runs.append(load_run(cand, f"paired4-{k}", i))
    L += [f"## {cand} — per-run", "",
          "| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | recalcs/tok | layouts/tok | load1 START | load1 END | contended |",
          "|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for r in runs:
        if r["missing"]: L.append(f"| {r['i']} | {r['bundle']} | {r['label']} | – | MISSING | | | | | | | | | |"); continue
        L.append(f"| {r['i']} | {r['bundle']} | {r['label']} | {(r['t0'] or '?')[11:]} → {(r['t1'] or '?')[11:]} | {r['ids']} | {' '.join(f'{x:.1f}' for x in r['per'])} | {f1(r['median'])} | {f1(r['total'])} | {r['rss']} | {f1(r['rpt'])} | {f1(r['lpt'])} | {f1(r['load0'])} | {f1(r['load1'])} | {'**yes** (' + r['s']['contended'][:60] + ')' if r['contended'] else 'no'} |")
    L.append("")
    pairs = []
    for k in range(1, len(runs), 2):
        ref, r = runs[k - 1], runs[k]
        if not r["missing"] and not ref["missing"]:
            pairs.append({"ref": ref, "cand": r, "dmed": r["median"] - ref["median"], "dtot": r["total"] - ref["total"],
                          "drpt": (r["rpt"] or 0) - (ref["rpt"] or 0), "dlpt": (r["lpt"] or 0) - (ref["lpt"] or 0), "drss": (r["rss"] or 0) - (ref["rss"] or 0)})
    L += [f"### {cand} — paired differences (candidate − the R2F run immediately before it)", "",
          "| pair | ref run (median / total) | cand run (median / total) | Δ median s/tok | Δ total s | Δ recalcs/tok | Δ layouts/tok | Δ RSS MB | contended (ref/cand) |",
          "|---|---|---|---:|---:|---:|---:|---:|---|"]
    for j, p in enumerate(pairs, 1):
        L.append(f"| {j} | {p['ref']['label']} ({f1(p['ref']['median'])} / {f1(p['ref']['total'])}) | {p['cand']['label']} ({f1(p['cand']['median'])} / {f1(p['cand']['total'])}) | {fs(p['dmed'])} | {fs(p['dtot'])} | {fs(p['drpt'])} | {fs(p['dlpt'])} | {p['drss']:+d} | {'yes' if p['ref']['contended'] else 'no'}/{'yes' if p['cand']['contended'] else 'no'} |")
    summ = None
    if pairs:
        summ = {k: mr([p[k] for p in pairs]) for k in ("dmed", "dtot", "drpt", "dlpt", "drss")}
        L.append(f"| **mean [range], n={len(pairs)}** | | | **{fs(summ['dmed'][0])} [{fs(summ['dmed'][1])} … {fs(summ['dmed'][2])}]** | **{fs(summ['dtot'][0])} [{fs(summ['dtot'][1])} … {fs(summ['dtot'][2])}]** | {fs(summ['drpt'][0])} [{fs(summ['drpt'][1])} … {fs(summ['drpt'][2])}] | {fs(summ['dlpt'][0])} [{fs(summ['dlpt'][1])} … {fs(summ['dlpt'][2])}] | {summ['drss'][0]:+.0f} | |")
    L.append("")
    refs = [r for r in runs if r["bundle"] == REF and not r["missing"]]
    rm = [r["median"] for r in refs]; adj = [rm[k + 1] - rm[k] for k in range(len(rm) - 1)]
    noise = max((abs(a) for a in adj), default=0.0)
    if rm:
        L.append(f"R2F reference drift within this candidate's sequence: medians {' '.join(f'{x:.1f}' for x in rm)} (range {max(rm)-min(rm):.1f}), adjacent-ref swings {' '.join(f'{x:+.1f}' for x in adj) or '–'}; "
                 f"recalcs/tok {' '.join(f1(r['rpt']) for r in refs)}; contended {sum(r['contended'] for r in refs)}/{len(refs)}. Sequential R2F row for scale: 23.6 s/token (B2, 2 of 3 runs contended).")
        L.append("")
    if not pairs:
        L.append(f"**{cand} — no complete pairs.**"); L.append("")
    else:
        d = [p["dmed"] for p in pairs]
        same_sign = all(x < 0 for x in d) or all(x > 0 for x in d)
        excl0 = same_sign and min(abs(x) for x in d) > 0
        real = excl0 and abs(summ["dmed"][0]) > noise
        cont = sum(p["ref"]["contended"] or p["cand"]["contended"] for p in pairs)
        verdict = ("REAL effect" if real else ("probably real but within one adjacent-ref swing" if excl0 else "NOT distinguishable from noise"))
        L.append(f"**{cand} — {verdict}.** Paired Δ median = {fs(summ['dmed'][0])} s/token (range {fs(summ['dmed'][1])} … {fs(summ['dmed'][2])}, n={len(d)}), Δ total = {fs(summ['dtot'][0])} s per 8 tokens (range {fs(summ['dtot'][1])} … {fs(summ['dtot'][2])}); "
                 f"{f'all {len(d)} pairs have the same sign' if same_sign else 'the pairs disagree in sign'} and the paired range {'excludes' if excl0 else 'includes'} zero, against a largest adjacent-ref swing of {noise:.1f} s/token and a ref spread of {max(rm)-min(rm) if rm else 0:.1f} s/token over the {len(refs)} ref runs. "
                 f"Pass counts move by {fs(summ['drpt'][0])} recalcs/token and {fs(summ['dlpt'][0])} layouts/token (deterministic per bundle, so any non-zero value is structural). RSS {summ['drss'][0]:+.0f} MB. {cont} of {len(d)} pairs had a contended run. ids: {'; '.join(p['cand']['ids'] for p in pairs)}.")
        L.append("")
    results[cand] = (pairs, summ, rm, refs)
open(f"{W}/bench/paired-round3.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
if "--no-append" not in sys.argv and args:
    res = open(f"{W}/bench/results.md").read(); rows = []
    for cand in args:
        if cand not in results: print(f"{cand}: no paired4 runs found"); continue
        pairs, summ, rm, refs = results[cand]
        rs = [p["cand"] for p in pairs]
        if not rs or f"| {cand} (paired vs R2F) |" in res: continue
        per_runs = [r["per"] for r in rs if len(r["per"]) == len(EXPECTED)]
        pm = [statistics.median(col) for col in zip(*per_runs)] if per_runs else []
        n = len(pm); sl = None
        if n >= 3:
            xs = range(1, n + 1); mx = (n + 1) / 2; my = sum(pm) / n; sl = sum((x - mx) * (v - my) for x, v in zip(xs, pm)) / sum((x - mx) ** 2 for x in xs)
        stl = [r["s"]["cdp"]["style_pct"] for r in rs if r["s"]["cdp"]["style_pct"] is not None]
        cont = [r["label"] for r in rs if r["contended"]]
        notes = (f"config: heap=1, mouseoff; B4 paired vs the R2F run immediately before each (n={len(pairs)}): Δ median {fs(summ['dmed'][0])} s/tok [{fs(summ['dmed'][1])} … {fs(summ['dmed'][2])}], Δ total {fs(summ['dtot'][0])} s [{fs(summ['dtot'][1])} … {fs(summ['dtot'][2])}], "
                 f"Δ recalcs/tok {fs(summ['drpt'][0])}, Δ layouts/tok {fs(summ['dlpt'][0])}; R2F ref medians {' '.join(f'{x:.1f}' for x in rm)}; see bench/paired-round3.md")
        if cont: notes += "; contended runs: " + ",".join(cont)
        rows.append(f"| {cand} (paired vs R2F) | {'; '.join(r['ids'] for r in rs)} | {' '.join(f'{x:.1f}' for x in pm)} | {statistics.median(pm):.1f} | {f'{sl:.2f}' if sl is not None else '–'} | {max(r['rss'] or 0 for r in rs)} | – (trace) / {statistics.median(stl):.1f} (CDP) | – | – | {notes} |")
    if rows:
        with open(f"{W}/bench/results.md", "a") as f: f.write("\n".join(rows) + "\n")
        print("\nAppended to results.md:\n" + "\n".join(rows))
