#!/usr/bin/env python3
"""R3A: per-pass style counters (Document::updateStyle args.counters, exposed by disabled-by-default-blink.debug) and
SelectorStats (per-selector elapsed/attempts/matches) joined to UpdateLayoutTree passes; aggregated per elementCount and per token.
usage: style_counters.py trace.json.gz anatomy.json out_prefix"""
import gzip, json, sys, collections, time, re
trace, anat_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
A = json.load(open(anat_path)); PID, TID = A["main"]
DEC = json.JSONDecoder(); T0 = time.time()
def events(path, chunk=1 << 24):
    f = gzip.open(path, "rt", encoding="utf-8", errors="replace")
    buf = f.read(chunk); i = buf.find("["); idx = i + 1
    while True:
        while True:
            while idx < len(buf) and buf[idx] in " \r\n\t,": idx += 1
            if idx >= len(buf):
                more = f.read(chunk)
                if not more: return
                buf = buf[idx:] + more; idx = 0; continue
            break
        if buf[idx] == "]": return
        try: obj, end = DEC.raw_decode(buf, idx)
        except json.JSONDecodeError:
            more = f.read(chunk)
            if not more: return
            buf = buf[idx:] + more; idx = 0; continue
        idx = end
        if idx > len(buf) // 2 and len(buf) > chunk:
            buf = buf[idx:]; idx = 0
            more = f.read(chunk)
            if more: buf += more
        yield obj
# token windows in absolute ts: anatomy stores bounds relative to trace start; recover from token_bounds_s + trace min ts... simpler: recompute from --saved-token here
saved = collections.defaultdict(list); ults = []; ups = []; sels = []
WANT = {"UpdateLayoutTree", "Document::updateStyle", "SelectorStats", "Document::recalcStyle"}
n = 0
for e in events(trace):
    n += 1
    if n % 5_000_000 == 0: print(n, f"{time.time()-T0:.0f}s", file=sys.stderr, flush=True)
    nm = e.get("name")
    if nm == "Animation" and e.get("ph") == "b":
        d = (e.get("args") or {}).get("data") or {}
        m = re.match(r"^--saved-token-(\d+)$", d.get("name") or d.get("displayName") or "")
        if m: saved[int(m.group(1))].append(e["ts"])
        continue
    if nm not in WANT or e.get("pid") != PID or e.get("tid") != TID or e.get("ph") != "X": continue
    ts, dur, a = e["ts"], e.get("dur", 0), e.get("args") or {}
    if nm == "UpdateLayoutTree":
        ec = a.get("elementCount"); 
        if ec is None: ec = (a.get("endData") or {}).get("elementCount", -1)
        ults.append((ts, dur, ec))
    elif nm == "Document::updateStyle": ups.append((ts, dur, a.get("counters") or {}))
    elif nm == "Document::recalcStyle": ups.append((ts, dur, {"_recalc": dur}))
    elif nm == "SelectorStats":
        rows = ((a.get("selector_stats") or {}).get("selector_timings") or [])
        tot = sum(r.get("elapsed (us)", 0) for r in rows); att = sum(r.get("match_attempts", 0) for r in rows); mat = sum(r.get("match_count", 0) for r in rows); fr = sum(r.get("fast_reject_count", 0) for r in rows)
        top = sorted(rows, key=lambda r: -r.get("elapsed (us)", 0))[:25]
        sels.append((ts, dur, len(rows), tot, att, mat, fr, [(r["selector"][:120], r.get("elapsed (us)", 0), r.get("match_attempts", 0), r.get("match_count", 0)) for r in top]))
print(f"streamed {n}; ult {len(ults)} updateStyle {len(ups)} selectorStats {len(sels)} {time.time()-T0:.0f}s", file=sys.stderr)
bounds = sorted((k, min(v)) for k, v in saved.items())
windows = [(bounds[i][0], bounds[i-1][1], bounds[i][1]) for i in range(1, len(bounds)) if bounds[i][0] == bounds[i-1][0] + 1]
ults.sort(); ups.sort(); sels.sort()
import bisect
def within(lst, a, b):
    i = bisect.bisect_left(lst, (a,)); r = []
    while i < len(lst) and lst[i][0] < b: r.append(lst[i]); i += 1
    return r
res = {"windows": [(k, (b - a) / 1e6) for k, a, b in windows], "tokens": {}}
for k, a, b in windows:
    passes = []
    for ts, dur, ec in within(ults, a, b):
        cs = {}; rec = 0
        for ts2, d2, c in within(ups, ts, ts + dur):
            if "_recalc" in c: rec += d2
            else:
                for kk, v in c.items(): cs[kk] = cs.get(kk, 0) + v
        # SelectorStats is emitted after the pass (in updateStyleAndLayoutIfNeededRecursive), so join it to the pass that precedes it: [pass start, next pass start)
        nxt = ults[bisect.bisect_right(ults, (ts, dur, ec))][0] if bisect.bisect_right(ults, (ts, dur, ec)) < len(ults) else b
        ss = within(sels, ts, nxt)
        s_tot = sum(s[3] for s in ss); s_att = sum(s[4] for s in ss); s_mat = sum(s[5] for s in ss); s_n = sum(s[2] for s in ss); s_fr = sum(s[6] for s in ss)
        passes.append({"t_ms": (ts - a) / 1000, "ec": ec, "dur_ms": dur / 1000, "recalc_ms": rec / 1000, "counters": cs, "sel_elapsed_ms": s_tot / 1000, "sel_attempts": s_att, "sel_matches": s_mat, "sel_fast_reject": s_fr, "sel_rows": s_n,
                       "sel_top": [t for s in ss for t in s[7]]})
    agg = collections.defaultdict(lambda: {"n": 0, "dur": 0.0, "recalc": 0.0, "sel_ms": 0.0, "sel_att": 0, "sel_mat": 0, "sel_fr": 0, "sel_rows": 0, "counters": collections.Counter(), "top": collections.Counter(), "top_att": collections.Counter()})
    tot = {"dur": 0.0, "sel_ms": 0.0, "counters": collections.Counter(), "sel_att": 0, "sel_mat": 0}
    for p in passes:
        g = agg[p["ec"]]; g["n"] += 1; g["dur"] += p["dur_ms"]; g["recalc"] += p["recalc_ms"]; g["sel_ms"] += p["sel_elapsed_ms"]; g["sel_att"] += p["sel_attempts"]; g["sel_mat"] += p["sel_matches"]; g["sel_fr"] += p["sel_fast_reject"]; g["sel_rows"] += p["sel_rows"]
        g["counters"].update(p["counters"])
        for sel, el, att, mat in p["sel_top"]: g["top"][sel] += el; g["top_att"][sel] += att
        tot["dur"] += p["dur_ms"]; tot["sel_ms"] += p["sel_elapsed_ms"]; tot["counters"].update(p["counters"]); tot["sel_att"] += p["sel_attempts"]; tot["sel_mat"] += p["sel_matches"]
    res["tokens"][k] = {"wall_s": (b - a) / 1e6, "passes_n": len(passes), "total": {"dur_ms": tot["dur"], "sel_ms": tot["sel_ms"], "sel_att": tot["sel_att"], "sel_mat": tot["sel_mat"], "counters": dict(tot["counters"])},
        "by_ec": {str(ec): {"n": g["n"], "mean_ms": g["dur"] / g["n"], "mean_recalc_ms": g["recalc"] / g["n"], "mean_sel_ms": g["sel_ms"] / g["n"], "mean_sel_att": g["sel_att"] / g["n"], "mean_sel_mat": g["sel_mat"] / g["n"], "mean_sel_fr": g["sel_fr"] / g["n"], "mean_sel_rows": g["sel_rows"] / g["n"],
                            "mean_counters": {kk: v / g["n"] for kk, v in g["counters"].items()}, "top_sel_us_per_pass": [(s, round(v / g["n"]), round(g["top_att"][s] / g["n"])) for s, v in g["top"].most_common(12)]}
                  for ec, g in sorted(agg.items(), key=lambda kv: -kv[1]["dur"])},
        "passes": passes}
json.dump(res, open(out + ".json", "w"), indent=1, default=str)
L = []; P = L.append
for k, T in res["tokens"].items():
    P(f"\n## token {k}: {T['passes_n']} passes, style {T['total']['dur_ms']:,.0f} ms, selector matching (SelectorStats elapsed) {T['total']['sel_ms']:,.1f} ms, attempts {T['total']['sel_att']:,}, matches {T['total']['sel_mat']:,}\n")
    P("counters/token: " + json.dumps({kk: round(v) for kk, v in sorted(T['total']['counters'].items())}))
    P("\n| ec | n | mean ms | recalc ms | selector ms | attempts | matches | fast-rej | elementsStyled | rulesMatched | rulesFastRejected | matchedPropertyApply | mpCacheAdded | mpCacheHit | customPropsApplied | baseStylesUsed | indepInherited | pseudo | top selectors (us/pass, attempts) |")
    P("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for ec, g in list(T["by_ec"].items())[:18]:
        c = g["mean_counters"]; f = lambda kk: f"{c.get(kk, 0):,.0f}"
        P(f"| {ec} | {g['n']} | {g['mean_ms']:.1f} | {g['mean_recalc_ms']:.1f} | {g['mean_sel_ms']:.2f} | {g['mean_sel_att']:,.0f} | {g['mean_sel_mat']:,.0f} | {g['mean_sel_fr']:,.0f} | {f('elementsStyled')} | {f('rulesMatched')} | {f('rulesFastRejected')} | {f('matchedPropertyApply')} | {f('matchedPropertyCacheAdded')} | {f('matchedPropertyCacheHit')} | {f('customPropertiesApplied')} | {f('baseStylesUsed')} | {f('independentInheritedStylesPropagated')} | {f('pseudoElementsStyled')} | " + "; ".join(f"`{s}` {v}/{a}" for s, v, a in g["top_sel_us_per_pass"][:6]) + " |")
open(out + ".md", "w").write("\n".join(L)); print("wrote", out, file=sys.stderr)
