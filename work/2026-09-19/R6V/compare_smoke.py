"""R6V: compare smoke runs (ref vs ui [vs nosmooth]): ids, per-token frames / UpdateLayoutTree / Layout, RecalcStyle/Layout deltas,
and the multiset of per-pass elementCounts (the UI must add only its own few elements to the per-layer pass). usage: compare_smoke.py <run-dir>..."""
import json, re, sys, pathlib
from collections import Counter
runs = [pathlib.Path(p) for p in sys.argv[1:]]
rows = {}
for r in runs:
    pr = json.load(open(r / "pipeline-results.json"))
    fin = [json.loads(l) for l in open(r / "harness.log") if '"final"' in l][-1]
    frames = (r / "frames.md").read_text() if (r / "frames.md").exists() else ""
    per_tok = re.findall(r"^\| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$", frames, re.M)
    passes = Counter()
    for m in re.finditer(r"^\| \d+ \| \d+ \| \d+ \| ([^|]*)\|", frames, re.M):
        for p in m.group(1).split():
            passes[int(p.split(":")[0])] += 1
    rows[r.name] = {"ids": fin["tokens"], "tokenMetrics": pr.get("tokenMetrics", {}), "perTok": per_tok, "passes": passes, "times": pr.get("tokenTimesMs", {})}
names = list(rows)
print("| run | ids | token: frames / ULT / Layout | ΔRecalcStyle / ΔLayout per token | capture s |")
print("|---|---|---|---|---|")
for n in names:
    d = rows[n]
    print(f"| {n} | {d['ids']} | " + "; ".join(f"t{t}: {f}/{u}/{l}" for t, f, u, l, _ in d["perTok"]) + " | " + "; ".join(f"t{t}: {m['dRecalc']}/{m['dLayout']}" for t, m in sorted(d["tokenMetrics"].items(), key=lambda x: int(x[0]))) + " | " + "; ".join(f"{int(v)/1000:.1f}" for _, v in sorted(d["times"].items(), key=lambda x: int(x[0]))) + " |")
ref = rows[names[0]]["passes"]
for n in names[1:]:
    cur = rows[n]["passes"]
    only_ref = ref - cur; only_cur = cur - ref
    print(f"\nper-pass elementCount multiset {names[0]} vs {n}: identical {sum((ref & cur).values())} passes; only in {names[0]}: {sorted(only_ref.elements())[:40]}; only in {n}: {sorted(only_cur.elements())[:40]}")
