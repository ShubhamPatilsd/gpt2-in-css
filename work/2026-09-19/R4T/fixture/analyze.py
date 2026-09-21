"""R4T: per-frame servicing cost vs structure. usage: python3 analyze.py results/<tag>.jsonl [more.jsonl]"""
import json, sys, statistics as st, collections
recs = [json.loads(l) for p in sys.argv[1:] for l in open(p) if l.strip()]
by = collections.defaultdict(list)
for r in recs: by[r["name"]].append(r)
med = lambda xs: st.median(xs) if xs else float("nan")
ORDER = ["ctrl-n0", "base", "n1000", "above20", "above40", "above60", "below5", "below20", "below40", "below60", "scr12", "scr96", "iblock", "inline", "scope-root", "cons16", "heavy-a40", "bigdom100k", "change50", "demo", "demo-contain", "demo-cv", "demo-below20", "demo-change50"]
names = [n for n in ORDER if n in by] + [n for n in by if n not in ORDER]
def col(n, f):
    xs = []
    for r in by[n]:
        try: v = f(r)
        except Exception: v = None
        if v is not None and v == v: xs.append(v)
    return xs
rows = {}
for n in names:
    a = lambda r: r["anatomy"]
    frames = col(n, lambda r: a(r)["frames"])
    row = dict(
        trials=len(by[n]), n=by[n][0]["meta"]["n"], ok="/".join(str(r["values"]["ok"]) if r["values"] else "-" for r in by[n]),
        frames=med(frames), fps=med(col(n, lambda r: a(r)["frames"] / (a(r)["windowMs"] / 1000))),
        busy=med(col(n, lambda r: a(r)["busyPerFrame"])), dur=med(col(n, lambda r: a(r)["med"]["dur"])),
        idle=med(col(n, lambda r: r["idle"]["taskMs"] / (r["idle"]["wallMs"] / 1000) / (a(r)["frames"] / (a(r)["windowMs"] / 1000)))),  # metrics-based ms per frame using traced fps
        animate=med(col(n, lambda r: a(r)["med"]["animate"])), ssaSelf=med(col(n, lambda r: a(r)["med"]["ssaSelf"])),
        svcN=med(col(n, lambda r: a(r)["med"]["svcN"])), svcMs=med(col(n, lambda r: a(r)["med"]["svcMs"])),
        ulSelf=med(col(n, lambda r: a(r)["med"]["ulSelf"])), ult=med(col(n, lambda r: a(r)["med"]["ultMs"])), ultN=med(col(n, lambda r: a(r)["med"]["ultN"])),
        layout=med(col(n, lambda r: a(r)["med"]["layoutMs"])), layoutN=med(col(n, lambda r: a(r)["med"]["layoutN"])),
        paintLC=med(col(n, lambda r: a(r)["med"]["paintLC"])), prepaint=med(col(n, lambda r: a(r)["med"]["prePaint"])), comp=med(col(n, lambda r: a(r)["med"]["compInputs"])),
        elems=collections.Counter(k for r in by[n] for k, v in a(r).get("elemHist", {}).items() for _ in range(v)).most_common(2),
        rss=med(col(n, lambda r: r["rssKb"] / 1024)), load=med(col(n, lambda r: r["loadMs"])),
    )
    rows[n] = row
base0 = rows.get("ctrl-n0", {}).get("busy", 0) or 0
print(f"# R4T fixture — {len(recs)} trials; medians over trials of per-frame medians (ms/frame); control frame (0 carriers) busy = {base0:.3f} ms\n")
print("| variant | N | ok | fps | frame dur | busy/frame | idle(metrics) | animate | ssa self | svc n | svc ms | UL self | ULT n:ms | layout n:ms | paintLC | prepaint+comp | passes(elems) | µs/carrier/frame (busy−ctrl) | RSS MB |")
print("|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---|---:|---:|")
for n in names:
    r = rows[n]; per = (r["busy"] - base0) / r["n"] * 1000 if r["n"] else float("nan")
    print(f"| {n} | {r['n']} | {r['ok']} | {r['fps']:.0f} | {r['dur']:.2f} | {r['busy']:.2f} | {r['idle']:.2f} | {r['animate']:.2f} | {r['ssaSelf']:.2f} | {r['svcN']:.0f} | {r['svcMs']:.2f} | {r['ulSelf']:.2f} | {r['ultN']:.0f}:{r['ult']:.2f} | {r['layoutN']:.0f}:{r['layout']:.2f} | {r['paintLC']:.2f} | {r['prepaint']+r['comp']:.2f} | {' / '.join(k for k,_ in r['elems'])} | {per:.2f} | {r['rss']:.0f} |")
# fits
def fit(xs, ys):
    n = len(xs); mx, my = sum(xs) / n, sum(ys) / n
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / max(1e-9, sum((x - mx) ** 2 for x in xs)); a = my - b * mx
    ss = sum((y - my) ** 2 for y in ys); sr = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    return a, b, 1 - sr / ss if ss else float("nan")
print("\n## Fits (busy ms/frame vs knob, N=2000)\n")
for label, pts in (("scroller depth (wrappers above)", [("base", 2), ("above20", 20), ("above40", 40), ("above60", 60)]),
                   ("subject depth below scroller (wrappers between scroller and track)", [("base", 0), ("below5", 5), ("below20", 20), ("below40", 40), ("below60", 60)])):
    pts = [(rows[k]["busy"], v) for k, v in pts if k in rows]
    if len(pts) >= 2:
        a, b, r2 = fit([v for _, v in pts], [y for y, _ in pts])
        print(f"- {label}: busy = {a:.3f} ms + {b*1000:.1f} µs/frame per level (= {b*1000/2000*1000:.2f} ns per carrier per level; R² {r2:.2f})")
if "base" in rows and "n1000" in rows:
    a, b, _ = fit([0, 1000, 2000], [base0, rows["n1000"]["busy"], rows["base"]["busy"]])
    print(f"- carriers: busy = {a:.3f} ms + {b*1000:.2f} µs per carrier (control, n1000, base)")
for k in names:
    if k in ("base", "ctrl-n0"): continue
    print(f"- {k}: {rows[k]['busy'] / rows['base']['busy']:.2f}× base busy/frame; animate {rows[k]['animate']/rows['base']['animate']:.2f}×, UL self {rows[k]['ulSelf']/max(1e-6,rows['base']['ulSelf']):.2f}×, svc calls {rows[k]['svcN']:.0f}")
