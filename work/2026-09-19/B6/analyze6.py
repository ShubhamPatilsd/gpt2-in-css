#!/usr/bin/env python3
"""B6 round-5 paired analysis (adapted from B5/analyze5.py): interleaved combined7-ref / candidate runs -> bench/paired-round5.md (regenerated for
every candidate that has paired6-* runs) + one '<cand> (paired vs combined7)' row appended to bench/results.md per candidate named on the command line (guarded).
Round-5 additions: RSS peak + RSS at token 8 per run (from the harness's 1 Hz rssSamples), Δ RSS peak / Δ RSS@tok8 per pair, per-token RecalcStyleCount /
LayoutCount (from the 1 Hz metricSamples, differenced at each token's capture time; the 8-token totals come from mBeforeRun→mAfterGen and are exact),
disk free / swap used at run START and END (from B6.log.md), machine-state line with median load1 AND median swap used.
Pair validity unchanged: both runs exist and ref->cand START gap <= 10 min. Verdict unchanged: paired Δ median, range vs the largest adjacent-ref swing.
usage: analyze6.py [--no-append] [--valid-count cand] [--verdict cand] [--oneline bundle label] [cand ...]"""
import glob, json, os, re, statistics, sys
from datetime import datetime
W = "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19"
sys.path.insert(0, f"{W}/B0")
from summarize_run import summarize, EXPECTED
REF = "combined7"
ORDER = ["R5H", "R5C", "R5E", "R5M"]
def npairs(c): return 4 if c.startswith("combined8") else 3
MAX_GAP_S = 600
CLEAN_LOAD = 10.0
OUT_MD = f"{W}/bench/paired-round5.md"
args = [a for a in sys.argv[1:] if not a.startswith("--")]

def per_token_extras(path):
    """RSS peak during generation, RSS at token 8 (last rendererMaxMB sample at/before token 8's capture), per-token max RSS,
    per-token recalcs/layouts from the 1 Hz metric samples (sample with the largest tResp <= token capture time; token 1 baseline = mBeforeRun)."""
    R = json.load(open(path)); ev = R.get("tokenEvents", []); tRun = R["tRun"]
    rss = [s for s in R.get("rssSamples", []) if "rendererMaxMB" in s]
    ms = sorted(R.get("metricSamples", []), key=lambda m: m.get("tResp", 0))
    def rss_at(t):
        c = [s for s in rss if s["t"] <= t]
        return c[-1]["rendererMaxMB"] if c else None
    def metric_at(t):
        c = [m for m in ms if m.get("tResp", 0) <= t]
        return c[-1] if c else R.get("mBeforeRun") or {}
    rss_tok, rc_tok, lo_tok = [], [], []
    prev_t = tRun; prev_m = R.get("mBeforeRun") or {}
    for e in ev:
        t = e["tResp"]
        win = [s["rendererMaxMB"] for s in rss if prev_t < s["t"] <= t]
        rss_tok.append(max(win) if win else rss_at(t))
        m = metric_at(t)
        rc_tok.append((m.get("RecalcStyleCount", 0) or 0) - (prev_m.get("RecalcStyleCount", 0) or 0))
        lo_tok.append((m.get("LayoutCount", 0) or 0) - (prev_m.get("LayoutCount", 0) or 0))
        prev_t, prev_m = t, m
    rss8 = rss_at(ev[7]["tResp"]) if len(ev) >= 8 else None
    return {"rssTok": rss_tok, "rss8": rss8, "rcTok": rc_tok, "loTok": lo_tok}

b6 = open(f"{W}/B6.log.md").read().splitlines() if os.path.exists(f"{W}/B6.log.md") else []
def loads(bundle, label):
    """START/END lines written by run_bench6.sh: load1, disk free MB, swap used MB, timestamps."""
    o = {"load0": None, "load1": None, "t0": None, "t1": None, "disk0": None, "disk1": None, "swap0": None, "swap1": None}
    for ln in b6:
        if f"[{bundle}/{label}]" not in ln: continue
        m = re.search(r"load= *([\d.]+)", ln); d = re.search(r"disk_free_MB=(\d+)", ln); s = re.search(r"swap_used_MB=(\d+)", ln)
        if " START " in ln and m: o["load0"] = float(m.group(1)); o["t0"] = ln[2:21]; o["disk0"] = int(d.group(1)) if d else None; o["swap0"] = int(s.group(1)) if s else None
        if " END " in ln and m: o["load1"] = float(m.group(1)); o["t1"] = ln[2:21]; o["disk1"] = int(d.group(1)) if d else None; o["swap1"] = int(s.group(1)) if s else None
    return o
def ts(s):
    try: return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception: return None
def load_run(b, l, i):
    p = f"{W}/bench/runs/{b}/{l}.json"
    if not os.path.exists(p): return {"i": i, "bundle": b, "label": l, "missing": True}
    s = summarize(p); x = per_token_extras(p); o = loads(b, l)
    return {"i": i, "bundle": b, "label": l, "missing": False, "s": s, **o, **x,
            "median": s["median"], "total": s["total"], "rss": s["rssPeakGenMB"], "rpt": s["cdp"]["recalcsPerToken"], "lpt": s["cdp"]["layoutsPerToken"],
            "contended": bool(s["contended"]), "ids": s["idsOk"], "per": s["perToken"]}
def f1(x): return "–" if x is None else f"{x:.1f}"
def fs(x): return "–" if x is None else f"{x:+.1f}"
def fi(x): return "–" if x is None else f"{x:d}"
def fsi(x): return "–" if x is None else f"{x:+d}"
def gb(mb): return "–" if mb is None else f"{mb/1024:.1f}"
def mr(v): return (statistics.mean(v), min(v), max(v)) if v else (None, None, None)

if "--oneline" in sys.argv and len(args) >= 2:
    b, l = args[0], args[1]; r = load_run(b, l, 0)
    if r["missing"]: print("MISSING"); sys.exit(1)
    print(f"tokens={r['s']['tokens']} ids={r['ids']} per={r['per']} median={r['median']} slope={r['s']['slope']} total={r['total']} rssPeak={r['rss']}MB rss@tok8={r['rss8']}MB "
          f"recalc/tok={r['rpt']} layout/tok={r['lpt']} recalcs/tok(1-8)={r['rcTok']} layouts/tok(1-8)={r['loTok']} stop={r['s']['stopReason']}"
          + (f" CONTENDED({r['s']['contended']})" if r['contended'] else ''))
    sys.exit(0)

def ks_for(cand):
    ks = set()
    for p in glob.glob(f"{W}/bench/runs/{REF}/paired6-ref-{cand}-[0-9]*.json"): ks.add(int(re.search(r"-(\d+)\.json$", p).group(1)))
    for p in glob.glob(f"{W}/bench/runs/{cand}/paired6-[0-9]*.json"): ks.add(int(re.search(r"-(\d+)\.json$", p).group(1)))
    return sorted(ks)
found = sorted({os.path.basename(os.path.dirname(p)) for p in glob.glob(f"{W}/bench/runs/*/paired6-[0-9]*.json")} |
               {re.search(r"paired6-ref-(.+)-\d+\.json$", p).group(1) for p in glob.glob(f"{W}/bench/runs/{REF}/paired6-ref-*-[0-9]*.json")},
               key=lambda c: (ORDER.index(c) if c in ORDER else 99, c))
found = [c for c in found if c != REF]

L = ["# Round-5 paired bench (B6, interleaved vs combined7) — 2026-09-24", "",
     "Why: same-bundle run-to-run drift exceeds the effect sizes under test, so each candidate run is paired with a `combined7` reference run (16.0 s/token, B5 paired; RSS peak ≈6 GB) taken immediately before it under the same CHROME.lock hold; the statistic is the paired difference. Round 5 is about memory as well as time, so RSS peak and RSS at token 8 are first-class columns.",
     "Protocol: `B6/run_bench6.sh` = `B5/run_bench5.sh` + round-5 machine gate — headless Chrome 153, heap=1, `B0_TRIGGER=keyboard` for BOTH arms, passive, untraced, AC required, quiet gate disabled (load recorded once; CONTENDED = load1 ≥ 6 or a > 90 % CPU hog), 30 s power watchdog. ONE CHROME.lock hold per pair (owner `B6 pair <cand>-<k>`, touch -c 30 s, rmdir own only), ref then cand back-to-back. Machine gate before EVERY Chrome launch: AC power AND free disk ≥ 3.0 GB AND `vm.swapusage` used < 3,000 MB (poll 60 s; if closed > 10 min under the lock the pair is abandoned and the lock released). Per candidate: ref, cand, ref, cand, ref, cand until 3 valid pairs (combined8*: 4). Runs: `bench/runs/combined7/paired6-ref-<cand>-<k>`, `bench/runs/<cand>/paired6-<k>`.",
     f"Pair validity: ref→cand START gap ≤ {MAX_GAP_S//60} min, else **INVALID** (shown, excluded from the mean/verdict; replacement pairs k = 4, 5, …).",
     "Columns: RSS peak = max renderer RSS (ps, 1 Hz) during generation; RSS@tok8 = renderer RSS sample at token 8's capture; recalcs/layouts per token = RecalcStyleCount / LayoutCount differenced at each token's capture time from the harness's 1 Hz `Performance.getMetrics` samples (the per-token split is ±1 sample; the 8-token totals /8 in the `recalcs/tok`, `layouts/tok` columns are exact). Frame counts are NOT available in untraced runs (the harness exposes them only in traces). disk/swap = free disk GB and swap used MB at run START → END.", ""]
results = {}
for cand in found:
    np_ = npairs(cand); ks = ks_for(cand)
    runs = []; i = 0
    for k in ks:
        i += 1; runs.append(load_run(REF, f"paired6-ref-{cand}-{k}", i))
        i += 1; runs.append(load_run(cand, f"paired6-{k}", i))
    L += [f"## {cand} — per-run", "",
          "| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | RSS@tok8 MB | RSS/tok MB (1–8) | recalcs/tok | layouts/tok | recalcs per token (1–8) | layouts per token (1–8) | load1 START→END | disk GB START→END | swap MB START→END | contended |",
          "|---:|---|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---|---|---|---|---|---|"]
    for r in runs:
        if r["missing"]: L.append(f"| {r['i']} | {r['bundle']} | {r['label']} | – | MISSING (not run) | | | | | | | | | | | | | | |"); continue
        L.append(f"| {r['i']} | {r['bundle']} | {r['label']} | {(r['t0'] or '?')[11:]} → {(r['t1'] or '?')[11:]} | {r['ids']} | {' '.join(f'{x:.1f}' for x in r['per'])} | {f1(r['median'])} | {f1(r['total'])} | {r['rss']} | {fi(r['rss8'])} | {' '.join(fi(x) for x in r['rssTok'])} | {f1(r['rpt'])} | {f1(r['lpt'])} | {' '.join(str(x) for x in r['rcTok'])} | {' '.join(str(x) for x in r['loTok'])} | {f1(r['load0'])} → {f1(r['load1'])} | {gb(r['disk0'])} → {gb(r['disk1'])} | {fi(r['swap0'])} → {fi(r['swap1'])} | {'**yes** (' + r['s']['contended'][:60] + ')' if r['contended'] else 'no'} |")
    present = [r for r in runs if not r["missing"]]
    lds = [x for r in present for x in (r["load0"], r["load1"]) if x is not None]
    sws = [x for r in present for x in (r["swap0"], r["swap1"]) if x is not None]
    dks = [x for r in present for x in (r["disk0"], r["disk1"]) if x is not None]
    mstate = None
    if lds:
        mstate = (f"Machine state [{cand}]: median load1 across this candidate's {len(present)} runs (START and END samples) = **{statistics.median(lds):.1f}** (range {min(lds):.1f}–{max(lds):.1f}); "
                  f"swap used median **{statistics.median(sws):.0f} MB** (range {min(sws)}–{max(sws)}); disk free {min(dks)/1024:.1f}–{max(dks)/1024:.1f} GB; " if sws and dks else
                  f"Machine state [{cand}]: median load1 across this candidate's {len(present)} runs (START and END samples) = **{statistics.median(lds):.1f}** (range {min(lds):.1f}–{max(lds):.1f}); ")
        mstate += f"{sum(r['contended'] for r in present)} of {len(present)} runs CONTENDED; runs {present[0]['t0'][11:16] if present[0]['t0'] else '?'}–{present[-1]['t1'][11:16] if present[-1]['t1'] else '?'}."
        L.append(mstate); L.append("")
    pairs = []
    for j, k in enumerate(ks):
        ref, r = runs[2 * j], runs[2 * j + 1]
        gap = None; why = ""
        if ref["missing"] or r["missing"]: why = "cand not run" if ref.get("missing") is False else "ref missing"
        else:
            a, b = ts(ref["t0"] or ""), ts(r["t0"] or "")
            if a and b: gap = (b - a).total_seconds()
            if gap is not None and gap > MAX_GAP_S: why = f"gap {gap/60:.0f} min > {MAX_GAP_S//60}"
        d = {}
        if not (ref["missing"] or r["missing"]):
            d = {"dmed": r["median"] - ref["median"], "dtot": r["total"] - ref["total"], "drpt": (r["rpt"] or 0) - (ref["rpt"] or 0),
                 "dlpt": (r["lpt"] or 0) - (ref["lpt"] or 0), "drss": (r["rss"] or 0) - (ref["rss"] or 0),
                 "drss8": (r["rss8"] - ref["rss8"]) if (r["rss8"] is not None and ref["rss8"] is not None) else None}
        pairs.append({"k": k, "ref": ref, "cand": r, "gap": gap, "valid": why == "", "why": why, **d})
    for p in pairs:
        if "dmed" in p:
            lds = [x for x in (p["ref"]["load0"], p["ref"]["load1"], p["cand"]["load0"], p["cand"]["load1"]) if x is not None]
            p["loadmax"] = max(lds) if lds else None
            p["clean"] = p["valid"] and not (p["ref"]["contended"] or p["cand"]["contended"]) and p["loadmax"] is not None and p["loadmax"] < CLEAN_LOAD
        else: p["loadmax"] = None; p["clean"] = False
    valid = [p for p in pairs if p["valid"]]; clean = [p for p in pairs if p["clean"]]
    L += [f"### {cand} — paired differences (candidate − the combined7 run immediately before it)", "",
          "| pair k | ref run (median / total / RSS peak) | cand run (median / total / RSS peak) | ref→cand start gap | valid | max load1 | Δ median s/tok | Δ total s | Δ RSS peak MB | Δ RSS@tok8 MB | Δ recalcs/tok | Δ layouts/tok | contended (ref/cand) |",
          "|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for p in pairs:
        if "dmed" not in p:
            L.append(f"| {p['k']} | {p['ref']['label']}{'' if p['ref']['missing'] else ' (' + f1(p['ref']['median']) + ' / ' + f1(p['ref']['total']) + ' / ' + str(p['ref']['rss']) + ')'} | {p['cand']['label']}{' MISSING' if p['cand']['missing'] else ''} | – | **INVALID** ({p['why']}) | | | | | | | | |"); continue
        L.append(f"| {p['k']} | {p['ref']['label']} ({f1(p['ref']['median'])} / {f1(p['ref']['total'])} / {p['ref']['rss']}) | {p['cand']['label']} ({f1(p['cand']['median'])} / {f1(p['cand']['total'])} / {p['cand']['rss']}) | {'–' if p['gap'] is None else f'{p['gap']/60:.1f} min'} | {'yes' if p['valid'] else '**INVALID** (' + p['why'] + ')'} | {f1(p['loadmax'])}{'' if p['clean'] or not p['valid'] else ' (noisy)'} | {fs(p['dmed'])} | {fs(p['dtot'])} | {p['drss']:+d} | {fsi(p['drss8'])} | {fs(p['drpt'])} | {fs(p['dlpt'])} | {'yes' if p['ref']['contended'] else 'no'}/{'yes' if p['cand']['contended'] else 'no'} |")
    summ = None
    if valid:
        summ = {kk: mr([p[kk] for p in valid if p.get(kk) is not None]) for kk in ("dmed", "dtot", "drpt", "dlpt", "drss", "drss8")}
        L.append(f"| **mean [range] over valid pairs, n={len(valid)}** | | | | | | **{fs(summ['dmed'][0])} [{fs(summ['dmed'][1])} … {fs(summ['dmed'][2])}]** | **{fs(summ['dtot'][0])} [{fs(summ['dtot'][1])} … {fs(summ['dtot'][2])}]** | **{summ['drss'][0]:+.0f} [{summ['drss'][1]:+d} … {summ['drss'][2]:+d}]** | {'–' if summ['drss8'][0] is None else f'{summ['drss8'][0]:+.0f} [{summ['drss8'][1]:+d} … {summ['drss8'][2]:+d}]'} | {fs(summ['drpt'][0])} [{fs(summ['drpt'][1])} … {fs(summ['drpt'][2])}] | {fs(summ['dlpt'][0])} [{fs(summ['dlpt'][1])} … {fs(summ['dlpt'][2])}] | |")
        if clean and len(clean) < len(valid):
            cs = {kk: mr([p[kk] for p in clean]) for kk in ("dmed", "dtot", "drss")}
            L.append(f"| *clean-load subset (no CONTENDED, load1 < {CLEAN_LOAD:.0f}), n={len(clean)}, k={','.join(str(p['k']) for p in clean)}* | | | | | | *{fs(cs['dmed'][0])} [{fs(cs['dmed'][1])} … {fs(cs['dmed'][2])}]* | *{fs(cs['dtot'][0])} [{fs(cs['dtot'][1])} … {fs(cs['dtot'][2])}]* | *{cs['drss'][0]:+.0f}* | | | | |")
    L.append("")
    refs = [p["ref"] for p in valid]
    rm = [r["median"] for r in refs]; adj = [rm[k + 1] - rm[k] for k in range(len(rm) - 1)]
    noise = max((abs(a) for a in adj), default=0.0)
    if rm:
        rr = [r["rss"] for r in refs]
        L.append(f"combined7 reference drift over the valid pairs: medians {' '.join(f'{x:.1f}' for x in rm)} (range {max(rm)-min(rm):.1f}), adjacent-ref swings {' '.join(f'{x:+.1f}' for x in adj) or '–'}; "
                 f"RSS peaks {' '.join(str(x) for x in rr)} MB (range {max(rr)-min(rr)}); recalcs/tok {' '.join(f1(r['rpt']) for r in refs)}; layouts/tok {' '.join(f1(r['lpt']) for r in refs)}; contended {sum(r['contended'] for r in refs)}/{len(refs)}. combined7 for scale: 16.0 s/token (B5 paired vs combined4, 4 pairs, medians 16.0 15.9 16.3 16.0; RSS peak 5973 MB).")
        L.append("")
    verdict = None
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
        drs = [p["drss"] for p in valid]; rss_same = all(x < 0 for x in drs) or all(x > 0 for x in drs)
        L.append(f"**{cand} — {verdict}.** Paired Δ median = {fs(summ['dmed'][0])} s/token (range {fs(summ['dmed'][1])} … {fs(summ['dmed'][2])}, n={len(d)} valid pairs{', invalid pairs excluded: k=' + ','.join(inv) if inv else ''}), Δ total = {fs(summ['dtot'][0])} s per 8 tokens (range {fs(summ['dtot'][1])} … {fs(summ['dtot'][2])}); "
                 f"{f'all {len(d)} pairs have the same sign' if same_sign else 'the pairs disagree in sign'} and the paired range {'excludes' if excl0 else 'includes'} zero, against a largest adjacent-ref swing of {noise:.1f} s/token and a ref spread of {max(rm)-min(rm) if rm else 0:.1f} s/token over the {len(refs)} ref runs. "
                 f"**Memory: Δ RSS peak = {summ['drss'][0]:+.0f} MB (range {summ['drss'][1]:+d} … {summ['drss'][2]:+d}; {'same sign in all pairs' if rss_same else 'mixed sign'}), Δ RSS@tok8 = {'–' if summ['drss8'][0] is None else f'{summ['drss8'][0]:+.0f} MB'}; candidate RSS peak {max(p['cand']['rss'] or 0 for p in valid)} MB vs ref {max(p['ref']['rss'] or 0 for p in valid)} MB (max over pairs).** "
                 f"Pass counts move by {fs(summ['drpt'][0])} recalcs/token and {fs(summ['dlpt'][0])} layouts/token (deterministic per bundle, so any non-zero value is structural). {cont} of {len(d)} pairs had a contended run. ids: {'; '.join(p['cand']['ids'] for p in valid)}."
                 + (f" Clean-load subset (no CONTENDED, load1 < {CLEAN_LOAD:.0f}; n={len(clean)}): Δ median {fs(statistics.mean([p['dmed'] for p in clean]))} s/token [{fs(min(p['dmed'] for p in clean))} … {fs(max(p['dmed'] for p in clean))}]." if clean and len(clean) < len(valid) else "")
                 + (" No pair was clean of load — read the mean with that caveat." if not clean else ""))
        L.append("")
    results[cand] = (pairs, valid, summ, rm, refs, clean, verdict, noise, mstate)

if "--valid-count" in sys.argv:
    c = args[0] if args else None
    print(len(results[c][1]) if c in results else 0); sys.exit(0)
if "--verdict" in sys.argv:
    c = args[0] if args else None
    if c not in results or not results[c][1]: print(f"VERDICT {c}: no valid pairs"); sys.exit(0)
    pairs, valid, summ, rm, refs, clean, verdict, noise, mstate = results[c]
    cm = [p["cand"]["median"] for p in valid]
    print(f"VERDICT {c} ({datetime.now():%F %T}): cand median {statistics.median(cm):.1f} s/token (runs {' '.join(f'{x:.1f}' for x in cm)}; ref medians {' '.join(f'{x:.1f}' for x in rm)}); "
          f"Δ median {fs(summ['dmed'][0])} [{fs(summ['dmed'][1])} … {fs(summ['dmed'][2])}] s/token; Δ total/8 tok {fs(summ['dtot'][0])} s [{fs(summ['dtot'][1])} … {fs(summ['dtot'][2])}]; "
          f"Δ RSS peak {summ['drss'][0]:+.0f} MB [{summ['drss'][1]:+d} … {summ['drss'][2]:+d}] (cand max {max(p['cand']['rss'] or 0 for p in valid)} vs ref max {max(p['ref']['rss'] or 0 for p in valid)}); Δ RSS@tok8 {'–' if summ['drss8'][0] is None else f'{summ['drss8'][0]:+.0f} MB'}; "
          f"Δ recalcs/tok {fs(summ['drpt'][0])}, Δ layouts/tok {fs(summ['dlpt'][0])} (cand {f1(valid[0]['cand']['rpt'])}/{f1(valid[0]['cand']['lpt'])} vs ref {f1(valid[0]['ref']['rpt'])}/{f1(valid[0]['ref']['lpt'])}); "
          f"n={len(valid)} valid pairs (k={','.join(str(p['k']) for p in valid)}), largest adjacent-ref swing {noise:.1f}; ids {'; '.join(p['cand']['ids'] for p in valid)}; verdict: {verdict}. {mstate or ''}")
    sys.exit(0)
open(OUT_MD, "w").write("\n".join(L) + "\n")
print("\n".join(L))
if "--no-append" not in sys.argv and args:
    res = open(f"{W}/bench/results.md").read(); rows = []
    for cand in args:
        if cand not in results: print(f"{cand}: no paired6 runs found"); continue
        pairs, valid, summ, rm, refs, clean, verdict, noise, mstate = results[cand]
        rs = [p["cand"] for p in valid]
        if not rs or f"| {cand} (paired vs {REF}) |" in res: continue
        per_runs = [r["per"] for r in rs if len(r["per"]) == len(EXPECTED)]
        pm = [statistics.median(col) for col in zip(*per_runs)] if per_runs else []
        n = len(pm); sl = None
        if n >= 3:
            xs = range(1, n + 1); mx = (n + 1) / 2; my = sum(pm) / n; sl = sum((x - mx) * (v - my) for x, v in zip(xs, pm)) / sum((x - mx) ** 2 for x in xs)
        stl = [r["s"]["cdp"]["style_pct"] for r in rs if r["s"]["cdp"]["style_pct"] is not None]
        cont = [r["label"] for r in rs if r["contended"]]
        inv = [str(p["k"]) for p in pairs if not p["valid"]]
        lds = [x for p in valid for r in (p["ref"], p["cand"]) for x in (r["load0"], r["load1"]) if x is not None]
        sws = [x for p in valid for r in (p["ref"], p["cand"]) for x in (r["swap0"], r["swap1"]) if x is not None]
        notes = (f"config: heap=1, trigger=keyboard (both arms); B6 paired vs the combined7 run immediately before each (n={len(valid)} valid pairs, k={','.join(str(p['k']) for p in valid)}{'; invalid excluded k=' + ','.join(inv) if inv else ''}): Δ median {fs(summ['dmed'][0])} s/tok [{fs(summ['dmed'][1])} … {fs(summ['dmed'][2])}], Δ total {fs(summ['dtot'][0])} s [{fs(summ['dtot'][1])} … {fs(summ['dtot'][2])}], "
                 f"Δ RSS peak {summ['drss'][0]:+.0f} MB [{summ['drss'][1]:+d} … {summ['drss'][2]:+d}], Δ RSS@tok8 {'–' if summ['drss8'][0] is None else f'{summ['drss8'][0]:+.0f} MB'}, RSS@tok8 (cand max) {max((r['rss8'] or 0) for r in rs)} MB, "
                 f"Δ recalcs/tok {fs(summ['drpt'][0])}, Δ layouts/tok {fs(summ['dlpt'][0])}; combined7 ref medians {' '.join(f'{x:.1f}' for x in rm)}; verdict {verdict}; machine state: median load1 {statistics.median(lds):.1f}, swap used {statistics.median(sws):.0f} MB" if lds and sws else "")
        notes += "; see bench/paired-round5.md"
        if cont: notes += "; contended runs: " + ",".join(cont)
        if clean and len(clean) < len(valid): notes += f"; clean-load subset (n={len(clean)}): Δ median {fs(statistics.mean([p['dmed'] for p in clean]))} s/tok [{fs(min(p['dmed'] for p in clean))} … {fs(max(p['dmed'] for p in clean))}]"
        if not clean: notes += "; NO clean-load pair (load1 ≥ 10 or CONTENDED in every pair)"
        rows.append(f"| {cand} (paired vs {REF}) | {'; '.join(r['ids'] for r in rs)} | {' '.join(f'{x:.1f}' for x in pm)} | {statistics.median(pm):.1f} | {f'{sl:.2f}' if sl is not None else '–'} | {max(r['rss'] or 0 for r in rs)} | – (trace) / {statistics.median(stl):.1f} (CDP) | – | – | {notes} |")
    if rows:
        with open(f"{W}/bench/results.md", "a") as f: f.write("\n".join(rows) + "\n")
        print("\nAppended to results.md:\n" + "\n".join(rows))
