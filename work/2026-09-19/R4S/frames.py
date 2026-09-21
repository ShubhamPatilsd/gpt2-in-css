"""List every main-thread frame of a run_bundle.mjs trace: style passes (elementCount), layouts (dirty objects), animation
start/end counts, and the token window each frame belongs to. usage: frames.py <run-dir> [out.md]"""
import gzip, json, sys
from collections import Counter, defaultdict

run = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else f"{run}/frames.md"
tr = json.load(gzip.open(f"{run}/trace.json.gz", "rt"))["traceEvents"]
pr = json.load(open(f"{run}/pipeline-results.json"))
tok_ts = {int(k): v["ts"] * 1e6 for k, v in pr["tokenMetrics"].items()}
# main renderer thread = the thread with the most UpdateLayoutTree events
cnt = Counter((e.get("pid"), e.get("tid")) for e in tr if e.get("name") == "UpdateLayoutTree" and e.get("ph") == "X")
(PID, TID), _ = cnt.most_common(1)[0]
X = sorted((e for e in tr if e.get("pid") == PID and e.get("tid") == TID and e.get("ph") == "X"), key=lambda e: (e["ts"], -e.get("dur", 0)))
anim = [e for e in tr if e.get("pid") == PID and e.get("name") == "Animation" and e.get("ph") in ("b", "e")]
frames = [e for e in X if e["name"] == "ProxyMain::BeginMainFrame"]
def inside(f, e):
    return f["ts"] <= e["ts"] <= f["ts"] + f.get("dur", 0)
rows = []
j = 0
for f in frames:
    fs, fe = f["ts"], f["ts"] + f.get("dur", 0)
    passes, layouts = [], []
    for e in X:
        if e["ts"] < fs or e["ts"] > fe:
            continue
        if e["name"] == "UpdateLayoutTree":
            a = e.get("args") or {}
            ec = a.get("elementCount", (a.get("endData") or {}).get("elementCount", -1))
            passes.append(f"{ec}:{e.get('dur', 0) // 1000}")
        elif e["name"] == "Layout":
            b = (e.get("args") or {}).get("beginData") or {}
            layouts.append(f"{b.get('dirtyObjects', '?')}:{e.get('dur', 0) // 1000}")
    ab = sum(1 for e in anim if fs <= e["ts"] <= fe and e["ph"] == "b")
    ae = sum(1 for e in anim if fs <= e["ts"] <= fe and e["ph"] == "e")
    token = next((k for k in sorted(tok_ts) if fs <= tok_ts[k]), None)
    rows.append((fs, f.get("dur", 0) / 1000, passes, layouts, ab, ae, token))
per_token = defaultdict(lambda: [0, 0, 0, 0.0])
for fs, dur, passes, layouts, ab, ae, token in rows:
    if token is None or not passes:
        continue
    p = per_token[token]
    p[0] += 1; p[1] += len(passes); p[2] += len(layouts); p[3] += dur
with open(out, "w") as w:
    w.write(f"# frames — {run}\n\nmain thread pid {PID} tid {TID}; {len(frames)} BeginMainFrame; token capture ts: {sorted(tok_ts)}\n\n")
    w.write("| token | frames with a style pass | UpdateLayoutTree | Layout | frame ms |\n|---:|---:|---:|---:|---:|\n")
    for k in sorted(per_token):
        p = per_token[k]
        w.write(f"| {k} | {p[0]} | {p[1]} | {p[2]} | {p[3]:.0f} |\n")
    w.write("\n| # | t (ms) | dur | passes (elementCount:ms) | layouts (dirty:ms) | anim b/e | token |\n|---:|---:|---:|---|---|---|---|\n")
    t0 = rows[0][0] if rows else 0
    for i, (fs, dur, passes, layouts, ab, ae, token) in enumerate(rows):
        w.write(f"| {i} | {(fs - t0) / 1000:.0f} | {dur:.0f} | {' '.join(passes)} | {' '.join(layouts)} | {ab}/{ae} | {token} |\n")
print(json.dumps({k: {"frames": v[0], "ult": v[1], "layout": v[2], "frameMs": round(v[3])} for k, v in sorted(per_token.items())}))
