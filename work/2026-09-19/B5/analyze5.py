#!/usr/bin/env python3
"""B5 round-4 paired analysis (adapted from B4/analyze4.py): interleaved combined4-ref / candidate runs -> bench/paired-round4.md (regenerated for
every candidate that has paired5-* runs) + one '<cand> (paired vs combined4)' row appended to bench/results.md per candidate named on the command line (guarded).
Pair validity (coordinator 2026-09-21 02:1x): a pair is VALID only if both runs exist and the ref->cand START gap is <= 10 min (MAX_GAP_S); invalid pairs are
shown but excluded from the mean/verdict. Pair index k is discovered from the files (k >= 1, unbounded: replacement pairs use k = np+1, ...).
usage: analyze5.py [--no-append] [--valid-count] [cand ...]   (--valid-count: print only the number of valid pairs for the one candidate named)"""
import glob, json, os, re, statistics, sys
from datetime import datetime
W = "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19"
sys.path.insert(0, f"{W}/B0")
from summarize_run import summarize, EXPECTED
REF = "combined4"
ORDER = ["R4S", "R4T", "combined5", "combined6", "combined7", "R4T2", "R4T-b"]
# "<name>-b" = a second block of pairs for bundle <name> (coordinator 03:4x: R4T-b at the END of the queue); cand runs live in bench/runs/<name>/paired5-b-<k>.json
def bundle_of(c): return c[:-2] if c.endswith("-b") else c
def cand_label(c, k): return f"paired5-b-{k}" if c.endswith("-b") else f"paired5-{k}"
NPAIRS = {"combined6": 4, "combined7": 4}
MAX_GAP_S = 600
CLEAN_LOAD = 10.0   # a pair is "clean" if valid, neither run CONTENDED and load1 (START/END of both runs) stayed < 10
args = [a for a in sys.argv[1:] if not a.startswith("--")]
quiet = "--valid-count" in sys.argv
def ks_for(cand):
    ks = set()
    for p in glob.glob(f"{W}/bench/runs/{REF}/paired5-ref-{cand}-[0-9]*.json"): ks.add(int(re.search(r"-(\d+)\.json$", p).group(1)))
    pre = "paired5-b" if cand.endswith("-b") else "paired5"
    for p in glob.glob(f"{W}/bench/runs/{bundle_of(cand)}/{pre}-[0-9]*.json"): ks.add(int(re.search(r"-(\d+)\.json$", p).group(1)))
    return sorted(ks)
found = sorted({os.path.basename(os.path.dirname(p)) for p in glob.glob(f"{W}/bench/runs/*/paired5-[0-9]*.json")} |
               {os.path.basename(os.path.dirname(p)) + "-b" for p in glob.glob(f"{W}/bench/runs/*/paired5-b-[0-9]*.json")} | 
               {re.search(r"paired5-ref-(.+)-\d+\.json$", p).group(1) for p in glob.glob(f"{W}/bench/runs/{REF}/paired5-ref-*-[0-9]*.json")},
               key=lambda c: (ORDER.index(c) if c in ORDER else 99, c))
found = [c for c in found if c != REF]
b0 = open(f"{W}/B0.log.md").read().splitlines()
def loads(bundle, label):
    st = en = None; t0 = t1 = None
    for ln in b0:
        if f"[{bundle}/{label}]" not in ln: continue
        m = re.search(r"load= *([\d.]+)", ln)
        if " START " in ln and m: st = float(m.group(1)); t0 = ln[2:21]
        if " END " in ln and m: en = float(m.group(1)); t1 = ln[2:21]
    return st, en, t0, t1
def ts(s): 
    try: return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception: return None
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
L = ["# Round-4 paired bench (B5, interleaved vs combined4) — 2026-09-21", "",
     "Why: same-bundle run-to-run drift today exceeds the effect sizes under test, so each candidate run is paired with a `combined4` reference run (18.2 s/token, B4 paired) taken immediately before it (same harness, same machine state within ~10 min); the statistic is the paired difference.",
     "Protocol: `B5/run_bench5.sh` = `B0/run_bench.sh` + round-4 CHROME.lock owner protocol — headless Chrome 153, heap=1, `B0_TRIGGER=keyboard` for BOTH arms (no mouse event, so mouseoff is moot), passive, AC required, quiet gate disabled (load recorded once; CONTENDED = load1 ≥ 6 or a > 90 % CPU hog), 30 s power watchdog, CHROME.lock held only while a run is active. Per candidate: ref, cand, ref, cand, ref, cand (3 pairs; combined6/combined7: 4 pairs), untraced. Runs: `bench/runs/combined4/paired5-ref-<cand>-<k>`, `bench/runs/<cand>/paired5-<k>`.",
     f"Pair validity (coordinator, 02:1x): the interleaving assumption needs the candidate to start soon after its reference — a pair whose ref→cand START gap exceeds {MAX_GAP_S//60} min (other agents' 32-token runs held CHROME.lock in between) is marked **INVALID** and excluded from the mean/verdict; the driver runs replacement pairs (k = 4, 5, …) until 3 (combined6/7: 4) valid pairs exist. From pair k ≥ 3 of combined5 the candidate arm gives up (rc 6) if it cannot take the lock within 390 s of the ref's end, so a late candidate is never run.",
     "Contended flags: every R4S-sequence run (01:00–01:16) was flagged CONTENDED by an orphaned R4C `populations.py` at ≈100 % CPU (both arms saw it; the coordinator killed it at 01:17) — runs after 01:17 are clean unless flagged in the table.", ""]
results = {}
for cand in found:
    np_ = NPAIRS.get(cand, 3); ks = ks_for(cand)
    runs = []; i = 0
    for k in ks:
        i += 1; runs.append(load_run(REF, f"paired5-ref-{cand}-{k}", i))
        i += 1; runs.append(load_run(bundle_of(cand), cand_label(cand, k), i))
    L += [f"## {cand} — per-run", "",
          "| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | recalcs/tok | layouts/tok | load1 START | load1 END | contended |",
          "|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for r in runs:
        if r["missing"]: L.append(f"| {r['i']} | {r['bundle']} | {r['label']} | – | MISSING (not run) | | | | | | | | | |"); continue
        L.append(f"| {r['i']} | {r['bundle']} | {r['label']} | {(r['t0'] or '?')[11:]} → {(r['t1'] or '?')[11:]} | {r['ids']} | {' '.join(f'{x:.1f}' for x in r['per'])} | {f1(r['median'])} | {f1(r['total'])} | {r['rss']} | {f1(r['rpt'])} | {f1(r['lpt'])} | {f1(r['load0'])} | {f1(r['load1'])} | {'**yes** (' + r['s']['contended'][:60] + ')' if r['contended'] else 'no'} |")
    present = [r for r in runs if not r["missing"]]
    lds = [x for r in present for x in (r["load0"], r["load1"]) if x is not None]
    if lds:
        L.append(f"Machine state: median load1 across this candidate's {len(present)} runs (START and END samples) = **{statistics.median(lds):.1f}** (range {min(lds):.1f}–{max(lds):.1f}); {sum(r['contended'] for r in present)} of {len(present)} runs CONTENDED; runs {present[0]['t0'][11:16] if present[0]['t0'] else '?'}–{present[-1]['t1'][11:16] if present[-1]['t1'] else '?'}.")
        L.append("")
    pairs = []
    for j, k in enumerate(ks):
        ref, r = runs[2 * j], runs[2 * j + 1]
        gap = None; why = ""
        if ref["missing"] or r["missing"]: why = "cand not run" if ref.get("missing") is False else "ref missing"
        else:
            a, b = ts(ref["t0"] or ""), ts(r["t0"] or "")
            if a and b: gap = (b - a).total_seconds()
            if gap is not None and gap > MAX_GAP_S: why = f"gap {gap/60:.0f} min > {MAX_GAP_S//60}"
        pairs.append({"k": k, "ref": ref, "cand": r, "gap": gap, "valid": why == "", "why": why,
                      **({"dmed": r["median"] - ref["median"], "dtot": r["total"] - ref["total"], "drpt": (r["rpt"] or 0) - (ref["rpt"] or 0),
                          "dlpt": (r["lpt"] or 0) - (ref["lpt"] or 0), "drss": (r["rss"] or 0) - (ref["rss"] or 0)} if not (ref["missing"] or r["missing"]) else {})})
    for p in pairs:
        if "dmed" in p:
            lds = [x for x in (p["ref"]["load0"], p["ref"]["load1"], p["cand"]["load0"], p["cand"]["load1"]) if x is not None]
            p["loadmax"] = max(lds) if lds else None
            p["clean"] = p["valid"] and not (p["ref"]["contended"] or p["cand"]["contended"]) and p["loadmax"] is not None and p["loadmax"] < CLEAN_LOAD
        else: p["loadmax"] = None; p["clean"] = False
    valid = [p for p in pairs if p["valid"]]; clean = [p for p in pairs if p["clean"]]
    L += [f"### {cand} — paired differences (candidate − the combined4 run immediately before it)", "",
          "| pair k | ref run (median / total) | cand run (median / total) | ref→cand start gap | valid | max load1 | Δ median s/tok | Δ total s | Δ recalcs/tok | Δ layouts/tok | Δ RSS MB | contended (ref/cand) |",
          "|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|"]
    for p in pairs:
        if "dmed" not in p:
            L.append(f"| {p['k']} | {p['ref']['label']}{'' if p['ref']['missing'] else ' (' + f1(p['ref']['median']) + ' / ' + f1(p['ref']['total']) + ')'} | {p['cand']['label']}{' MISSING' if p['cand']['missing'] else ''} | – | **INVALID** ({p['why']}) | | | | | | | |"); continue
        L.append(f"| {p['k']} | {p['ref']['label']} ({f1(p['ref']['median'])} / {f1(p['ref']['total'])}) | {p['cand']['label']} ({f1(p['cand']['median'])} / {f1(p['cand']['total'])}) | {'–' if p['gap'] is None else f'{p['gap']/60:.1f} min'} | {'yes' if p['valid'] else '**INVALID** (' + p['why'] + ')'} | {f1(p['loadmax'])}{'' if p['clean'] or not p['valid'] else ' (noisy)'} | {fs(p['dmed'])} | {fs(p['dtot'])} | {fs(p['drpt'])} | {fs(p['dlpt'])} | {p['drss']:+d} | {'yes' if p['ref']['contended'] else 'no'}/{'yes' if p['cand']['contended'] else 'no'} |")
    summ = None
    if valid:
        summ = {kk: mr([p[kk] for p in valid]) for kk in ("dmed", "dtot", "drpt", "dlpt", "drss")}
        L.append(f"| **mean [range] over valid pairs, n={len(valid)}** | | | | | | **{fs(summ['dmed'][0])} [{fs(summ['dmed'][1])} … {fs(summ['dmed'][2])}]** | **{fs(summ['dtot'][0])} [{fs(summ['dtot'][1])} … {fs(summ['dtot'][2])}]** | {fs(summ['drpt'][0])} [{fs(summ['drpt'][1])} … {fs(summ['drpt'][2])}] | {fs(summ['dlpt'][0])} [{fs(summ['dlpt'][1])} … {fs(summ['dlpt'][2])}] | {summ['drss'][0]:+.0f} | |")
        if clean and len(clean) < len(valid):
            cs = {kk: mr([p[kk] for p in clean]) for kk in ("dmed", "dtot")}
            L.append(f"| *clean-load subset (no CONTENDED, load1 < {CLEAN_LOAD:.0f}), n={len(clean)}, k={','.join(str(p['k']) for p in clean)}* | | | | | | *{fs(cs['dmed'][0])} [{fs(cs['dmed'][1])} … {fs(cs['dmed'][2])}]* | *{fs(cs['dtot'][0])} [{fs(cs['dtot'][1])} … {fs(cs['dtot'][2])}]* | | | | |")
    L.append("")
    refs = [p["ref"] for p in valid]
    rm = [r["median"] for r in refs]; adj = [rm[k + 1] - rm[k] for k in range(len(rm) - 1)]
    noise = max((abs(a) for a in adj), default=0.0)
    if rm:
        L.append(f"combined4 reference drift over the valid pairs: medians {' '.join(f'{x:.1f}' for x in rm)} (range {max(rm)-min(rm):.1f}), adjacent-ref swings {' '.join(f'{x:+.1f}' for x in adj) or '–'}; "
                 f"recalcs/tok {' '.join(f1(r['rpt']) for r in refs)}; contended {sum(r['contended'] for r in refs)}/{len(refs)}. combined4 for scale: 18.2 s/token (B4 paired, 4 cand runs, medians 18.4 18.1 18.1 18.5).")
        L.append("")
    if not valid:
        L.append(f"**{cand} — no valid pairs yet** ({len(pairs)} pair(s) on disk, all invalid)."); L.append("")
    else:
        d = [p["dmed"] for p in valid]
        same_sign = all(x < 0 for x in d) or all(x > 0 for x in d)
        excl0 = same_sign and min(abs(x) for x in d) > 0
        real = excl0 and abs(summ["dmed"][0]) > noise
        cont = sum(p["ref"]["contended"] or p["cand"]["contended"] for p in valid)
        verdict = ("REAL effect" if real else ("probably real but within one adjacent-ref swing" if excl0 else "NOT distinguishable from noise"))
        inv = [str(p["k"]) for p in pairs if not p["valid"]]
        L.append(f"**{cand} — {verdict}.** Paired Δ median = {fs(summ['dmed'][0])} s/token (range {fs(summ['dmed'][1])} … {fs(summ['dmed'][2])}, n={len(d)} valid pairs{', invalid pairs excluded: k=' + ','.join(inv) if inv else ''}), Δ total = {fs(summ['dtot'][0])} s per 8 tokens (range {fs(summ['dtot'][1])} … {fs(summ['dtot'][2])}); "
                 f"{f'all {len(d)} pairs have the same sign' if same_sign else 'the pairs disagree in sign'} and the paired range {'excludes' if excl0 else 'includes'} zero, against a largest adjacent-ref swing of {noise:.1f} s/token and a ref spread of {max(rm)-min(rm) if rm else 0:.1f} s/token over the {len(refs)} ref runs. "
                 f"Pass counts move by {fs(summ['drpt'][0])} recalcs/token and {fs(summ['dlpt'][0])} layouts/token (deterministic per bundle, so any non-zero value is structural). RSS {summ['drss'][0]:+.0f} MB. {cont} of {len(d)} pairs had a contended run. ids: {'; '.join(p['cand']['ids'] for p in valid)}."
                 + (f" Clean-load subset (no CONTENDED, load1 < {CLEAN_LOAD:.0f}; n={len(clean)}): Δ median {fs(statistics.mean([p['dmed'] for p in clean]))} s/token [{fs(min(p['dmed'] for p in clean))} … {fs(max(p['dmed'] for p in clean))}]." if clean and len(clean) < len(valid) else "")
                 + (" No pair was clean of load (user activity / other agents' builds during the sequence) — read the mean with that caveat." if not clean else ""))
        L.append("")
    results[cand] = (pairs, valid, summ, rm, refs, clean)
if quiet:
    c = args[0] if args else None
    print(len(results[c][1]) if c in results else 0); sys.exit(0)
open(f"{W}/bench/paired-round4.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
if "--no-append" not in sys.argv and args:
    res = open(f"{W}/bench/results.md").read(); rows = []
    for cand in args:
        if cand not in results: print(f"{cand}: no paired5 runs found"); continue
        pairs, valid, summ, rm, refs, clean = results[cand]
        rs = [p["cand"] for p in valid]
        if not rs or f"| {cand} (paired vs combined4) |" in res: continue
        per_runs = [r["per"] for r in rs if len(r["per"]) == len(EXPECTED)]
        pm = [statistics.median(col) for col in zip(*per_runs)] if per_runs else []
        n = len(pm); sl = None
        if n >= 3:
            xs = range(1, n + 1); mx = (n + 1) / 2; my = sum(pm) / n; sl = sum((x - mx) * (v - my) for x, v in zip(xs, pm)) / sum((x - mx) ** 2 for x in xs)
        stl = [r["s"]["cdp"]["style_pct"] for r in rs if r["s"]["cdp"]["style_pct"] is not None]
        cont = [r["label"] for r in rs if r["contended"]]
        inv = [str(p["k"]) for p in pairs if not p["valid"]]
        notes = (f"config: heap=1, trigger=keyboard (both arms); B5 paired vs the combined4 run immediately before each (n={len(valid)} valid pairs, k={','.join(str(p['k']) for p in valid)}{'; invalid excluded k=' + ','.join(inv) if inv else ''}): Δ median {fs(summ['dmed'][0])} s/tok [{fs(summ['dmed'][1])} … {fs(summ['dmed'][2])}], Δ total {fs(summ['dtot'][0])} s [{fs(summ['dtot'][1])} … {fs(summ['dtot'][2])}], "
                 f"Δ recalcs/tok {fs(summ['drpt'][0])}, Δ layouts/tok {fs(summ['dlpt'][0])}; combined4 ref medians {' '.join(f'{x:.1f}' for x in rm)}; see bench/paired-round4.md")
        if cont: notes += "; contended runs: " + ",".join(cont)
        if clean and len(clean) < len(valid): notes += f"; clean-load subset (n={len(clean)}): Δ median {fs(statistics.mean([p['dmed'] for p in clean]))} s/tok [{fs(min(p['dmed'] for p in clean))} … {fs(max(p['dmed'] for p in clean))}]"
        if not clean: notes += "; NO clean-load pair (load1 ≥ 10 or CONTENDED in every pair)"
        rows.append(f"| {cand} (paired vs combined4) | {'; '.join(r['ids'] for r in rs)} | {' '.join(f'{x:.1f}' for x in pm)} | {statistics.median(pm):.1f} | {f'{sl:.2f}' if sl is not None else '–'} | {max(r['rss'] or 0 for r in rs)} | – (trace) / {statistics.median(stl):.1f} (CDP) | – | – | {notes} |")
    if rows:
        with open(f"{W}/bench/results.md", "a") as f: f.write("\n".join(rows) + "\n")
        print("\nAppended to results.md:\n" + "\n".join(rows))
