# Round 5 plan (2026-09-24) — lower s/token AND memory for `combined7` (cap 8, ≈16.0 s/token, RSS peak ≈6 GB)

Base bundle: `bundles/combined7` (combined4 + R4S + R4D + R4T chunk 64). 32-token demo base: `combined4-c32c`.
Constraints unchanged: no JS, no model change, stock Chrome, exact ids (8/8: 11,314,1101,7926,11,475,314,1101; 32/32: R4C / R4P refs).
Ground rules: PLAN.md + round-4 additions — CHROME.lock held for a WHOLE paired run (ref+cand), owner marker, touch -c 30 s,
rmdir only own; AC power required for timing (harness refuses on battery); log load1 + RSS + vm.swapusage per run; kill your
own children on exit; disk ≥ 3 GB free before any trace. Reference for pairs = `combined7`.

Where combined7's ≈16 s go (from R3A/R4 attributions, to be re-measured by R5A on combined7 itself):
transport (≈8k values/layer × 12 through view-timelines: changed-carrier ≈1.6 s after R4T, idle servicing ≈1 s,
per-frame fixed ≈35 × 117 ms ≈ 4 s), head ≈2.9 s, per-pass fixed ≈1.3 s, element floor + GC ≈2–3 s, latches ≈0.5 s.
Memory: RSS 1.9 → ≈6 GB during 8 tokens; suspects: decoded fonts (285 files incl. head), font instances + shape caches
(144·p V + 12·p score instances per layer), 240k-element DOM + ComputedStyle, ≈100k carrier animations + keyframes, Oilpan garbage.

| Agent | Question | Method | Deliverable |
|---|---|---|---|
| R5A | Where do combined7's 16 s and 6 GB go NOW? | ONE traced 8-token run (blink, blink.style, devtools.timeline, v8.gc, blink_gc, fonts) + `disabled-by-default-memory-infra` dumps (light, at tokens 1/4/8) → time by mechanism (R3A method), RSS by allocator (Oilpan, PartitionAlloc: fonts/shaping/CSS values, Skia, discardable); DOM element count by subtree | ranked levers for time and memory with predicted s/token and MB |
| R5C | Can the 768-value ctx hop leave the timelines? | 12–24 parallel anchor→size-container chains (depth ≤ 32, 2 values/container) read inside the proj pass; 2-layer smoke; predicted 2.5 → 2.0 frames/layer and −768 carriers/layer | bundle `R5C`, frames/layer, pass counts |
| R5H | Replace R4S's 192-deep score chain by `1ch` font-metric readback (R4X §6.1) on the elements that already instantiate the score fonts | cmap glyph '0' → FvsDot glyph; scores inherited via `--fs` into the softmax element; exact-class; removes the container recalcs that grow with p (fixes R4S's cap-32 penalty) | bundle `R5H` (cap 8) + `R5H-c32` |
| R5M | Memory: what can be cut without touching numerics? | (1) fonts-only page → RSS of decoded fonts; test `unicode-range`/subsetting so unused faces are never decoded; head font split; (2) count elements per subtree from index.html; remove/merge the largest inert populations (F2-style); (3) per-animation memory: fixture 10k vs 100k carriers; (4) font-instance churn at cap 8: bound live instances (pin or reuse); (5) `--heap-growing-percent` / renderer flags are launcher-side only and secondary | measured MB per suspect, bundle `R5M` with the exact cuts, RSS peak before/after |
| R5E | Element/declaration floor: how much of the per-pass cost is dead weight at cap 8? | from R5A's element census: find subtrees restyled per pass that carry no live values (unfilled slots beyond cap, head rows, debug/diag nodes, wrappers); remove or `content-visibility:hidden` them | bundle `R5E`, elements/pass before/after |
| B6 | Paired benches vs `combined7` | B5 protocol (lock held per pair, gap ≤ 10 min, 3–4 valid pairs), RSS peak per run as a first-class column | rows in bench/paired-round5.md |
| R5X | Merge R5C + R5H + R5M + R5E → `combined8` (cap 8) and `combined8-c32` | R4M protocol (flag-off byte identity, owners' checkers, correctness runs, READY) | bundles + one 32-token prompt-40 run in a CLEAN-memory session |

Machine preconditions at plan time (12:08): battery 23 % discharging, disk 1.5 GB free, swap 1.9/3 GB — timing runs and traces
wait for AC and ≥ 3 GB free; builds and offline analysis proceed.
