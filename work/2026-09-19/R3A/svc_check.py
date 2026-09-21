#!/usr/bin/env python3
"""R3A: sanity check of where AnimationTimeline::serviceAnimations X events sit inside a few frames (ts containment)."""
import gzip, json, sys, re, bisect, collections
trace, anat = sys.argv[1], json.load(open(sys.argv[2])); PID, TID = anat["main"]
DEC = json.JSONDecoder()
def events(path, chunk=1 << 24):
    f = gzip.open(path, "rt", encoding="utf-8", errors="replace"); buf = f.read(chunk); idx = buf.find("[") + 1
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
            buf = buf[idx:]; idx = 0; more = f.read(chunk)
            if more: buf += more
        yield obj
saved = {}; frames = []; conts = collections.defaultdict(list); svc = []; svci = []
for e in events(trace):
    nm = e.get("name")
    if nm == "Animation" and e.get("ph") == "b":
        d = (e.get("args") or {}).get("data") or {}; m = re.match(r"^--saved-token-(\d+)$", d.get("name") or d.get("displayName") or "")
        if m: saved.setdefault(int(m.group(1)), e["ts"])
    if e.get("pid") != PID or e.get("tid") != TID: continue
    if nm == "AnimationTimeline::serviceAnimations":
        (svc if e.get("ph") == "X" else svci).append(e["ts"]); continue
    if e.get("ph") != "X": continue
    if nm in ("ProxyMain::BeginMainFrame", "WebFrameWidgetImpl::BeginMainFrame", "PageAnimator::serviceScriptedAnimations", "UpdateLayoutTree", "WebFrameWidgetImpl::UpdateLifecycle", "LocalFrameView::RunPaintLifecyclePhase", "Layout", "LocalFrameView::UpdateStyleAndLayout"):
        conts[nm].append((e["ts"], e["dur"], (e.get("args") or {}).get("elementCount")))
svc.sort(); svci.sort()
for k in conts: conts[k].sort()
t0 = saved[4]
fr = [f for f in conts["ProxyMain::BeginMainFrame"] if t0 <= f[0] < t0 + 3_000_000][:5]
cnt = lambda lst, a, b: bisect.bisect_left(lst, b) - bisect.bisect_left(lst, a)
for fts, fd, _ in fr:
    print(f"frame at {(fts-t0)/1000:.0f} ms dur {fd/1000:.0f} ms: svcX {cnt(svc, fts, fts+fd)} svcI {cnt(svci, fts, fts+fd)}")
    for nm in ("WebFrameWidgetImpl::BeginMainFrame", "PageAnimator::serviceScriptedAnimations", "WebFrameWidgetImpl::UpdateLifecycle", "LocalFrameView::UpdateStyleAndLayout", "UpdateLayoutTree", "Layout", "LocalFrameView::RunPaintLifecyclePhase"):
        for ts, d, ec in conts[nm]:
            if fts <= ts < fts + fd: print(f"   {nm:45s} +{(ts-fts)/1000:7.1f} ms dur {d/1000:8.1f} ms ec={ec} svcX {cnt(svc, ts, ts+d)} svcI {cnt(svci, ts, ts+d)}")
