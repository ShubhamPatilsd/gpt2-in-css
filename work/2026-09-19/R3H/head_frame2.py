#!/usr/bin/env python3
"""R3H: anatomy of the head frame (the frame holding the >40k-element UpdateLayoutTree) for every token
in one gzip Chromium light trace. Single streaming pass; keeps renderer-main-thread events in
[latch_k - PRE, latch_k + POST] for every token latch k (the head frame sits ~2-4 s before the latch).

usage: head_frame.py trace.json.gz summary.json out_prefix [PRE_s POST_s]
"""
import gzip, json, sys, collections, time, re
from array import array
import numpy as np

trace_path, summary_path, out_prefix = sys.argv[1], sys.argv[2], sys.argv[3]
PRE = float(sys.argv[4]) if len(sys.argv) > 4 else 9.0
POST = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5
S = json.load(open(summary_path))
PID, TID = S["main_pid"], S["main_tid"]
T_RUN = S["t_run"] or S["t_nav"] or int(S["t_end"] - S["generate_phase"]["wall_ms"] * 1000)
bounds = [(k, T_RUN + int(v * 1000)) for k, v in S["token_bounds_ms_after_run"]]
wins = [(k, t - int(PRE * 1e6), t + int(POST * 1e6)) for k, t in bounds]
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
        try:
            obj, end = DEC.raw_decode(buf, idx)
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

def in_win(ts):
    for k, lo, hi in wins:
        if lo <= ts <= hi: return k
    return None

names = {}; name_list = []
def nid(n):
    i = names.get(n)
    if i is None: i = names[n] = len(name_list); name_list.append(n)
    return i
TS, DUR, NID = array('q'), array('q'), array('i')
detail = {}; inst = []; anim = []
n = 0; kept = 0; argkeys = collections.Counter()
for e in events(trace_path):
    n += 1
    if n % 5_000_000 == 0: print(f"{n} events, kept {kept}, {time.time()-T0:.0f}s", file=sys.stderr, flush=True)
    if e.get("pid") != PID or e.get("tid") != TID: continue
    ts = e.get("ts", 0)
    if in_win(ts) is None: continue
    ph = e.get("ph"); nm = e.get("name"); a = e.get("args") or {}
    if ph == "X":
        d = e.get("dur", 0)
        TS.append(ts); DUR.append(d); NID.append(nid(nm)); kept += 1
        i = len(TS) - 1
        if nm == "UpdateLayoutTree":
            ec = a.get("elementCount")
            if ec is None: ec = (a.get("endData") or {}).get("elementCount", -1)
            detail[i] = {"ec": ec, "args": json.dumps(a)[:600]}
        elif nm == "Layout":
            b = a.get("beginData") or {}; ed = a.get("endData") or {}
            detail[i] = {"dirty": b.get("dirtyObjects"), "total": b.get("totalObjects"), "partial": b.get("partialLayout"), "end": {k: v for k, v in ed.items() if k not in ("layoutRoots",)}, "roots": len(ed.get("layoutRoots") or [])}
        elif nm == "ProxyMain::BeginMainFrame":
            detail[i] = {"bfid": a.get("begin_frame_id")}
        elif nm == "LocalFrameView::ScheduleAnimation":
            detail[i] = {"fn": (a.get("location") or {}).get("function_name")}
        elif nm in ("Document::updateStyle", "LocalFrameView::layout", "PaintController::commitNewDisplayItems", "Blink.Style.UpdateTime") and a:
            detail[i] = {"args": json.dumps(a)[:1500]}
        elif nm in ("PrePaint", "Blink.PrePaint.UpdateTime", "Blink.CompositingInputs.UpdateTime", "Paint", "Blink.Paint.UpdateTime", "CullRectUpdate", "LocalFrameView::RunPaintLifecyclePhase", "PaintArtifactCompositor::Update", "Layerize", "LayerTreeHost::DoUpdateLayers", "Commit", "InlineNode::ShapeTextIncludingFirstLine", "LocalFrameView::performLayout", "Blink.Layout.UpdateTime", "Blink.Style.UpdateTime") and a:
            detail[i] = {"args": json.dumps(a)[:300]}
        if a:
            for k in a: argkeys[(nm, k)] += 1
    elif ph in ("I", "i", "R", "n") and nm != "Animation":
        key = ""
        if nm == "LocalFrameView::ScheduleAnimation": key = (a.get("location") or {}).get("function_name", "")
        inst.append((ts, nm, key))
    if nm == "Animation" and ph in ("b", "n", "e", "S", "T", "F", "I", "i"):
        d = a.get("data") or {}
        anim.append((ts, ph, d.get("name") or d.get("displayName") or "", d.get("state") or "", d.get("nodeName") or ""))
print(f"done streaming: {n} events; kept {kept} X, {len(inst)} instants, {len(anim)} Animation; {time.time()-T0:.0f}s", file=sys.stderr, flush=True)

TS = np.frombuffer(TS, dtype=np.int64).copy(); DUR = np.frombuffer(DUR, dtype=np.int64).copy(); NID = np.frombuffer(NID, dtype=np.int32).copy()
order = np.lexsort((-DUR, TS)); inv = np.empty_like(order); inv[order] = np.arange(len(order))
detail = {int(inv[i]): v for i, v in detail.items()}
TS, DUR, NID = TS[order], DUR[order], NID[order]
END = TS + DUR
tsl, endl, durl = TS.tolist(), END.tolist(), DUR.tolist(); selfl = durl[:]; depthl = [0] * len(tsl); parentl = [-1] * len(tsl)
stack = []
for i in range(len(tsl)):
    t = tsl[i]
    while stack and endl[stack[-1]] <= t: stack.pop()
    depthl[i] = len(stack)
    if stack: selfl[stack[-1]] -= durl[i]; parentl[i] = stack[-1]
    stack.append(i)
ms = lambda us: round(us / 1000, 2)
inst_ts = np.array([x[0] for x in inst], dtype=np.int64); io = np.argsort(inst_ts); inst_ts = inst_ts[io]; inst = [inst[i] for i in io]
anim_ts = np.array([x[0] for x in anim], dtype=np.int64); ao = np.argsort(anim_ts); anim_ts = anim_ts[ao]; anim = [anim[i] for i in ao]

bmf = names.get("ProxyMain::BeginMainFrame"); ult = names.get("UpdateLayoutTree")
# head passes = UpdateLayoutTree with elementCount >= 20000
head_passes = [i for i in range(len(tsl)) if NID[i] == ult and detail.get(i, {}).get("ec", 0) and detail[i]["ec"] >= 20000]
print(f"head passes: {[(ms(tsl[i]-T_RUN), detail[i]['ec'], ms(durl[i])) for i in head_passes]}", file=sys.stderr)
out = {"trace": trace_path, "PRE": PRE, "POST": POST, "tokens": []}
def frame_of(i):
    p = parentl[i]
    while p >= 0 and NID[p] != bmf: p = parentl[p]
    return p
seen = set()
for hp in head_passes:
    fi = frame_of(hp)
    if fi < 0 or fi in seen: continue
    seen.add(fi)
    a, b = tsl[fi], endl[fi]
    tok = in_win(a)
    idxs = np.where((TS >= a) & (TS < b))[0]
    incl = collections.Counter(); selfc = collections.Counter(); cnt = collections.Counter()
    for i in idxs:
        nm = name_list[NID[i]]; incl[nm] += durl[i]; selfc[nm] += selfl[i]; cnt[nm] += 1
    T = {"token": tok, "t_ms_after_run": ms(a - T_RUN), "ms_before_latch": ms(dict(bounds)[tok] - b) if tok else None, "dur_ms": ms(b - a)}
    T["names"] = sorted(((nm, cnt[nm], ms(incl[nm]), ms(selfc[nm])) for nm in incl), key=lambda r: -r[3])
    T["passes"] = [(detail[i]["ec"], ms(durl[i])) for i in idxs if NID[i] == ult]
    T["layouts"] = [dict(detail[i], ms=ms(durl[i])) for i in idxs if name_list[NID[i]] == "Layout"]
    T["details"] = [(name_list[NID[i]], ms(durl[i]), detail[i]) for i in idxs if i in detail and "args" in detail[i]][:80]
    def chain(i):
        out = []; p = parentl[i]
        while p >= 0 and len(out) < 8: out.append(name_list[NID[p]]); p = parentl[p]
        return out
    T["parents"] = [(name_list[NID[i]], ms(durl[i]), chain(i)) for i in idxs if name_list[NID[i]] in ("Blink.CompositingInputs.UpdateTime", "Blink.PrePaint.UpdateTime", "CullRectUpdate", "Layout", "UpdateLayoutTree", "InlineNode::ShapeTextIncludingFirstLine", "Document::rebuildLayoutTree") and durl[i] > 5000]
    T["names_all"] = T["names"]
    # shaping: count + total + distribution, and which parent Layout they sit in
    sh = [i for i in idxs if name_list[NID[i]] == "InlineNode::ShapeTextIncludingFirstLine"]
    shd = np.array([durl[i] for i in sh]) if sh else np.array([0])
    T["shape"] = {"n": len(sh), "sum_ms": ms(int(shd.sum())), "median_us": float(np.median(shd)), "p90_us": float(np.percentile(shd, 90)), "max_us": int(shd.max()),
                  "by_parent_layout": collections.Counter()}
    for i in sh:
        p = parentl[i]
        while p >= 0 and name_list[NID[p]] != "Layout": p = parentl[p]
        T["shape"]["by_parent_layout"][f"layout@{ms(tsl[p]-a) if p>=0 else 'none'}"] += 1
    T["shape"]["by_parent_layout"] = dict(T["shape"]["by_parent_layout"])
    # sequence of top-level lifecycle children
    dfi = depthl[fi]; seq = []
    for i in idxs:
        if depthl[i] <= dfi + 3 and name_list[NID[i]] not in ("RunTask",):
            seq.append((depthl[i] - dfi, name_list[NID[i]].split("::")[-1], ms(durl[i]), ms(selfl[i]), ms(tsl[i] - a)))
    T["seq"] = seq[:200]
    sa = collections.Counter(detail[i].get("fn") for i in idxs if name_list[NID[i]] == "LocalFrameView::ScheduleAnimation")
    lo_, hi_ = np.searchsorted(inst_ts, a), np.searchsorted(inst_ts, b)
    ic = collections.Counter()
    for j in range(lo_, hi_):
        if inst[j][1] == "LocalFrameView::ScheduleAnimation": sa[inst[j][2]] += 1
        else: ic[inst[j][1]] += 1
    T["schedule_anim"] = dict(sa); T["instants"] = dict(ic)
    lo_, hi_ = np.searchsorted(anim_ts, a), np.searchsorted(anim_ts, b)
    ac = collections.Counter(); an = collections.Counter()
    for j in range(lo_, hi_):
        _, ph, nm_, st, node = anim[j]; ac[f"{ph}/{st}"] += 1
        an[(re.sub(r"\d+", "N", nm_), ph, st, re.sub(r"\d+", "N", node)[:40])] += 1
    T["anim_counts"] = dict(ac); T["anim_names"] = [(k, v) for k, v in an.most_common(30)]
    # neighbours: previous and next frame durations + passes (context)
    fr_all = [i for i in range(len(tsl)) if NID[i] == bmf and abs(tsl[i] - a) < 6_000_000]
    T["neighbour_frames"] = [(ms(tsl[i] - a), ms(durl[i]), [detail[j]["ec"] for j in np.where((TS >= tsl[i]) & (TS < endl[i]))[0] if NID[j] == ult]) for i in fr_all]
    out["tokens"].append(T)
out["argkeys"] = sorted(((f"{k[0]}|{k[1]}", v) for k, v in argkeys.items()), key=lambda x: -x[1])[:120]
json.dump(out, open(out_prefix + ".json", "w"), indent=1, default=str)
# markdown summary
L = []; P = L.append
P(f"# head frames — {trace_path}\n")
P("| token | t after run (ms) | ms before latch | frame ms | passes ec:ms | layouts dirty/total:ms | shape n / ms / median us | compInputs | PrePaint | paintLC incl/self | GC nested |")
P("|---:|---:|---:|---:|---|---|---|---:|---:|---|---:|")
for T in out["tokens"]:
    d = {nm: (c, inc, se) for nm, c, inc, se in T["names"]}
    g = sum(inc for nm, c, inc, se in T["names"] if nm.startswith("V8.GC") or nm == "MajorGC")
    P(f"| {T['token']} | {T['t_ms_after_run']:.0f} | {T['ms_before_latch']} | {T['dur_ms']:.0f} | {' '.join(f'{ec}:{m:.0f}' for ec, m in T['passes'])} | {' '.join(f'{l['dirty']}/{l['total']}:{l['ms']:.0f}' for l in T['layouts'])} | {T['shape']['n']} / {T['shape']['sum_ms']} / {T['shape']['median_us']:.0f} | {d.get('Blink.CompositingInputs.UpdateTime',(0,0,0))[1]:.0f} | {d.get('PrePaint',(0,0,0))[1]:.0f} | {d.get('LocalFrameView::RunPaintLifecyclePhase',(0,0,0))[1]:.0f}/{d.get('LocalFrameView::RunPaintLifecyclePhase',(0,0,0))[2]:.0f} | {g:.0f} |")
for T in out["tokens"][:2]:
    P(f"\n## token {T['token']} — names (count, incl ms, self ms), top 45\n")
    for r in T["names"][:45]: P(f"- {r}")
    P(f"\n### sequence (depth, name, incl, self, t_in_frame)\n")
    for r in T["seq"][:120]: P(f"- {r}")
    P(f"\n### layouts\n"); [P(f"- {l}") for l in T["layouts"]]
    P(f"\n### shaping by parent layout: {T['shape']['by_parent_layout']}  p90 {T['shape']['p90_us']:.0f} us max {T['shape']['max_us']} us")
    P(f"\n### schedule_anim {T['schedule_anim']}\n### instants {T['instants']}\n### anim_counts {T['anim_counts']}\n### anim names\n"); [P(f"- {v} {k}") for k, v in T["anim_names"]]
    P(f"\n### details (args)\n"); [P(f"- {r}") for r in T["details"][:80]]
    P(f"\n### parent chains\n"); [P(f"- {r}") for r in T["parents"]]
    P(f"\n### all names\n"); [P(f"- {r}") for r in T["names_all"]]
    P(f"\n### neighbour frames (t rel, ms, passes)\n"); [P(f"- {r}") for r in T["neighbour_frames"]]
P("\n## arg keys seen (name|key, count)\n"); [P(f"- {r}") for r in out["argkeys"]]
open(out_prefix + ".md", "w").write("\n".join(L))
print(f"wrote {out_prefix}.json/.md; {time.time()-T0:.0f}s", file=sys.stderr)
