"""R4T mechanism fixture summary. usage: python3 analyze_mech.py results/mech.jsonl"""
import json, sys, statistics as st, collections
recs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
by = collections.defaultdict(list)
for r in recs: by[r["name"]].append(r)
med = lambda xs: st.median(xs) if xs else float("nan")
print("| variant | publishers M | anims/elem | nested | layer rules | big map | style ms / restyle | task ms | µs per publisher | first restyle ms | value ok |")
print("|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---|")
for name, rs in by.items():
    m = rs[0]["meta"]; s = med([r["styleMsMed"] for r in rs]); t = med([r["taskMsMed"] for r in rs]); f = med([r["muts"][0]["styleMs"] for r in rs])
    ok = all(r["muts"][-1]["expected"] is None or (r["muts"][-1]["value"] is not None and abs(r["muts"][-1]["value"] - r["muts"][-1]["expected"]) < 0.01) or not m["nest"] for r in rs)
    print(f"| {name} | {m['M']} | {m['anim'] or 64} | {'y' if m['nest'] else 'sib'} | {m['layers']} | {m['big']} | {s:.1f} | {t:.1f} | {s / m['M'] * 1000:.0f} | {f:.1f} | {'y' if ok else '-'} |")
g = lambda n: med([r["styleMsMed"] for r in by[n]]) if n in by else float("nan")
print(f"""
Per publishing element (style ms per restyle / M):
- siblings, 1 layer rule, small map: {g('m160-sib')/160*1000:.0f} µs (160) — includes applying its 64 declarations
- nested vs siblings (160): +{(g('m160-nest')-g('m160-sib'))/160*1000:.0f} µs/element for the inherited-map delta copy of the chain
- 12 @container layer-rule variants (nested, 160): +{(g('m160-nest-l12')-g('m160-nest'))/160*1000:.0f} µs/element
- 30k inherited props declared on the ancestor: +{g('m160-nest-big')-g('m160-nest'):.1f} ms per restyle at M=160, +{g('m20-nest-l12-big')-g('m20-sib-l12-big') if 'm20-sib-l12-big' in by else float('nan'):.1f} ms nested-vs-sib at M=20, +{g('m1200-nest-big')-g('m1200-nest'):.1f} ms at M=1200 -> a per-pass cost of the ancestor's declarations, NOT per publisher
- M=1200 nested: {g('m1200-nest')/1200*1000:.0f} µs/element; with 12 layer rules: {g('m1200-nest-l12')/1200*1000:.0f}; + big map: {g('m1200-nest-l12-big')/1200*1000:.0f}
- animated consumers (3,072 carriers changed per mutation): 48 x 64 nested = {g('a48x64-nest'):.1f} ms style / {med([r['taskMsMed'] for r in by.get('a48x64-nest', [])]):.1f} ms task vs 6 x 512 = {g('a6x512-nest'):.1f} / {med([r['taskMsMed'] for r in by.get('a6x512-nest', [])]):.1f}; with 12 layer rules + big map: {g('a48x64-nest-l12-big'):.1f} / {med([r['taskMsMed'] for r in by.get('a48x64-nest-l12-big', [])]):.1f} vs {g('a6x512-nest-l12-big'):.1f} / {med([r['taskMsMed'] for r in by.get('a6x512-nest-l12-big', [])]):.1f}
""")
