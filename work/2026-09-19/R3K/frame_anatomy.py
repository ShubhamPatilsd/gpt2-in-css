#!/usr/bin/env python3
"""R2A: per-frame anatomy of one token window from a (gzip) Chromium light trace.

Single streaming pass (reuses P2's event iterator). Keeps only renderer main-thread events inside the
window [t_a, t_b] (ms after the run mark, taken from <bundle>-t1-summary.json), plus Animation
async events and instant events (ScheduleAnimation / ScheduleStyleRecalculation / serviceAnimations).
Then groups by ProxyMain::BeginMainFrame, computes inclusive/self per name per frame with a stack,
and writes <out>-frames.json + <out>-frames.md.

usage: frame_anatomy.py trace.json.gz summary.json token_index out_prefix
"""
import gzip, json, sys, collections, time, re
from array import array

trace_path, summary_path, tok_idx, out_prefix = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
S = json.load(open(summary_path))
PID, TID = S["main_pid"], S["main_tid"]
# same base as parse_trace.py: run mark, else nav, else (trace start = end mark - generate wall)
T_RUN = S["t_run"] or S["t_nav"] or int(S["t_end"] - S["generate_phase"]["wall_ms"] * 1000)
bounds = dict((k, v) for k, v in S["token_bounds_ms_after_run"])
bounds.setdefault(0, 0.0)  # R3K: token 1 window starts at the run mark (R2A only parsed tokens >= 2)
# token k window = [latch of k-1, latch of k]
t_a = T_RUN + int(bounds[tok_idx - 1] * 1000); t_b = T_RUN + int(bounds[tok_idx] * 1000)
PAD = 2_000_000  # 2 s padding each side so that the frame containing the boundary is complete
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

names = {}; name_list = []
def nid(n):
    i = names.get(n)
    if i is None: i = names[n] = len(name_list); name_list.append(n)
    return i
TS, DUR, NID, TDUR = array('q'), array('q'), array('i'), array('q')
detail = {}           # index in TS -> small dict of args of interest
inst = []             # (ts, name, key) instant events
anim = []             # (ts, ph, name, state, node, id)
n = 0; kept = 0; lo = t_a - PAD; hi = t_b + PAD
for e in events(trace_path):
    n += 1
    if n % 5_000_000 == 0: print(f"{n} events, kept {kept}, {time.time()-T0:.0f}s", file=sys.stderr, flush=True)
    if e.get("pid") != PID or e.get("tid") != TID: continue
    ts = e.get("ts", 0)
    if ts < lo or ts > hi: continue
    ph = e.get("ph"); nm = e.get("name"); a = e.get("args") or {}
    if ph == "X":
        d = e.get("dur", 0)
        TS.append(ts); DUR.append(d); NID.append(nid(nm)); TDUR.append(e.get("tdur", d)); kept += 1
        i = len(TS) - 1
        if nm == "UpdateLayoutTree":
            ec = a.get("elementCount")
            if ec is None: ec = (a.get("endData") or {}).get("elementCount", -1)
            detail[i] = {"ec": ec}
        elif nm == "Layout":
            b = a.get("beginData") or {}
            detail[i] = {"dirty": b.get("dirtyObjects"), "total": b.get("totalObjects"), "partial": b.get("partialLayout")}
        elif nm == "ProxyMain::BeginMainFrame":
            detail[i] = {"bfid": a.get("begin_frame_id")}
        elif nm == "MainFrameAborted":
            detail[i] = {"reason": ((a.get("main_frame_pipeline") or {}).get("aborted_on_main_reason"))}
        elif nm == "HitTest":
            ed = a.get("endData") or {}
            detail[i] = {"x": ed.get("x"), "y": ed.get("y"), "node": ed.get("nodeName"), "move": ed.get("move")}
        elif nm == "LocalFrameView::ScheduleAnimation":
            detail[i] = {"fn": (a.get("location") or {}).get("function_name")}
        elif nm == "Commit":
            detail[i] = {"seq": a.get("frameSeqId")}
        elif nm in ("LayerTreeHost::DoUpdateLayers", "UpdateLayer"):
            detail[i] = {k: v for k, v in a.items() if k != "data"}
    elif ph in ("I", "i", "R", "n") and nm != "Animation":
        key = ""
        if nm == "LocalFrameView::ScheduleAnimation": key = (a.get("location") or {}).get("function_name", "")
        elif nm == "UpdateLayer": key = a.get("layerId")
        inst.append((ts, nm, key))
    if nm == "Animation" and ph in ("b", "n", "e", "S", "T", "F", "I", "i"):
        d = a.get("data") or {}
        anim.append((ts, ph, d.get("name") or d.get("displayName") or "", d.get("state") or "", d.get("nodeName") or "", d.get("id"), d.get("compositeFailed"), d.get("unsupportedProperties")))
print(f"done streaming: {n} events; kept {kept} X, {len(inst)} instants, {len(anim)} Animation; {time.time()-T0:.0f}s", file=sys.stderr, flush=True)

import numpy as np
TS = np.frombuffer(TS, dtype=np.int64).copy(); DUR = np.frombuffer(DUR, dtype=np.int64).copy(); NID = np.frombuffer(NID, dtype=np.int32).copy(); TDUR = np.frombuffer(TDUR, dtype=np.int64).copy()
order = np.lexsort((-DUR, TS)); inv = np.empty_like(order); inv[order] = np.arange(len(order))
detail = {int(inv[i]): v for i, v in detail.items()}
TS, DUR, NID, TDUR = TS[order], DUR[order], NID[order], TDUR[order]
END = TS + DUR
tsl, endl, durl = TS.tolist(), END.tolist(), DUR.tolist(); selfl = durl[:]; depthl = [0] * len(tsl); parentl = [-1] * len(tsl)
stack = []
for i in range(len(tsl)):
    t = tsl[i]
    while stack and endl[stack[-1]] <= t: stack.pop()
    depthl[i] = len(stack)
    if stack: selfl[stack[-1]] -= durl[i]; parentl[i] = stack[-1]
    stack.append(i)
SELF = np.array(selfl); DEPTH = np.array(depthl); PARENT = np.array(parentl)
ms = lambda us: round(us / 1000, 2)

# ---------- frames ----------
bmf = names.get("ProxyMain::BeginMainFrame")
fr_idx = [i for i in range(len(tsl)) if NID[i] == bmf and t_a <= tsl[i] < t_b]
frames = []
inst_ts = np.array([x[0] for x in inst], dtype=np.int64); inst_order = np.argsort(inst_ts); inst_ts = inst_ts[inst_order]; inst = [inst[i] for i in inst_order]
anim_ts = np.array([x[0] for x in anim], dtype=np.int64); a_order = np.argsort(anim_ts); anim_ts = anim_ts[a_order]; anim = [anim[i] for i in a_order]
LIFE = ["WebFrameWidgetImpl::UpdateLifecycle", "LocalFrameView::UpdateStyleAndLayout", "UpdateLayoutTree", "Document::recalcStyle", "Document::updateStyle", "Layout", "InlineNode::ShapeTextIncludingFirstLine",
        "PageAnimator::serviceScriptedAnimations", "AnimationTimeline::serviceAnimations", "Blink.CompositingInputs.UpdateTime", "PrePaint", "LocalFrameView::RunPaintLifecyclePhase", "Paint", "PaintArtifactCompositor::Update",
        "Layerize", "Commit", "LayerTreeHost::DoUpdateLayers", "EventHandler::handleMouseMoveEvent", "LayoutView::HitTest", "HitTest", "MainFrameAborted", "LocalFrameView::ScheduleAnimation", "CullRectUpdate",
        "LocalFrameView::RunAccessibilitySteps", "LocalFrameView::UpdateViewportIntersectionsForSubtree", "Blink.Paint.UpdateTime", "Blink.CompositingCommit.UpdateTime", "TimerBase::run", "V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED", "V8.GC_MC_INCREMENTAL", "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", "MajorGC", "UpdateLayer", "RunTask"]
prev_end = None
for k, fi in enumerate(fr_idx):
    a, b = tsl[fi], endl[fi]
    m = (TS >= a) & (TS < b)
    idxs = np.where(m)[0]
    f = {"i": k, "t_ms": ms(a - t_a), "dur_ms": ms(b - a), "gap_before_ms": ms(a - prev_end) if prev_end is not None else None, "bfid": detail.get(fi, {}).get("bfid")}
    incl = collections.Counter(); selfc = collections.Counter(); cnt = collections.Counter()
    for i in idxs:
        nm = name_list[NID[i]]; incl[nm] += durl[i]; selfc[nm] += selfl[i]; cnt[nm] += 1
    f["incl_ms"] = {nm: ms(incl[nm]) for nm in LIFE if nm in incl}
    f["self_ms"] = {nm: ms(selfc[nm]) for nm in LIFE if nm in selfc}
    f["count"] = {nm: cnt[nm] for nm in LIFE if nm in cnt}
    # untraced self of the frame = BeginMainFrame dur - sum of children dur (children at depth+1)
    f["self_top_other"] = sorted(((nm, ms(v)) for nm, v in selfc.items() if nm not in LIFE and v > 200), key=lambda x: -x[1])[:8]
    f["passes"] = [(detail[i]["ec"], ms(durl[i])) for i in idxs if name_list[NID[i]] == "UpdateLayoutTree"]
    # serviceAnimations attribution: nearest ancestor among the lifecycle phases
    ATTR = {"UpdateLayoutTree", "PageAnimator::serviceScriptedAnimations", "LocalFrameView::RunPaintLifecyclePhase", "Layout", "PrePaint"}
    sa_attr = collections.Counter(); sa_attr_ms = collections.Counter()
    for i in idxs:
        if name_list[NID[i]] != "AnimationTimeline::serviceAnimations": continue
        pj = parentl[i]; anc = "other"
        while pj >= 0:
            nm_ = name_list[NID[pj]]
            if nm_ in ATTR: anc = nm_; break
            pj = parentl[pj]
        sa_attr[anc] += 1; sa_attr_ms[anc] += durl[i]
    f["serviceAnim_by_parent"] = {k: (v, ms(sa_attr_ms[k])) for k, v in sa_attr.items()}
    f["bmf_incl_ms"] = ms(sum(durl[i] for i in idxs if name_list[NID[i]] == "WebFrameWidgetImpl::BeginMainFrame"))
    f["layouts"] = [(detail[i]["dirty"], detail[i]["total"], ms(durl[i])) for i in idxs if name_list[NID[i]] == "Layout"]
    f["hit"] = [detail[i] for i in idxs if name_list[NID[i]] == "HitTest"]
    f["aborted"] = [detail[i].get("reason") for i in idxs if name_list[NID[i]] == "MainFrameAborted"]
    sa = collections.Counter(detail[i].get("fn") for i in idxs if name_list[NID[i]] == "LocalFrameView::ScheduleAnimation")
    lo_, hi_ = np.searchsorted(inst_ts, a), np.searchsorted(inst_ts, b)
    for j in range(lo_, hi_):
        if inst[j][1] == "LocalFrameView::ScheduleAnimation": sa[inst[j][2]] += 1
        elif inst[j][1] == "AnimationTimeline::serviceAnimations": cnt["AnimationTimeline::serviceAnimations(I)"] += 1
        else: cnt[inst[j][1] + "(I)"] += 1
    f["schedule_anim"] = dict(sa)
    f["count"]["AnimationTimeline::serviceAnimations(I)"] = cnt.get("AnimationTimeline::serviceAnimations(I)", 0)
    f["count"]["ScheduleStyleRecalculation(I)"] = cnt.get("ScheduleStyleRecalculation(I)", 0)
    # ordered top-level children of BeginMainFrame (depth = frame depth + 1) for sequence view
    dfi = depthl[fi]
    seq = []
    for i in idxs:
        if parentl[i] == fi or (depthl[i] == dfi + 2 and name_list[NID[parentl[i]]] == "WebFrameWidgetImpl::UpdateLifecycle") or (depthl[i] == dfi + 3 and name_list[NID[parentl[i]]] in ("LocalFrameView::RunStyleAndLayoutLifecyclePhases",)):
            nm = name_list[NID[i]]
            if nm in ("RunTask",): continue
            tag = nm.split("::")[-1]
            if nm == "LocalFrameView::UpdateStyleAndLayout":
                pss = [(detail[j]["ec"]) for j in idxs if name_list[NID[j]] == "UpdateLayoutTree" and tsl[j] >= tsl[i] and tsl[j] < endl[i]]
                lys = [(detail[j]["dirty"]) for j in idxs if name_list[NID[j]] == "Layout" and tsl[j] >= tsl[i] and tsl[j] < endl[i]]
                tag += f"[style {pss} layout {lys}]"
            seq.append((tag, ms(durl[i])))
    f["seq"] = seq
    # Animation events in the frame and in the gap before it
    lo_, hi_ = np.searchsorted(anim_ts, prev_end if prev_end is not None else a), np.searchsorted(anim_ts, b)
    ac = collections.Counter(); an = collections.Counter()
    for j in range(lo_, hi_):
        _, ph, nm_, st, node, aid, cf, up = anim[j]
        ac[(ph, st)] += 1
        if nm_ and not re.match(r"^--saved-\d+-\d+$|^--saved-b\d", nm_): an[(nm_, ph, st)] += 1
    f["anim_counts"] = {f"{k[0]}/{k[1]}": v for k, v in ac.items()}
    f["anim_named"] = sorted(((f"{k[0]}|{k[1]}|{k[2]}", v) for k, v in an.items()), key=lambda x: -x[1])[:12]
    # tasks between previous frame end and this frame start
    if prev_end is not None:
        gm = (TS >= prev_end) & (TS < a) & (DEPTH == 0)
        gc = collections.Counter()
        for i in np.where(gm)[0]:
            # top-level RunTask; look at its biggest child
            ch = [j for j in np.where((TS >= tsl[i]) & (TS < endl[i]) & (PARENT == i))[0]]
            big = max(ch, key=lambda j: durl[j]) if ch else None
            gc[name_list[NID[big]] if big is not None else name_list[NID[i]]] += durl[i]
        f["gap_tasks_ms"] = {k_: ms(v) for k_, v in gc.most_common(6)}
    frames.append(f)
    prev_end = b

# window-level per-name inclusive/self (main thread, in window)
m = (TS >= t_a) & (TS < t_b)
W = collections.defaultdict(lambda: [0, 0, 0])
for i in np.where(m)[0]:
    w = W[name_list[NID[i]]]; w[0] += 1; w[1] += durl[i]; w[2] += selfl[i]
window = sorted(((nm, c, ms(d), ms(s)) for nm, (c, d, s) in W.items()), key=lambda r: -r[3])[:70]

# Animation names in window (excluding --saved-*)
an_all = collections.Counter(); an_state = collections.Counter()
lo_, hi_ = np.searchsorted(anim_ts, t_a), np.searchsorted(anim_ts, t_b)
for j in range(lo_, hi_):
    _, ph, nm_, st, node, aid, cf, up = anim[j]
    an_state[(ph, st)] += 1
    an_all[(re.sub(r"\d+", "N", nm_), ph, st, re.sub(r"\d+", "N", node)[:40])] += 1
out = {"trace": trace_path, "token": tok_idx, "window_ms_after_run": [bounds[tok_idx - 1], bounds[tok_idx]], "frames_n": len(frames), "frames": frames,
       "window_names": window, "anim_state_counts": {f"{k[0]}/{k[1]}": v for k, v in an_state.items()},
       "anim_names_window": [(k, v) for k, v in an_all.most_common(80)],
       "instant_counts_window": dict(collections.Counter(x[1] + ("|" + str(x[2]) if x[2] else "") for x in inst if t_a <= x[0] < t_b))}
# R3K summary: hover-related counts for the token window
zp = sum(1 for f in frames for ec, d in f["passes"] if ec in (0, 1))
zp_ms = sum(d for f in frames for ec, d in f["passes"] if ec in (0, 1))
hits = sum(len(f["hit"]) for f in frames)
hit_ms = sum(f["incl_ms"].get("HitTest", 0) for f in frames)
mm_ms = sum(f["incl_ms"].get("EventHandler::handleMouseMoveEvent", 0) for f in frames)
lv_ms = sum(f["incl_ms"].get("LayoutView::HitTest", 0) for f in frames)
usl = sum(f["count"].get("LocalFrameView::UpdateStyleAndLayout", 0) for f in frames)
allp = sum(len(f["passes"]) for f in frames)
out["r3k"] = {"frames": len(frames), "wall_ms": ms(t_b - t_a), "passes_total": allp, "passes_0or1_elem": zp, "passes_0or1_elem_ms": round(zp_ms, 1),
              "hit_tests": hits, "HitTest_ms": round(hit_ms, 1), "LayoutView_HitTest_ms": round(lv_ms, 1), "handleMouseMove_ms": round(mm_ms, 1),
              "UpdateStyleAndLayout_n": usl, "hit_points": collections.Counter(f"{h.get('x')},{h.get('y')}" for f in frames for h in f["hit"]).most_common(4)}
print("R3K", json.dumps(out["r3k"]), file=sys.stderr)
json.dump(out, open(out_prefix + "-frames.json", "w"), indent=1, default=str)

# ---------- markdown ----------
L = []; P = L.append
P(f"# frames of token {tok_idx} — {trace_path}\n")
P(f"window {bounds[tok_idx-1]:.1f}–{bounds[tok_idx]:.1f} ms after run; {len(frames)} BeginMainFrame; wall {ms(t_b-t_a)} ms\n")
P("| # | t (ms) | gap | dur | passes (elementCount:ms) | layouts (dirty:ms) | animate | serviceAnim n | compInputs | prepaint(n) | paintLC | hit | aborted | anim start/end | gap tasks |")
P("|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|---|")
for f in frames:
    ps = " ".join(f"{ec}:{d:.0f}" for ec, d in f["passes"])
    ly = " ".join(f"{dd}:{d:.0f}" for dd, tt, d in f["layouts"])
    g = f.get("gap_tasks_ms") or {}
    P(f"| {f['i']} | {f['t_ms']:.0f} | {f['gap_before_ms'] if f['gap_before_ms'] is not None else ''} | {f['dur_ms']:.0f} | {ps} | {ly} | {f['incl_ms'].get('PageAnimator::serviceScriptedAnimations',0):.0f} | {f['count'].get('AnimationTimeline::serviceAnimations',0)} | {f['incl_ms'].get('Blink.CompositingInputs.UpdateTime',0):.0f} | {f['incl_ms'].get('PrePaint',0):.0f}({f['count'].get('PrePaint',0)}) | {f['incl_ms'].get('LocalFrameView::RunPaintLifecyclePhase',0):.0f} | {f['incl_ms'].get('EventHandler::handleMouseMoveEvent',0):.0f} | {','.join(str(x) for x in f['aborted'])} | {f['anim_counts'].get('b/running',0)}/{f['anim_counts'].get('e/',0)} | {' '.join(f'{k.split(chr(58))[-1]}={v:.0f}' for k,v in g.items())} |")
P("\n## window-level names (count, incl ms, self ms)\n")
for r in window: P(f"- {r}")
P("\n## Animation names in window (name, ph, state, node) -> count\n")
for k, v in out["anim_names_window"]: P(f"- {v} {k}")
P("\n## instant events in window\n")
for k, v in sorted(out["instant_counts_window"].items(), key=lambda kv: -kv[1]): P(f"- {v} {k}")
open(out_prefix + "-frames.md", "w").write("\n".join(L))
print(f"wrote {out_prefix}-frames.json/.md; {time.time()-T0:.0f}s", file=sys.stderr)
