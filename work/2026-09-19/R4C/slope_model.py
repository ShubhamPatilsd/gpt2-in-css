#!/usr/bin/env python3
"""R4C: fit the per-token curve of the c32 run and attribute the slope to the per-position populations with R3A/F5 constants.
usage: slope_model.py run-combined4-c32/c32-run1.json"""
import json, sys, statistics
R = json.load(open(sys.argv[1])); ev = R["tokenEvents"]; per = [(e["k"], e["tokenSeconds"]) for e in ev]
ms = sorted(R["metricSamples"], key=lambda s: s["tResp"])
import bisect
mt = [s["tResp"] for s in ms]
def m_at(t): i = bisect.bisect_left(mt, t); return ms[min(i, len(ms)-1)]
def fit(xs, ys):
    n=len(xs); mx=sum(xs)/n; my=sum(ys)/n; b=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/sum((x-mx)**2 for x in xs); a=my-b*mx
    return a, b, (sum((y-(a+b*x))**2 for x,y in zip(xs,ys))/max(1,n-2))**.5
xs=[k for k,_ in per][1:]; ys=[s for _,s in per][1:]
a,b,se=fit(xs,ys); print(f"tokens 2..{xs[-1]}: s/token = {a:.2f} + {b:.3f}·k (rmse {se:.2f}); predicted k=8 {a+8*b:.1f}, k=32 {a+32*b:.1f}")
# CDP style/layout/task per token
prev=m_at(R["tRun"]); rows=[]
for e in ev:
    m=m_at(e["tResp"]); d=lambda k:(m.get(k,0) or 0)-(prev.get(k,0) or 0)
    rows.append(dict(k=e["k"], s=e["tokenSeconds"], recalc=d("RecalcStyleCount"), layout=d("LayoutCount"), style=d("RecalcStyleDuration"), lay=d("LayoutDuration"), task=d("TaskDuration"))); prev=m
for key,lab in (("recalc","RecalcStyleCount/token"),("layout","LayoutCount/token"),("style","style s/token"),("lay","layout s/token"),("task","task s/token")):
    a2,b2,se2=fit([r["k"] for r in rows[1:]],[r[key] for r in rows[1:]]); print(f"  {lab:24s} = {a2:8.2f} + {b2:7.3f}·k   (rmse {se2:.2f}); at k=2 {a2+2*b2:.1f}, k=32 {a2+32*b2:.1f}")
passes = statistics.median(r["recalc"] for r in rows[1:])
print(f"\nmodelled per-position terms (passes/token = {passes:.0f} measured median RecalcStyleCount):")
# (1) in-delay KV transitions: 26 per slot per layer, 12 layers -> 312 per position; F5: 5.7 us each per style pass
t1 = 312 * 5.7e-6 * passes; print(f"  (1) in-delay KV latch transitions: 312·p × 5.7 µs × {passes:.0f} passes = {t1:.3f} s/token per position ({t1*32:.1f} s at p=32)")
# (2) filled-slot font instances: per layer 12 score glyph fonts + 12 V fonts get a distinct 768-axis list per filled slot
print(f"  (2) filled-slot distinct font-variation instances: 24·p per layer × 12 layers = {24*12}·p instances/token (cost per instance unmeasured; residual below)")
# (3) transition starts per token: flat 312 (26 per layer) -> 312 × 218 us = 0.07 s, no slope
print(f"  (3) latch transition starts: 312/token flat × 218 µs = {312*218e-6:.2f} s/token (no slope)")
# (4) live timelines: +12 score carriers per slot, flat in p (all 384 exist from the start): 10.7 us per timeline per frame
print(f"  (4) score-carrier timelines: 384 live (cap 32) vs 96 (cap 8): +288 × 10.7 µs × ≈40 frames = {288*10.7e-6*40:.2f} s/token flat step")
# (5) V glyph leaves: +18,432 elements × 5 us per restyle × ~12 ctx passes/token; +18,432 laid-out glyphs
print(f"  (5) V glyph leaves: +18,432 × 5 µs × 12 passes = {18432*5e-6*12:.2f} s/token flat step (style floor only; list parse + shaping extra)")
resid = b - t1; print(f"\nmeasured slope {b:.3f} s/token/position; modelled (1) {t1:.3f}; unexplained residual {resid:.3f} s/token/position -> {resid/(24*12)*1e3:.2f} ms per filled-slot font instance if all of it is (2)")
