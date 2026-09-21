#!/usr/bin/env python3
"""R3A: per-token / per-frame / per-phase / per-pass anatomy of a heavy Chromium trace (gzip JSON, ring mode).

pass 1: main thread (most UpdateLayoutTree), token bounds (--saved-token-N transition starts), (cat,name,ph) inventory.
pass 2: main-thread X events inside [first complete token start - pad, last complete token end + pad] (+ instants as ts/name).
Then: stack -> self time / parent / depth; frames (ProxyMain::BeginMainFrame); each event attributed to its nearest
lifecycle-phase ancestor; per token: phase totals, per-phase top names (self), per-pass children, head frame, per-frame rows.
usage: anatomy.py trace.json.gz run.json out_prefix [tokens=all]   (tokens: e.g. "3-6")
"""
import gzip, json, sys, collections, time, re
from array import array
import numpy as np

trace_path, run_json, out_prefix = sys.argv[1], sys.argv[2], sys.argv[3]
tok_sel = sys.argv[4] if len(sys.argv) > 4 else "all"
run = json.load(open(run_json)) if run_json != "-" else {}
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
def log(*a): print(*a, file=sys.stderr, flush=True)

# ---------------- pass 1 ----------------
ult = collections.Counter(); inv = collections.defaultdict(lambda: [0, 0]); saved_tok = collections.defaultdict(list)
tmin = tmax = None; n = 0; arg_samples = collections.defaultdict(list); marks = {}
for e in events(trace_path):
    n += 1
    if n % 5_000_000 == 0: log(f"pass1 {n} {time.time()-T0:.0f}s")
    nm = e.get("name"); ph = e.get("ph"); ts = e.get("ts")
    if nm == "UpdateLayoutTree": ult[(e.get("pid"), e.get("tid"))] += 1
    r = inv[(e.get("cat"), nm, ph)]; r[0] += 1
    if ph == "X": r[1] += e.get("dur", 0)
    if ts is not None:
        if tmin is None or ts < tmin: tmin = ts
        if tmax is None or ts > tmax: tmax = ts
    if nm == "Animation" and ph == "b":
        d = (e.get("args") or {}).get("data") or {}
        an = d.get("name") or d.get("displayName") or ""
        m = re.match(r"^--saved-token-(\d+)$", an)
        if m: saved_tok[int(m.group(1))].append(ts)
    if ph == "R" and "blink.user_timing" in (e.get("cat") or ""): marks.setdefault(nm, ts)
    if ph in ("X", "I", "i", "b", "n") and len(arg_samples[nm]) < 2 and e.get("args"):
        s = json.dumps(e["args"])[:300]
        if s not in arg_samples[nm]: arg_samples[nm].append(s)
(PID, TID), n_ult = ult.most_common(1)[0]
log(f"pass1 done: {n} events; main {PID}/{TID} ult={n_ult}; ts {tmin}..{tmax} ({(tmax-tmin)/1e6:.1f} s); saved-token {sorted((k, len(v)) for k, v in saved_tok.items())}")
tok_bounds = sorted((k, min(v)) for k, v in saved_tok.items())
# token k window = [bound(k-1), bound(k)]; complete if both inside the trace range with margin
windows = []
for i in range(1, len(tok_bounds)):
    k0, t0 = tok_bounds[i - 1]; k1, t1 = tok_bounds[i]
    if k1 == k0 + 1 and t0 > tmin + 500_000: windows.append((k1, t0, t1))
if tok_sel != "all":
    a, b = [int(x) for x in tok_sel.split("-")]; windows = [w for w in windows if a <= w[0] <= b]
log("complete token windows:", [(k, round((t1 - t0) / 1e6, 2)) for k, t0, t1 in windows])
if not windows: raise SystemExit("no complete token window")
PAD = 3_000_000
lo = windows[0][1] - PAD; hi = windows[-1][2] + PAD

# ---------------- pass 2 ----------------
names = {}; name_list = []
def nid(nm):
    i = names.get(nm)
    if i is None: i = names[nm] = len(name_list); name_list.append(nm)
    return i
TS, DUR, NID = array('q'), array('q'), array('i')
detail = {}; ITS, INID = array('q'), array('i'); anim = []
kept = 0; n = 0
for e in events(trace_path):
    n += 1
    if n % 5_000_000 == 0: log(f"pass2 {n} kept {kept} {time.time()-T0:.0f}s")
    if e.get("pid") != PID or e.get("tid") != TID: continue
    ts = e.get("ts", 0)
    if ts < lo or ts > hi: continue
    ph = e.get("ph"); nm = e.get("name"); a = e.get("args") or {}
    if ph == "X":
        TS.append(ts); DUR.append(e.get("dur", 0)); NID.append(nid(nm)); kept += 1
        i = len(TS) - 1
        if nm == "UpdateLayoutTree":
            ec = a.get("elementCount")
            if ec is None: ec = (a.get("endData") or {}).get("elementCount", -1)
            detail[i] = {"ec": ec}
        elif nm == "Layout":
            b = a.get("beginData") or {}
            detail[i] = {"dirty": b.get("dirtyObjects"), "total": b.get("totalObjects")}
        elif nm == "LocalFrameView::ScheduleAnimation":
            detail[i] = {"fn": (a.get("location") or {}).get("function_name")}
        elif nm == "HitTest":
            ed = a.get("endData") or {}; detail[i] = {"x": ed.get("x"), "y": ed.get("y"), "node": ed.get("nodeName")}
        elif a and nm not in ("AnimationTimeline::serviceAnimations", "InlineNode::ShapeTextIncludingFirstLine", "RunTask"):
            # keep numeric args of any other event (heavy categories may carry counts)
            d = {}
            for k, v in a.items():
                if isinstance(v, (int, float)): d[k] = v
                elif isinstance(v, dict):
                    for k2, v2 in v.items():
                        if isinstance(v2, (int, float)): d[k + "." + k2] = v2
            if d: detail[i] = d
    elif ph in ("I", "i", "n", "R"):
        key = nm
        if nm == "LocalFrameView::ScheduleAnimation": key = nm + "|" + str((a.get("location") or {}).get("function_name", ""))
        ITS.append(ts); INID.append(nid(key))
    if nm == "Animation" and ph in ("b", "e"):
        d = a.get("data") or {}
        anim.append((ts, ph, d.get("name") or d.get("displayName") or "", d.get("state") or ""))
log(f"pass2 done: kept {kept} X, {len(ITS)} instants, {len(anim)} Animation; {time.time()-T0:.0f}s")

TS = np.frombuffer(TS, dtype=np.int64).copy(); DUR = np.frombuffer(DUR, dtype=np.int64).copy(); NID = np.frombuffer(NID, dtype=np.int32).copy()
order = np.lexsort((-DUR, TS)); inv_o = np.empty_like(order); inv_o[order] = np.arange(len(order))
detail = {int(inv_o[i]): v for i, v in detail.items()}
TS, DUR, NID = TS[order], DUR[order], NID[order]; END = TS + DUR
tsl, endl, durl = TS.tolist(), END.tolist(), DUR.tolist(); nidl = NID.tolist()
selfl = durl[:]; depthl = [0] * len(tsl); parentl = [-1] * len(tsl)
stack = []
for i in range(len(tsl)):
    t = tsl[i]
    while stack and endl[stack[-1]] <= t: stack.pop()
    depthl[i] = len(stack)
    if stack: selfl[stack[-1]] -= durl[i]; parentl[i] = stack[-1]
    stack.append(i)
ITS = np.frombuffer(ITS, dtype=np.int64).copy(); INID = np.frombuffer(INID, dtype=np.int32).copy()
io = np.argsort(ITS, kind="stable"); ITS, INID = ITS[io], INID[io]
anim.sort(); anim_ts = np.array([x[0] for x in anim], dtype=np.int64)
ms = lambda us: round(us / 1000, 2)

# ---------------- phases ----------------
PHASE_NAMES = ["WebFrameWidgetImpl::BeginMainFrame", "UpdateLayoutTree", "Layout", "LocalFrameView::RunCompositingInputsLifecyclePhase", "LocalFrameView::RunPrePaintLifecyclePhase",
               "LocalFrameView::RunPaintLifecyclePhase", "EventHandler::handleMouseMoveEvent", "WebFrameWidgetImpl::UpdateLifecycle", "ProxyMain::BeginMainFrame"]
PHASE_SHORT = {"WebFrameWidgetImpl::BeginMainFrame": "animate", "UpdateLayoutTree": "style", "Layout": "layout", "LocalFrameView::RunCompositingInputsLifecyclePhase": "compinputs",
               "LocalFrameView::RunPrePaintLifecyclePhase": "prepaint", "LocalFrameView::RunPaintLifecyclePhase": "paintLC", "EventHandler::handleMouseMoveEvent": "hover",
               "WebFrameWidgetImpl::UpdateLifecycle": "UL-other", "ProxyMain::BeginMainFrame": "frame-other"}
phase_nid = {names[p]: PHASE_SHORT[p] for p in PHASE_NAMES if p in names}
# phase of event i = nearest ancestor (inclusive of itself? no: the phase container's own self time is "<phase> self")
phase_of = [None] * len(tsl)
for i in range(len(tsl)):
    p = parentl[i]; ph = "task"
    while p >= 0:
        if nidl[p] in phase_nid: ph = phase_nid[nidl[p]]; break
        p = parentl[p]
    phase_of[i] = ph
is_phase = [nidl[i] in phase_nid for i in range(len(tsl))]

bmf = names.get("ProxyMain::BeginMainFrame")
gcre = re.compile(r"GC|MajorGC|MinorGC")
out = {"trace": trace_path, "main": [PID, TID], "trace_range_s": (tmax - tmin) / 1e6, "token_bounds_s": [(k, (t - tmin) / 1e6) for k, t in tok_bounds],
       "inventory": sorted(((c, nm, ph, v[0], ms(v[1])) for (c, nm, ph), v in inv.items()), key=lambda r: -r[3]), "arg_samples": {k: v for k, v in arg_samples.items()},
       "tokens": []}

def name_table(idxs, key=lambda i: True):
    c = collections.Counter(); d = collections.Counter(); s = collections.Counter()
    for i in idxs:
        if not key(i): continue
        nm = nidl[i]; c[nm] += 1; d[nm] += durl[i]; s[nm] += selfl[i]
    return c, d, s

for (k, t0, t1) in windows:
    W = {"token": k, "wall_ms": ms(t1 - t0)}
    m = (TS >= t0) & (TS < t1); idxs = np.where(m)[0].tolist()
    # phase totals: sum of self time by phase (incl. the phase container's own self as "<phase>-self")
    ph_self = collections.Counter(); ph_names = collections.defaultdict(collections.Counter); ph_cnt = collections.defaultdict(collections.Counter)
    gc_by_phase = collections.Counter()
    for i in idxs:
        nm = name_list[nidl[i]]
        if is_phase[i]: ph = phase_nid[nidl[i]]; key = ph + " (self)"
        else: ph = phase_of[i]; key = nm
        ph_self[ph] += selfl[i]; ph_names[ph][key] += selfl[i]; ph_cnt[ph][key] += 1
        if gcre.search(nm) and selfl[i] > 0: gc_by_phase[ph] += selfl[i]
    W["phase_self_ms"] = {p: ms(v) for p, v in ph_self.most_common()}
    W["gc_self_by_phase_ms"] = {p: ms(v) for p, v in gc_by_phase.most_common()}
    W["phase_top"] = {p: [(nm, ph_cnt[p][nm], ms(v)) for nm, v in ph_names[p].most_common(25)] for p in ph_names}
    # instants per token
    lo_, hi_ = np.searchsorted(ITS, t0), np.searchsorted(ITS, t1)
    W["instants"] = {name_list[n_]: int(c_) for n_, c_ in zip(*np.unique(INID[lo_:hi_], return_counts=True))}
    # Animation b/e
    la, ha = np.searchsorted(anim_ts, t0), np.searchsorted(anim_ts, t1)
    ac = collections.Counter(); an = collections.Counter()
    for j in range(la, ha):
        _, ph, nm_, st = anim[j]; ac[ph + "/" + st] += 1; an[(re.sub(r"\d+", "N", nm_), ph)] += 1
    W["anim_counts"] = dict(ac); W["anim_names"] = [(f"{a}|{b}", v) for (a, b), v in an.most_common(30)]
    # frames
    fr = [i for i in idxs if nidl[i] == bmf]
    W["frames_n"] = len(fr); frames = []
    for fi in fr:
        a, b = tsl[fi], endl[fi]
        fm = np.where((TS >= a) & (TS < b))[0].tolist()
        f = {"t_ms": ms(a - t0), "dur_ms": ms(b - a)}
        pself = collections.Counter(); pnames = collections.defaultdict(collections.Counter)
        for i in fm:
            nm = name_list[nidl[i]]
            if is_phase[i]: ph = phase_nid[nidl[i]]; key = ph + " (self)"
            else: ph = phase_of[i]; key = nm
            pself[ph] += selfl[i]; pnames[ph][key] += selfl[i]
        f["phase_ms"] = {p: ms(v) for p, v in pself.items()}
        f["passes"] = [(detail.get(i, {}).get("ec"), ms(durl[i])) for i in fm if name_list[nidl[i]] == "UpdateLayoutTree"]
        f["layouts"] = [(detail.get(i, {}).get("dirty"), ms(durl[i])) for i in fm if name_list[nidl[i]] == "Layout"]
        li, hi2 = np.searchsorted(ITS, a), np.searchsorted(ITS, b)
        ic = collections.Counter(name_list[n_] for n_ in INID[li:hi2].tolist())
        f["inst"] = {kk: v for kk, v in ic.most_common(8)}
        f["sa_x"] = sum(1 for i in fm if name_list[nidl[i]] == "AnimationTimeline::serviceAnimations")
        la, ha = np.searchsorted(anim_ts, a), np.searchsorted(anim_ts, b)
        f["anim_b"] = sum(1 for j in range(la, ha) if anim[j][1] == "b"); f["anim_e"] = sum(1 for j in range(la, ha) if anim[j][1] == "e")
        f["top"] = {p: [(nm, ms(v)) for nm, v in pnames[p].most_common(6)] for p in pnames}
        frames.append(f)
    W["frames"] = frames
    # passes: per UpdateLayoutTree, children self by name
    passes = []
    for i in idxs:
        if name_list[nidl[i]] != "UpdateLayoutTree": continue
        a, b = tsl[i], endl[i]
        ch = np.where((TS >= a) & (TS < b))[0].tolist()
        cn = collections.Counter(); cc = collections.Counter()
        for j in ch:
            if j == i: continue
            nm = name_list[nidl[j]]; cn[nm] += selfl[j]; cc[nm] += 1
        li, hi2 = np.searchsorted(ITS, a), np.searchsorted(ITS, b)
        ic = collections.Counter(name_list[n_] for n_ in INID[li:hi2].tolist())
        passes.append({"t_ms": ms(a - t0), "ec": detail.get(i, {}).get("ec"), "dur_ms": ms(durl[i]), "self_ms": ms(selfl[i]),
                       "children": [(nm, cc[nm], ms(v)) for nm, v in cn.most_common(14)], "inst": {kk: v for kk, v in ic.most_common(6)}})
    W["passes"] = passes
    # per-pass aggregate by elementCount
    agg = collections.defaultdict(lambda: {"n": 0, "dur": 0, "children": collections.Counter(), "ccount": collections.Counter(), "inst": collections.Counter()})
    for p in passes:
        g = agg[p["ec"]]; g["n"] += 1; g["dur"] += p["dur_ms"]
        for nm, c_, v in p["children"]: g["children"][nm] += v; g["ccount"][nm] += c_
        for kk, v in p["inst"].items(): g["inst"][kk] += v
    W["passes_by_ec"] = {str(ec): {"n": g["n"], "sum_ms": round(g["dur"], 1), "mean_ms": round(g["dur"] / g["n"], 1),
                                    "children_mean_ms": [(nm, round(g["ccount"][nm] / g["n"], 1), round(v / g["n"], 2)) for nm, v in g["children"].most_common(12)],
                                    "inst_mean": {kk: round(v / g["n"], 1) for kk, v in g["inst"].most_common(6)}} for ec, g in sorted(agg.items(), key=lambda kv: -kv[1]["dur"])}
    # layouts
    W["layouts"] = [(ms(tsl[i] - t0), detail.get(i, {}).get("dirty"), ms(durl[i])) for i in idxs if name_list[nidl[i]] == "Layout"]
    # head frame = frame with the biggest pass
    if frames:
        hf = max(frames, key=lambda f: max([d for _, d in f["passes"]] + [0]))
        W["head_frame"] = hf
    # whole-window name table (self)
    c, d, s = name_table(idxs)
    W["names_self_top"] = [(name_list[nm], c[nm], ms(d[nm]), ms(s[nm])) for nm, _ in s.most_common(80)]
    out["tokens"].append(W)
    log(f"token {k}: wall {W['wall_ms']} ms, {len(fr)} frames, {len(passes)} passes; {time.time()-T0:.0f}s")

json.dump(out, open(out_prefix + "-anatomy.json", "w"), indent=1, default=str)

# ---------------- markdown ----------------
L = []; P = L.append
P(f"# R3A anatomy — {trace_path}\n\nmain thread {PID}/{TID}; trace covers {out['trace_range_s']:.1f} s; token bounds (s after trace start): {[(k, round(t, 1)) for k, t in out['token_bounds_s']]}\n")
P("## per-token phase self-time (ms)\n")
phs = sorted({p for W in out["tokens"] for p in W["phase_self_ms"]}, key=lambda p: -sum(W["phase_self_ms"].get(p, 0) for W in out["tokens"]))
P("| phase | " + " | ".join(f"tok {W['token']}" for W in out["tokens"]) + " | mean |")
P("|---|" + "---:|" * (len(out["tokens"]) + 1))
P("| wall | " + " | ".join(f"{W['wall_ms']:,.0f}" for W in out["tokens"]) + f" | {np.mean([W['wall_ms'] for W in out['tokens']]):,.0f} |")
P("| frames | " + " | ".join(str(W["frames_n"]) for W in out["tokens"]) + f" | {np.mean([W['frames_n'] for W in out['tokens']]):.1f} |")
P("| style passes | " + " | ".join(str(len(W["passes"])) for W in out["tokens"]) + f" | {np.mean([len(W['passes']) for W in out['tokens']]):.1f} |")
for p in phs:
    vals = [W["phase_self_ms"].get(p, 0) for W in out["tokens"]]
    P(f"| {p} | " + " | ".join(f"{v:,.0f}" for v in vals) + f" | {np.mean(vals):,.0f} |")
for W in out["tokens"]:
    P(f"\n## token {W['token']} — top names by self time within each phase (name, count, self ms)\n")
    for p, rows in sorted(W["phase_top"].items(), key=lambda kv: -W["phase_self_ms"].get(kv[0], 0)):
        P(f"- **{p}** {W['phase_self_ms'].get(p,0):,.0f} ms: " + "; ".join(f"{nm} ×{c} {v:,.1f}" for nm, c, v in rows[:14]))
    P(f"\n### token {W['token']} — passes by elementCount (n, sum ms, mean ms; mean children self ms per pass)\n")
    for ec, g in list(W["passes_by_ec"].items())[:16]:
        P(f"- ec {ec}: n {g['n']}, sum {g['sum_ms']:,.0f}, mean {g['mean_ms']}: " + "; ".join(f"{nm} ×{c} {v}" for nm, c, v in g["children_mean_ms"][:10]) + " | inst " + json.dumps(g["inst_mean"]))
    P(f"\n### token {W['token']} — instants: " + json.dumps(dict(sorted(W["instants"].items(), key=lambda kv: -kv[1])[:12])))
    P(f"\n### token {W['token']} — Animation b/e: {json.dumps(W['anim_counts'])}; names: {W['anim_names'][:12]}")
    hf = W.get("head_frame")
    if hf: P(f"\n### token {W['token']} — head frame: {hf['dur_ms']:,.0f} ms at {hf['t_ms']:,.0f} ms; phases {json.dumps(hf['phase_ms'])}; passes {hf['passes']}; layouts {hf['layouts']}\n  top: {json.dumps(hf['top'])}")
    P(f"\n### token {W['token']} — frames\n")
    P("| # | t | dur | passes ec:ms | layouts dirty:ms | " + " | ".join(phs) + " | sa X | anim b/e |")
    P("|---:|---:|---:|---|---|" + "---:|" * len(phs) + "---:|---|")
    for j, f in enumerate(W["frames"]):
        P(f"| {j} | {f['t_ms']:,.0f} | {f['dur_ms']:,.0f} | {' '.join(f'{ec}:{d:.0f}' for ec, d in f['passes'])} | {' '.join(f'{dd}:{d:.0f}' for dd, d in f['layouts'])} | " + " | ".join(f"{f['phase_ms'].get(p,0):.0f}" for p in phs) + f" | {f['sa_x']} | {f['anim_b']}/{f['anim_e']} |")
P("\n## inventory (cat, name, ph, count, sum ms) — top 120\n")
for r in out["inventory"][:120]: P(f"- {r}")
open(out_prefix + "-anatomy.md", "w").write("\n".join(L))
log(f"wrote {out_prefix}-anatomy.json/.md {time.time()-T0:.0f}s")
