# Round 1 results (2026-09-18/19)

Protocol: headless Chrome 153, AC + caffeinate, passive (no geometry reads during generation),
heap flag `--js-flags=--heap-growing-percent=10` ON (matches Codex's runs and P2's control), 3 untraced
runs + 1 light trace per bundle, quiet gate (load < 3), Chromium mutex. Full rows: `bench/results.md`;
per-bundle histograms: `bench/<bundle>.md`; agent reports: `B0.md F2.md F3.md F3b.md F4.md F5.md`.

| Bundle | What | Median s/token | Δ vs baseline | Slope s/token² | RSS peak | Frames/token | Whole-DOM passes/token |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline (v2 rebuild) | current source, unmodified | 40.2 | — | 0.80 | 5.6 GB | 85 | 2 |
| F5 | `inherits:false` handshake/epoch/feedback + scoped republish; inline forwards instead of 1,538 `:nth-child` rules; filled-slot bank aliases | 32.8 | −7.4 (−18 %) | 1.05 | 5.0 GB | 85 | 1 |
| F2 | proj packs → global 3,072-axis list (−3,072 elements); V weight once; `@function` GELU → inline | 36.9 | −3.3 (−8 %) | 1.10 | 6.4 GB | 85 | 2 |
| **combined** | F2 + F5 + F4 (KV latches 48→26 per slot, head 769→2, numeric list entries) | **30.3** | **−9.9 (−25 %)** | **0.49** | 5.9 GB | 85 | 1 |
| F3a | F5 + anchor/container chain for fc→proj→out | 34.2 | −6.0 (−15 %) | 1.00 | 5.6 GB | 73.7 | 1 |
| combined2 | combined + chain | 36.9 | −3.3 (−8 %) | 0.71 | 6.7 GB | 73.7 | 1 |

Fix 1 (heap flag): 3 runs, effect below the ±20 % contention noise of the time; kept ON. Removing it
raised RSS to 5.9 GB and increased swapping on this 16 GB machine.

## What worked and why

- F5 removed the two largest inherited-write cascades (`--loop-ack`/`--loop-ready` with zero readers
  dirtying the open core 24×/token; body `--epoch` dirtying the whole document) and the quadratic
  `:nth-child` selector bucket. Exactly the M1 §8.1–8.2 law: same pass count, narrower passes.
- F4 found the latch cost tracks retained-list bytes (~8 ns/B), not transition count, and halved the
  per-token slope by shortening the held lists.
- F2's gain came from fewer elements and fewer `@function` calls (M1 §8.3), not from bytes; its inline
  GELU costs ~0.8 GB RSS (flag `--no-inline-gelu` available).

## What did not work and why

- The MLP anchor/container chain (F3/F3b) is exact and removes 2 frames/layer, but a k-deep gather
  chain restyles every level below each container when its published numbers change (inherited
  custom properties dirty all descendants, M1 MB2a), so the gather costs Σ depth²/2 element recalcs:
  ≈170k per layer ≈ 0.65 s. That equals the frames it saves. Chains pay only for small gathers
  (≲ 500 values, e.g. attention scores, LN stats). Correction from R2A's trace dissection: the chain
  bundles lost on LAYOUT (`performLayout` self 17.1 s vs 3.6 s per 8 tokens; the chain frame lays out
  8,141 objects ≈ 1.1 s per layer), not on paint — style, animation and paint all went down.

## Where the remaining 30.3 s sits (combined trace, tokens 3–7)

| Block | Share | ≈ s | Note |
|---|---:|---:|---|
| Style: passes of 100–999 elements | 25 % | 7.7 | readback → next-hop subtrees (qkv-c0 126 el, fc-c0 784, cache-bridge 780, loop-reader/signals 357, pass-advance 485); cost model 5 µs/element + ≈40 µs per timeline animation whose timeline moved + 218 µs per started transition; FVS list evaluation is only ≈0.2 s/token; the two loop passes run 3–6× the model (≈4 s/token unexplained) — R2A §4–5 |
| Style: passes of 1k–9,999 elements | 16 % | 4.9 | readback carriers (3,089 / 2,934 populations), 1,553-element bank republish |
| Frames (paint lifecycle 16 % + animate 10 % + prepaint 6 % + hit-test 3 %) | 35 % | 10.6 | 85 frames × ≈105–120 ms of per-live-timeline bookkeeping (≈19k serviceAnimations calls/frame for 10,858 view-timelines, ≈11 µs each) + pending-animation updates; 3 of 7 frames per layer are pure handshake (R2A §1, §2, §8) |
| Layout | 15 % | 4.6 | shaping + carriers |
| Whole-DOM head pass (51,247 elements) | 3 % | 0.9 | 1.4/token × 677 ms |
| GC nested | 5 % | 1.5 | |

## Round 2 targets (see PLAN-round2.md)

Revised after R2A (work/2026-09-19/R2A.md): 1. hop-gated timelines — only the active hop's carrier
animations live (R2E, predicted −6…−7 s); 2. drop the two pulse-end frames per layer and fold the
pass-advance frame (R2F, −2.5…−3.5 s); 3. `overflow: clip` on head rows / metrics (R2D, −1.5…−2.5 s);
4. harness: move the mouse off the page (B1 `mouseoff`, −1 s artifact); 5. probe the loop-reader /
loop-signals passes that run 3–6× the cost model (−2…−4 s); 6. REINSTATED after R2B (MB7/MB8): hoist
every calc()/round() out of `font-variation-settings` lists — such lists re-instantiate the font and
re-shape on every restyle even when unchanged (4–5 ms/element at 768 axes, 20–23 ms at 3,072; hoisted
plain var() lists do not) → bundle R2C, predicted −4.9 s/token (layout −4.3, style −0.6); 7. `contain:
paint` on static compute/head roots (R2D, −1.2 s measured in MB9). Dropped: head lock (the whole-DOM
pass is the head matmul itself); mass `inherits:false` scoping (MB6: ≤ 0.2 s/token).
