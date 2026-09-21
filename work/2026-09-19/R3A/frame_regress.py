#!/usr/bin/env python3
"""R3A: per-frame regression inputs from the heavy trace (one streaming pass): for every ProxyMain::BeginMainFrame in the
selected token windows: durations of the lifecycle containers (self of RunPaintLifecyclePhase, UpdateLifecycle, animate step),
counts of LocalFrameView::ScheduleAnimation by function_name (X + instant), Animation b/e, serviceAnimations X in the animate step,
Layout dirty objects, style pass elementCounts. Then least-squares fits. usage: frame_regress.py trace.json.gz anatomy.json out_prefix"""
import gzip, json, sys, collections, time, re, bisect
import numpy as np
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
CONT = {"ProxyMain::BeginMainFrame": "frame", "LocalFrameView::RunPaintLifecyclePhase": "paintLC", "WebFrameWidgetImpl::UpdateLifecycle": "UL", "WebFrameWidgetImpl::BeginMainFrame": "animate",
        "PageAnimator::serviceScriptedAnimations": "ssa", "UpdateLayoutTree": "ult", "Layout": "layout", "Blink.CompositingInputs.UpdateTime": "compin", "PrePaint": "prepaint", "Paint": "paint", "CullRectUpdate": "cull",
        "PaintArtifactCompositor::Update": "pac", "LocalFrameView::UpdateStyleAndLayout": "usl", "Document::recalcStyle": "recalc", "EventHandler::handleMouseMoveEvent": "hover"}
X = collections.defaultdict(list)  # kind -> (ts, dur, extra)
SA = []  # (ts, fn) ScheduleAnimation X or I
AN = []  # (ts, ph)
SVC = []  # ts of serviceAnimations X
GC = []  # (ts, dur, name) top-level GC events (nested handled by containment later - we only sum durations of V8.GC_* that are not nested in another GC: approximate by taking MC_INCREMENTAL* and HEAP_ENSURE*)
saved = collections.defaultdict(list); n = 0
for e in events(trace):
    n += 1
    if n % 5_000_000 == 0: print(n, f"{time.time()-T0:.0f}s", file=sys.stderr, flush=True)
    nm = e.get("name"); ph = e.get("ph")
    if nm == "Animation":
        if ph == "b":
            d = (e.get("args") or {}).get("data") or {}
            m = re.match(r"^--saved-token-(\d+)$", d.get("name") or d.get("displayName") or "")
            if m: saved[int(m.group(1))].append(e["ts"])
        if ph in ("b", "e") and e.get("pid") == PID: AN.append((e["ts"], ph))
        continue
    if e.get("pid") != PID or e.get("tid") != TID: continue
    ts = e.get("ts", 0); a = e.get("args") or {}
    if nm == "LocalFrameView::ScheduleAnimation": SA.append((ts, (a.get("location") or {}).get("function_name", ""))); continue
    if ph != "X": continue
    dur = e.get("dur", 0)
    if nm == "AnimationTimeline::serviceAnimations": SVC.append(ts); continue
    k = CONT.get(nm)
    if k:
        extra = None
        if k == "ult":
            extra = a.get("elementCount"); 
            if extra is None: extra = (a.get("endData") or {}).get("elementCount", -1)
        elif k == "layout": extra = (a.get("beginData") or {}).get("dirtyObjects")
        X[k].append((ts, dur, extra))
    elif nm.startswith("V8.GC") or nm == "MajorGC": GC.append((ts, dur, nm))
print(f"streamed {n} {time.time()-T0:.0f}s", file=sys.stderr)
for k in X: X[k].sort()
SA.sort(); AN.sort(); SVC.sort(); GC.sort()
SA_ts = np.array([s[0] for s in SA]); AN_ts = np.array([s[0] for s in AN]); SVC_ts = np.array(SVC); GC_ts = np.array([g[0] for g in GC])
def inside(lst, a, b):
    i = bisect.bisect_left(lst, (a,)); r = []
    while i < len(lst) and lst[i][0] < b: r.append(lst[i]); i += 1
    return r
def sum_in(kind, a, b): return sum(d for _, d, _ in inside(X[kind], a, b))
# GC self time within [a,b): sum of GC event durations minus nested GC durations (stack)
def gc_self(a, b):
    ev = inside(GC, a, b); ev.sort(key=lambda g: (g[0], -g[1])); tot = 0; stack = []
    for ts, d, nm in ev:
        while stack and stack[-1] <= ts: stack.pop()
        if not stack: tot += d
        stack.append(ts + d)
    return tot
bounds = sorted((k, min(v)) for k, v in saved.items())
windows = [(bounds[i][0], bounds[i-1][1], bounds[i][1]) for i in range(1, len(bounds)) if bounds[i][0] == bounds[i-1][0] + 1]
rows = []
for k, a, b in windows:
    for fts, fdur, _ in inside(X["frame"], a, b):
        fe = fts + fdur
        r = {"tok": k, "t_ms": (fts - a) / 1000, "dur": fdur / 1000}
        pl = inside(X["paintLC"], fts, fe); r["paintLC"] = sum(d for _, d, _ in pl) / 1000
        r["paintLC_self"] = (sum(d for _, d, _ in pl) - sum(sum_in(kk, s, s + d) for s, d, _ in pl for kk in ("paint", "cull", "pac"))) / 1000
        ul = inside(X["UL"], fts, fe); r["UL"] = sum(d for _, d, _ in ul) / 1000
        r["UL_self"] = (r["UL"] * 1000 - sum(sum_in(kk, s, s + d) for s, d, _ in ul for kk in ("usl", "compin", "prepaint", "paintLC"))) / 1000
        an = inside(X["animate"], fts, fe); r["animate"] = sum(d for _, d, _ in an) / 1000
        ssa = inside(X["ssa"], fts, fe); r["ssa"] = sum(d for _, d, _ in ssa) / 1000
        r["svc_animate"] = sum(int(np.searchsorted(SVC_ts, s + d) - np.searchsorted(SVC_ts, s)) for s, d, _ in an)
        r["svc_frame"] = int(np.searchsorted(SVC_ts, fe) - np.searchsorted(SVC_ts, fts))
        r["ssa_self"] = (r["ssa"] * 1000 - sum(d for s, d, _ in an for t_ in [0] for d in [0])) / 1000  # placeholder, replaced below
        # ssa self = ssa - serviceAnimations durations inside: need durations; approximate with anatomy later. keep count only.
        r["style"] = sum_in("ult", fts, fe) / 1000; r["passes"] = [x for _, _, x in inside(X["ult"], fts, fe)]
        r["recalc"] = sum_in("recalc", fts, fe) / 1000
        r["layout"] = sum_in("layout", fts, fe) / 1000; r["dirty"] = sum((x or 0) for _, _, x in inside(X["layout"], fts, fe))
        r["compin"] = sum_in("compin", fts, fe) / 1000; r["prepaint"] = sum_in("prepaint", fts, fe) / 1000; r["hover"] = sum_in("hover", fts, fe) / 1000
        r["gc"] = gc_self(fts, fe) / 1000
        lo, hi = np.searchsorted(SA_ts, fts), np.searchsorted(SA_ts, fe)
        c = collections.Counter(fn for _, fn in SA[lo:hi]); r["sa_add"] = c.get("Add", 0); r["sa_next"] = c.get("ScheduleServiceOnNextFrame", 0); r["sa_other"] = sum(v for kk, v in c.items() if kk not in ("Add", "ScheduleServiceOnNextFrame"))
        lo, hi = np.searchsorted(AN_ts, fts), np.searchsorted(AN_ts, fe)
        r["an_b"] = sum(1 for _, p in AN[lo:hi] if p == "b"); r["an_e"] = sum(1 for _, p in AN[lo:hi] if p == "e")
        # gap before the frame: Animation events between previous frame end and this frame start are attributed to this frame too
        rows.append(r)
del_ = "ssa_self"
for r in rows: r.pop(del_, None)
json.dump({"windows": [(k, (b - a) / 1e6) for k, a, b in windows], "frames": rows}, open(out + ".json", "w"), indent=1)
# fits
def fit(y, cols, label):
    Xm = np.column_stack([np.ones(len(rows))] + [np.array([r[c] for r in rows], dtype=float) for c in cols]); yv = np.array(y, dtype=float)
    beta, *_ = np.linalg.lstsq(Xm, yv, rcond=None); pred = Xm @ beta; r2 = 1 - ((yv - pred) ** 2).sum() / ((yv - yv.mean()) ** 2).sum()
    return f"{label}: {' + '.join([f'{beta[0]:.1f} ms'] + [f'{beta[i+1]*1000:.1f} us*{c}' for i, c in enumerate(cols)])}  (R2 {r2:.3f}, n {len(rows)})"
L = [f"frames {len(rows)} in tokens {[k for k, _, _ in windows]}"]
med = lambda c: float(np.median([r[c] for r in rows]))
L.append("medians per frame: " + json.dumps({c: round(med(c), 2) for c in ("dur", "paintLC_self", "UL_self", "animate", "ssa", "svc_animate", "svc_frame", "style", "layout", "compin", "prepaint", "gc", "sa_add", "sa_next", "an_b", "an_e", "dirty")}))
L.append("sums per token: " + json.dumps({c: round(sum(r[c] for r in rows) / len(windows), 1) for c in ("dur", "paintLC_self", "UL_self", "animate", "style", "layout", "compin", "prepaint", "gc", "hover", "sa_add", "sa_next", "an_b", "an_e")}))
L.append(fit([r["paintLC_self"] for r in rows], ["sa_add", "an_b"], "paintLC self"))
L.append(fit([r["paintLC_self"] for r in rows], ["sa_add", "an_b", "an_e"], "paintLC self"))
L.append(fit([r["paintLC_self"] for r in rows], ["sa_add", "an_b", "dirty"], "paintLC self"))
L.append(fit([r["paintLC_self"] for r in rows], ["sa_add", "an_b", "svc_animate"], "paintLC self"))
L.append(fit([r["UL_self"] for r in rows], ["dirty"], "UL self"))
L.append(fit([r["UL_self"] for r in rows], ["dirty", "sa_add"], "UL self"))
L.append(fit([r["UL_self"] for r in rows], ["dirty", "sa_add", "sa_next"], "UL self"))
L.append(fit([r["UL_self"] for r in rows], ["dirty", "svc_frame"], "UL self"))
L.append(fit([r["animate"] for r in rows], ["svc_animate"], "animate"))
L.append(fit([r["animate"] for r in rows], ["svc_animate", "sa_add", "sa_next"], "animate"))
L.append(fit([r["compin"] for r in rows], ["dirty"], "compositing inputs"))
L.append(fit([r["compin"] + r["prepaint"] for r in rows], ["dirty"], "compositing inputs + prepaint"))
L.append(fit([r["layout"] for r in rows], ["dirty"], "layout"))
# frame types by pass signature
sig = collections.defaultdict(list)
for r in rows: sig[" ".join(str(p) for p in r["passes"])].append(r)
L.append("\n| signature | n | med dur | style | recalc | layout | dirty | animate | UL self | compin | prepaint | paintLC self | gc | hover | svc animate | sa Add | sa Next | anim b/e |")
L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
for s, rs in sorted(sig.items(), key=lambda kv: -len(kv[1]) * np.median([r['dur'] for r in kv[1]])):
    m = lambda c: np.median([r[c] for r in rs])
    L.append(f"| `{s}` | {len(rs)} | {m('dur'):.0f} | {m('style'):.0f} | {m('recalc'):.0f} | {m('layout'):.0f} | {m('dirty'):.0f} | {m('animate'):.0f} | {m('UL_self'):.0f} | {m('compin'):.0f} | {m('prepaint'):.0f} | {m('paintLC_self'):.0f} | {m('gc'):.0f} | {m('hover'):.1f} | {m('svc_animate'):.0f} | {m('sa_add'):.0f} | {m('sa_next'):.0f} | {m('an_b'):.0f}/{m('an_e'):.0f} |")
open(out + ".md", "w").write("\n".join(L)); print("\n".join(L[:20])); print("wrote", out, file=sys.stderr)
