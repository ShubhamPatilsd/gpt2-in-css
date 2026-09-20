#!/usr/bin/env python3
"""R2G: summarise fixture results (results/<variant>.jsonl from run.mjs) and fit the :has() traversal cost.

usage: python3 analyze.py [results_dir]
"""
import glob, json, os, statistics as st, sys

RES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
CORE, BODY, SVG = 16893, 68045 + 70, 581  # fixture subtree sizes (controller desc., body desc. approx, svg + chain)
LOOP_ARGS, TOKEN_ARGS, BLOCK_ARGS, ACK_ARGS = 184, 7, 2, 88


def med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return st.median(xs) if xs else float("nan")


rows = {}
for f in sorted(glob.glob(os.path.join(RES, "*.jsonl"))):
    recs = [json.loads(l) for l in open(f) if l.strip()]
    ok = [r for r in recs if not r.get("error")]
    if not ok:
        rows[os.path.basename(f)[:-6]] = {"error": recs[-1].get("error", "?")[:120] if recs else "no records"}
        continue
    passes = []
    for r in ok:
        ev = r["trace"]["updateLayoutTree"]["events"]
        passes.append([(e["elementCount"], round(e["durUs"] / 1000, 1)) for e in ev])
    rows[ok[0]["variant"]] = {
        "trials": len(ok),
        "ultMs": med([r["trace"]["updateLayoutTree"]["totalUs"] / 1000 for r in ok]),
        "ultN": med([r["trace"]["updateLayoutTree"]["count"] for r in ok]),
        "elems": med([sum(x or 0 for x in r["trace"]["updateLayoutTree"]["elementCounts"]) for r in ok]),
        "layoutMs": med([r["trace"]["layout"]["totalUs"] / 1000 for r in ok]),
        "animSelfMs": med([r["trace"]["animation"]["bucket"]["selfUs"] / 1000 for r in ok]),
        "busyMs": med([r["trace"]["topLevelBusyUs"] / 1000 for r in ok]),
        "rsdMs": med([r["metricsDelta"]["RecalcStyleDurationMs"] for r in ok]),
        "verified": sum(1 for r in ok if r.get("verify", {}).get("changed")),
        "passes": passes[0],
        "mutation": ok[0].get("mutation"),
        "rss": med([r.get("rssAfterMutation", {}).get("maxRendererRssMB") or float("nan") for r in ok]),
        "errors": len(recs) - len(ok),
    }

print(f"| variant | trials | ULT n | ULT ms | elems | Layout ms | Anim self ms | busy ms | RSD ms | verified | RSS MB | passes (elementCount:ms) trial 0 |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|")
for v, r in rows.items():
    if "error" in r:
        print(f"| {v} | ERROR {r['error']} |")
        continue
    print(f"| {v} | {r['trials']} | {r['ultN']:.0f} | {r['ultMs']:.1f} | {r['elems']:.0f} | {r['layoutMs']:.1f} | {r['animSelfMs']:.1f} | {r['busyMs']:.1f} | {r['rsdMs']:.1f} | {r['verified']}/{r['trials']} | {r['rss']:.0f} | {' '.join(f'{c}:{m}' for c, m in r['passes'][:6])} |")


def ult(v):
    return rows.get(v, {}).get("ultMs", float("nan"))


print("\n## :has() traversal fit (pass-advance family)")
visits = {
    "pa-demo": LOOP_ARGS * CORE + (TOKEN_ARGS + BLOCK_ARGS) * BODY,
    "pa-demo-anims": LOOP_ARGS * (CORE + 1545) + (TOKEN_ARGS + BLOCK_ARGS) * (BODY + 1545),
    "pa-corefill": LOOP_ARGS * CORE + (TOKEN_ARGS + BLOCK_ARGS) * (BODY - 51149),
    "pa-nofill": LOOP_ARGS * (CORE - 16311) + (TOKEN_ARGS + BLOCK_ARGS) * (BODY - 51149 - 16311),
    "pa-fixed": LOOP_ARGS * SVG + TOKEN_ARGS * 12 + BLOCK_ARGS * 3,
    "pa-nohas": 0, "pa-nohas-nosvg": 0, "pa-nohas-anims": 0,
}
base = ult("pa-nohas")
for v, n in visits.items():
    if v in rows and "error" not in rows[v]:
        extra = ult(v) - (ult("pa-nohas-anims") if v.endswith("-anims") else base)
        print(f"{v:16s} ULT {ult(v):7.1f} ms  predicted visits {n / 1e6:5.2f} M  extra vs no-:has() {extra:7.1f} ms  -> {1e6 * extra / n if n else float('nan'):6.1f} ns/visit")
if "pa-demo" in rows and "pa-nofill" in rows:
    slope = (ult("pa-demo") - ult("pa-nofill")) / (visits["pa-demo"] - visits["pa-nofill"]) * 1e6
    print(f"slope demo-vs-nofill: {slope:.1f} ns/visit")
print("\n## svg family: ancestor :has() per <g> (88 args x core subtree)")
if "svg-demo" in rows and "svg-nohas" in rows:
    d = ult("svg-demo") - ult("svg-nohas")
    print(f"svg-demo - svg-nohas = {d:.1f} ms over {ACK_ARGS * CORE / 1e6:.2f} M visits -> {1e6 * d / (ACK_ARGS * CORE):.1f} ns/visit; svg-nohas - svg-plain = {ult('svg-nohas') - ult('svg-plain'):.1f} ms (SMIL/<g> vs <i>)")
print("\n## reader family (1,538 timeline anims)")
for v in ("rd-unrelated", "rd-unrelated-split", "rd-change", "rd-change-split", "rd-change-nosvg", "rd-change-latch"):
    if v in rows and "error" not in rows[v]:
        print(f"{v:20s} ULT {ult(v):7.1f} ms  passes {rows[v]['passes'][:4]}  layout {rows[v]['layoutMs']:.1f} ms  anim self {rows[v]['animSelfMs']:.1f} ms")
