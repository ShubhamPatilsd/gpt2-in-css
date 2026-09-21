"""R4V: per-token RSS saw-tooth (GC/purge cadence) and main-thread CPU (ThreadTime) vs wall, from the harness JSONs."""
import json, sys, numpy as np
runs = {
 "c32c-hello": "R4D/run-combined4-c32c/c32c-run1.json", "c32c-p40": "R4M/run-combined4-c32c/c32c-runC-p40.json",
 "c6-hello": "R4M/run-combined6-c32/c32-run1.json", "c6-p40": "R4M/run-combined6-c32/c32-run2-p40.json",
 "c7-p40": "R4M/run-combined7-c32/c32-runA-p40.json", "c7-hello": "R4M/run-combined7-c32/c32-runB-hello.json",
 "c32-R4C-hello": "R4C/run-combined4-c32/c32-run1.json", "c32b-hello": "R4D/run-combined4-c32b/c32b-run1.json",
}
DROP = 250  # MB decrease between consecutive 1 Hz samples counts as a GC/purge event
out = {}
for name, path in runs.items():
    try: j = json.load(open(path))
    except Exception as e: print(name, "skip", e); continue
    te = j["tokenEvents"]; rs = j["rssSamples"]; ms = j["metricSamples"]; tRun = j["tRun"]
    bounds = [tRun] + [tRun + e["sinceRun"] for e in te]
    rt = np.array([s["t"] for s in rs]); rv = np.array([s["rendererMaxMB"] for s in rs])
    mt = np.array([m["tResp"] for m in ms]); thread = np.array([m["ThreadTime"] for m in ms]); task = np.array([m["TaskDuration"] for m in ms])
    proc = np.array([m["ProcessTime"] for m in ms]); heap = np.array([m["JSHeapUsedSize"] for m in ms]) / 2**20
    rows = []
    for k in range(len(te)):
        a, b = bounds[k], bounds[k + 1]
        sel = (rt >= a) & (rt < b); v = rv[sel]
        drops = int((np.diff(v) < -DROP).sum()) if v.size > 1 else 0
        dropMB = float(-np.diff(v)[np.diff(v) < -DROP].sum()) if v.size > 1 else 0.0
        ia = np.searchsorted(mt, a); ib = np.searchsorted(mt, b); ia = min(ia, len(mt) - 1); ib = min(ib, len(mt) - 1)
        dth = thread[ib] - thread[ia]; dtask = task[ib] - task[ia]; dproc = proc[ib] - proc[ia]
        rows.append(dict(k=k + 1, wall=(b - a) / 1000, drops=drops, dropMB=dropMB, rss_mean=float(v.mean()) if v.size else 0, rss_min=float(v.min()) if v.size else 0, rss_max=float(v.max()) if v.size else 0, thread=dth, task=dtask, proc=dproc, jsheapMB=float(heap[ib])))
    out[name] = rows
    w = np.array([r["wall"] for r in rows]); d = np.array([r["drops"] for r in rows]); k = np.arange(1, len(rows) + 1)
    th = np.array([r["thread"] for r in rows]); pr = np.array([r["proc"] for r in rows]); mb = np.array([r["dropMB"] for r in rows])
    A = np.vstack([np.ones_like(k[1:]), k[1:]]).T; coef = np.linalg.lstsq(A, w[1:], rcond=None)[0]; resid = w[1:] - A @ coef
    corr = np.corrcoef(resid, d[1:])[0, 1] if d[1:].std() > 0 else float('nan')
    # partial fit wall = a + b k + c drops
    A2 = np.vstack([np.ones_like(k[1:]), k[1:], d[1:]]).T; c2 = np.linalg.lstsq(A2, w[1:], rcond=None)[0]
    A3 = np.vstack([np.ones_like(k[1:]), k[1:], mb[1:]/1000]).T; c3 = np.linalg.lstsq(A3, w[1:], rcond=None)[0]
    print(f"{name:14s} total {w.sum():7.1f}s  drops/token mean {d.mean():4.1f} (GB dropped/token {mb.mean()/1000:4.1f})  rss mean {np.mean([r['rss_mean'] for r in rows]):5.0f} MB  "
          f"thread/wall {th.sum()/w.sum():.2f}  proc/wall {pr.sum()/w.sum():.2f}  fit wall={coef[0]:.1f}+{coef[1]:.3f}k  resid~drops r={corr:+.2f}  "
          f"wall={c2[0]:.1f}+{c2[1]:.3f}k+{c2[2]:.2f}*drops | ={c3[0]:.1f}+{c3[1]:.3f}k+{c3[2]:.2f}*GBdropped")
json.dump(out, open("R4V/rss_gc_cadence.json", "w"), indent=0)
print()
for name in ("c32c-hello", "c32c-p40"):
    print("==", name, " k: wall drops GBdropped rss_mean rss_min thread task")
    print(" ".join(f"{r['k']}:{r['wall']:.0f}/{r['drops']}/{r['dropMB']/1000:.1f}/{r['rss_mean']:.0f}/{r['rss_min']:.0f}/{r['thread']:.0f}/{r['task']:.0f}" for r in out[name]))
