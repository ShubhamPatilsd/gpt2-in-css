#!/usr/bin/env python3
"""R5A: census-based mechanism model of combined7's s/token, using R3A (R2F trace) and R4T (fixture) per-unit constants. Compared with the untraced
split of B5's four runs (style 6.03 / layout 4.90 / other 4.48 s at tokens 2-8). Constants are quoted with their source; nothing here is measured on combined7."""
L=12; p=4.5  # mean filled positions over tokens 2-8 at cap 8 (p = k, positions incl. prompt: k=2..8 -> 2..8, mean 5; use 4.5 for tokens 1-8)
carriers={'qkv':2304,'ctx(cache-bridge)':768,'attn':768,'fc':3072,'proj':768,'loop':768}
changed=sum(carriers.values())  # per layer
timelines=9231; anims_per_consumer=64
frames_per_layer=2.5  # R4S (was 3.0)
frames=L*frames_per_layer+4  # + head + embedding/S1 + 2 handshake (R2F lean)
per_frame_fixed_R3A=117.0  # ms at 10.9k timelines (R3A §1b), of which 10.7 us per live timeline
per_frame_fixed=per_frame_fixed_R3A*timelines/10900
paint_per_changed=14.1e-3+45.8e-6*anims_per_consumer  # ms, R4T fit
style_per_changed=0.020  # ms per changed-timeline animation applied (R4T: 40 -> ~20 us at chunk 64)
style_unchanged=0.022  # ms per animation restyled unchanged (R3A)
elem=0.005  # ms per element restyled (R3A/M1 4.45-5 us)
pass_fixed=12.7  # ms per style pass (R3A: 4.0 ULT self + 2.8 updateStyle self + 5.9 servicing in 2nd pass)
passes_per_token=134+65*p  # measured RecalcStyleCount per token (B5); R3A had 132 in R2F
passes_frame2=frames  # only the 2nd pass of a frame carries the 5.9 ms servicing; container re-recalcs are cheap
head=3.0  # s untraced (R3A §3: style 0.75, layout 1.34 shaping+performLayout, compositing 0.86, paint 0.2)
transitions=26*L  # KV latch starts per token (R3A: 26/layer); loop latch removed by R3R
trans_cost=0.218+0.096  # ms style + paint per transition start (R3A)
vleaf_restyles=768*8*L  # all 6144 leaves restyled once per layer
score_glyphs=12*p*L
shaping_per_glyph=0.0176  # ms (R3A head rows 17.6 us; V leaves similar order)
rows={}
rows['per-frame fixed (animate self + UL self + paintLC floor + 2nd-pass servicing)']=frames*per_frame_fixed/1000
rows['paint lifecycle per changed carrier (PendingAnimations::Update, R4T)']=L*changed*paint_per_changed/1000
rows['style: changed-timeline animation application']=L*changed*style_per_changed/1000
rows['style: element floor of the layer passes (~14.9k-element core subtree x ~6 passes/layer ... use 60k elements/layer)']=L*60000*elem/1000
rows['style: pass fixed (ULT self + updateStyle self) x recalcs']=passes_per_token*6.8/1000
rows['KV latch transitions (style+paint)']=transitions*trans_cost/1000
rows['head frame (style+layout+compositing+paint)']=head
rows['layout: V-leaf + score-glyph shaping/flex (768p+12p per layer)']=L*(768*p+12*p)*shaping_per_glyph/1000*2  # x2: shape + performLayout share (R3A 4.3 us/dirty obj + 17.6 us shaping)
rows['layout: carriers (8,448 changed widths/layer x 18.2 us dirty-object cost, R3A)']=L*changed*0.0182/1000
rows['GC (Oilpan sweeping stalls + incremental marking, R3A 1.0 s; R4W 1.6-3.8 at cap 32)']=1.2
tot=sum(rows.values())
print(f"frames/token {frames:.0f}; per-frame fixed {per_frame_fixed:.0f} ms; changed carriers/layer {changed}; passes/token {passes_per_token:.0f}")
print("| mechanism | model s/token | source constants |"); print("|---|---:|---|")
for k,v in rows.items(): print(f"| {k} | {v:.2f} | |")
print(f"| **sum** | **{tot:.2f}** | measured wall mean tokens 2-8: 15.55 |")
