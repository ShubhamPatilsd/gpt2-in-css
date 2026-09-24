# Round 5 (2026-09-24) — lower s/token and memory for `combined7` (≈16.0 s/token, RSS ≈6 GB at token 8)

Plan: PLAN-round5.md. Reference for pairs: `combined7`. Machine: 16 GB RAM; during this round the disk fell to 0–0.3 GB free
because macOS swap grew to 6.4 GB (renderer 6 GB + user apps + sessions) → all Chrome runs gated on AC + ≥3 GB free + swap < 3 GB.

## R5A — attribution of combined7 (R5A.md; one memory-infra traced 8-token run under heavy pressure, ids 8/8)

Time (s/token, tokens 2–5): style 5.3–6.0 = fc-stage write pass 1.3–1.9 (3,072 carriers ≈45 µs each) + fc→proj readback
1.3 (48 chunks × 64 anims) + qkv→KV→scores 1.0–1.3 (grows with p: 12·p K-list substitutions) + loop/LN1→qkv 0.7–1.0 +
ctx→attn 0.35 + head pass 0.4 + handshake 0.2; layout 4.3–5.9 (head ≈1.3 + R4S's interleaved container recalcs, which run
INSIDE Layout, + V-leaf shaping ∝ p); PrePaint 1.8 flat (39 frames × 46 ms); GC 1.7 (pressure-inflated); paint-lifecycle +
animate + lifecycle self ≈2.9 (needs the blink-category trace, queued).
Memory (renderer footprint 6.24 GB at token 8): **Oilpan 3.9 GB with only 0.92 GB live → ≈3.0 GB swept var()-substitution
garbage kept committed until an OS purge**; decoded webfonts 872 MB (283 faces = 5.1× the 239 MB woff2: stage 535, head 338,
embedding 100); font instances/shape caches ≈0.83 GB (purgeable); PA strings 0.35 GB. Oilpan live: custom-property tries
468 MB (854k HashTrieNode<CSSVariableData>, 999k CSSVariableData; 114k ComputedStyles ≈4.1 KB each), layout fragments 70,
shaping 63, CSSOM 50, calc trees 46, animations only 15.6 MB (9,427 ElementAnimations, 12,767 KeyframeEffects), DOM 15.
Census: 67,569 elements (head 51,138; V leaves 6,144 + 768 rows; carriers 7,680 + 768 embedding; 9,223 view-timelines);
CSS 40 MB (39,513 @property, 9,232 @keyframes, 13.1 MB per-layer `.shared-fc-cN` rules; two elements with 24,107 / 16,158
`initial` resets). Fonts 283 faces, all force-loaded by the witness barrier.
Ranked levers: T1 fewer/cheaper carriers on fc/proj/attn (3.0–3.6 s of style) → R5C; T2 `1ch` scores (1.0–1.3 s + the p-
growing recalcs in Layout) → R5H; T3 2.0 frames/layer (−0.7 s) → R5C; M1 Oilpan garbage (−1…−3 GB); M2 decoded fonts
(−0.3…−0.5 GB); M3 property tries (−0.1…−0.3 GB); M4 instance caches (−0.3 GB). E1: no inert per-pass population found
(dead-element floor ≤0.2 s).

## Bundles built (offline PASS; Chrome runs gated)

| Bundle | Change | Offline | Chrome |
|---|---|---|---|
| **R5H** (cap 8, **READY 14:31, 8/8, verify rc 0**), R5H-c32 | scores via `1ch` on empty elements carrying the dot-font instance (cmap '0' → dot glyph, other tables byte-identical); 12 per-head chains of `capacity` nested slot elements; removes R4S chain + score timelines; 2.5 frames/layer, no interleaved container recalcs (expect RecalcStyleCount flat 84 at cap 32) | flag-off byte-identical to combined7 / combined7-c32; rule diff confined; witnesses identical modulo 12 dot paths; NumPy 8/8 + 32/32 | smoke trio: identical tokens ×3; pass structure = R4S (token 1: 20 frames / 41 ULT / 26 layouts; flag-off 21 / 47 / 30); correctness 8/8. **R5H-c32 prompt 40: 32/32 ids, 918.2 s** (best prompt-40 total so far; c32c run C 1,008.6, combined7-c32 run A 1,050.1, all in the swap-pressured state), fit 12.7 + 0.97·k (lowest intercept yet), **RecalcStyleCount flat 72/token** (c32c 84; R4S 126 + 70.8·k), LayoutCount 64, RSS 3.5–4.5 GB, swap 2.8 → 3.1 GB during the run |
| **R5C** (cap 8, **READY 15:35, 8/8, verify rc 0**) | ctx hop (768) off timelines onto 3 anchor→fixed-size-container chains × 128 (forced by the 256-axis attn shard fonts); fan-in via position:fixed sum scrollers; `--range-attn` becomes a data-independent bound (exact-class, not bit-identical); 4 passes = **2.0 frames/layer**, −769 carriers; max depth 342/512 | flag-off byte-identical; mappings verified for all 384 containers; witnesses 283/283; NumPy 8/8; +4,215 elements | smoke pair: identical tokens; token-1 structure 17 frames / 35 ULT / 22 layouts vs ref 20 / 41 / 26 (2 layers) — the frame reduction is real; 8-token correctness queued behind R5H-c32; predicted −0.8 ± 0.4 s/token |
| **R5M** (cap 8, **READY 14:3x, 8/8, verify rc 0**) | `R5M_HEAD_LITERAL`: the 50,257 head rows carry a literal `width:calc-size(...)` instead of inherited `--base/--tie` custom properties → elements declaring inherited custom properties 50,687 → 430; expected −220 MB of live property tries and less garbage per head restyle; index.html 6.5 → 9.9 MB | flag-off byte-identical; css + 283/283 witnesses identical; each literal == reference `--base`; NumPy 8/8 | correctness 8/8; RSS peak 4,414 MB (combined7 clean-state 5.7–6.0 GB; today's swap state deflates RSS, so B6's paired RSS column decides) |
| **R5E** (cap 8, **READY 16:01, 8/8, verify rc 0**) | dead weight is declarations, not elements: `.core-reset` 16,156 `--p:initial` all no-ops → 0; `.head-isolation` 24,105 → 3,865; 4,992 `--lp` inherit forwards removed (inherits:true instead); 9 unread lists and 7 diagnostic probes dropped (`R5E_KEEP_DIAG=1` restores) → sheet −793 KB, the 163-element per-layer pass loses 322 KB of its 3.38 MB | flag-off byte-identical; CSS diff confined; witnesses 283/283; NumPy 8/8 | smoke pair identical tokens (after a harness fix: invalidationTracking trace exceeded V8 string length); correctness 8/8; B6 pairs next; predicted −0.2…−0.3 s/token |

R5E structural remainder (not exactly removable at cap 8): unfilled `display:none` V leaves still style-resolved when
their row is dirtied (0.14 s/token mean, 0.65 at p=1 of a cap-32 run — a c32 lever via suffix wrappers); non-current KV
banks re-examine 37·(W+1) in-delay transitions per restyle (≈0.25 s/token at token 8); ≈10.3 MB (26 %) of the sheet is
layer-invariant text repeated in the 12 per-layer rule variants (memory-only lever).

R5M measurements (fixtures, R5M.md): decoded fonts = **1,230 MB** resident for the 283 faces (914 MB sfnt, 881 MB HVAR,
×1.35 — the raw woff2 seems kept too); not released by GC or simulated critical pressure; every face is used at cap 8 and
unused declared faces cost 0 (lazy) → the witness barrier is not the problem; irreducible without a smaller weight
representation → agent R5F (font compaction). Font instances ≈ 0 MB each (even the 54 MB head faces); leaf instances
6–14 KB; ≈2.6k new instances/token → instance caches are not the lever. Live view-timeline animations 9,216 ≈ 35–70 MB.
DOM/style 2.5–2.8 KB per laid-out element; the unlocked head subtree ≈ 0.9 GB (= the +2 GB of token 1). Garbage per token:
V-leaf subtree 25,351 elements × 12 restyles ≈ 1.0 GB (75 %), query/bank/reader passes 0.23 GB, head 0.12 GB.

## R5F — weight-font memory (R5F.md; offline, fixtures gated)

Of the 914 MB decoded sfnt, 883 MB is HVAR. Two encoding wastes: each 9-bit weight is stored twice as int16 (a signed
axis needs a −w and a +w region), and every 256-axis face carries a 786 KB VarRegionList (512 regions × 256 axes × 6 B,
spec-mandated) → region lists 207 MB (23 %), delta rows 676 MB; ≈45 bits stored per weight vs a ≈240 MB quantisation floor.
- Tier 1 (font-only swap, advances identical at 45 M checked cells): strip outlines/name/STAT −25 MB; **embedding font
  −26.9 MB** (a fontTools bug wrote NumShorts 0xC451 → LONG_WORDS with 17,489 int32 columns for max|δ| 7,312; woff2 had
  hidden it). Total −52 MB (−5.7 %).
- Tier 2 (−19…−26 %, −170…−236 MB): merge same-tag shard faces across layers into 18–36 files (one VarRegionList each);
  demonstrated on layer-0 A-group −20.0 % with 12.4 M cells identical, but needs a PUA codepoint re-allocation in the
  emitter (R5X-level). Recipe in R5F.md §6.
- Rejected with evidence: 8-bit columns (every column has |δ| = 255), VarStore.optimize (reorders), single-region signed
  axis (halves the F2Dot14 grid), .ttf vs .woff2 (memory-infra shows the raw woff2 is not retained — R5M's ×1.35 is
  unattributed). Chrome acceptance of the tier-1 encodings still needs a smoke.

## B6 paired benches vs `combined7` (bench/paired-round5.md; lock held per pair; RSS columns)

| Candidate | Valid pairs | Cand median s/tok | Δ median [range] | Δ RSS peak | Pass deltas | Verdict |
|---|---:|---:|---:|---:|---|---|
| R5H (`1ch` scores) | 3 | 17.3 | +0.5 [−0.6 … +1.1] | +0 MB [−289 … +397] | recalcs/tok 435.8 → 71.2 (R4S's position-growing recalcs gone: combined7 249 → 647 across tokens, R5H flat 71); layouts 64 = 64 | not distinguishable at cap 8 (its lever is cap 32: R5H-c32 918 s vs 1,009–1,050) |
| R5M (head-row literal widths) | 3 | 17.2 | −1.9 [−3.7 … +0.2] (signs disagree; refs drifted +1.9 over the window) | **+239 MB [+115 … +475], same sign ×3** | recalcs/layouts identical | time not distinguishable; **memory NOT cut — the 50,257 inline `calc-size()` declarations cost more CSSOM than the inherited properties they replaced** → not adopted |
| R5C (ctx hop on 3×128 anchor chains, 2.0 frames/layer) | 3 | 18.9 | **+1.6 [+1.3 … +1.9], REAL regression** (ref drift 0.4) | −27 MB | recalcs/tok **+4,596** (= 384 size containers × 12 layers of interleaved container recalcs), layouts −12 | **CLOSED**: every size container in a chain costs an interleaved style recalc (~0.35 ms each); the 6 frames saved (≈0.7 s) are outweighed by 4.6k recalcs/token. Same mechanism as R4S's cap-32 penalty, now at cap 8. Anchor/container chains are only viable for ≲100 values per layer. R5C.md §5: smoke qkv-pass Layout 65 → 152 ms (161 → 1,370 dirty objects) = 0.23 ms per chain container at cap 2, 0.35 ms at cap 8; break-even ≈100–140 containers/layer; no variant gets a 768-value hop below that (2 values/container is the unit limit; anchor-size() never reaches font-variation-settings; 256-axis fonts fix the depth) → route closed for hops > ≈100 values. `bundles/R5C/DO-NOT-MERGE` |
| R5E (dead declarations removed) | 3 | — | +0.0 [−0.7 … +0.8] | — | recalcs/layouts −20/−20 per 8 tokens (probe removal) | not distinguishable (predicted −0.15…−0.3, below today's noise); exact and harmless — keep as hygiene in the merge |
| **combined8** (combined7 + R5E + R5H) | 4 | 15.7–16.1 | **−1.0 [−1.6 … −0.5], all 4 same sign, "probably real"** (adjacent-ref swing 1.4) | +124 MB [+67 … +259] (R5H's 12 dot faces + chains) | recalcs/tok −365 (R4S recalcs gone), layouts 0 | best cap-8 totals 122.5 / 122.8 s per 8 tokens (≈15.3 s/token); adopt as the new base |

Machine-state caveat for all round-5 absolute numbers (B6): today's combined7 reference runs show a per-token slope of
≈0.91 s/token² (medians 17.2 13.6 15.2 16.3 17.0 18.9 20.4 21.6) vs 0.05 in round 4's quiet-machine pairs — the swap-loaded
16 GB machine makes even capacity-8 runs grow with position, in both arms. Only paired Δs are comparable to round 4.

## R5X — merge: `combined8` (cap 8) = combined7 + R5E + R5H; `combined8-c32` (cap 32, widths, R4D, R4T 64, R5E, R5H, no R4S)

Offline PASS (R4M protocol): flags-off twins byte-identical to combined7 / combined7-c32; R5E-only == R5E, R5H-only == R5H /
R5H-c32; owners' checkers PASS at both capacities; witnesses 271/283 identical + the 12 dot faces; NumPy 8/8 and 32/32
(prompt 40); no JS. Elements 67,569 → 67,524. R5C (regression) and R5M (memory-negative) excluded. Chrome correctness +
c32 prompt-40 run armed behind the gate. Incident: three parallel builds at 16:23 pushed swap to 4.9 GB and closed the
gate (rule: one build at a time, never during a benched pair). **combined8 READY 17:0x: 8/8 ids, verify rc 0.** **combined8-c32 prompt 40: 32/32 ids, 905.6 s** (R5H-c32 918.2; c32c run C 1,008.6; all swap-pressured, swap 3.3 GB here), fit 12.7 + 0.94·k, RecalcStyleCount flat 72, LayoutCount 64, RSS peak 4.4 GB → the best verified 32-token demo bundle. B6 pairs combined8 at cap 8 next.

B6 round-wide: 16 valid pairs, 32 runs, 32 × 8/8 ids, 0 invalid pairs. combined7 itself ran 15.4–19.9 s/token today (median
≈16.8) vs 16.0 on 09-21. Within-state paired ΔRSS: R5M +239, combined8 +124, R5C −27, R5E −15, R5H ≈0 — **no round-5 page
change reduced memory**; the memory levers that remain are the launcher flags (R5G, pending) and the font-merge recipe
(R5F tier 2, −200 MB, needs an emitter codepoint re-allocation).

## R5G — stock launcher flags for memory (R5G.md; n=1 pairs vs no-flag combined7, footprint via /usr/bin/footprint)

| Flag set | Δ footprint peak | Δ s/token | Δ page load | Verdict |
|---|---:|---:|---:|---|
| `--js-flags=--heap-growing-percent=10 --optimize-for-size` | −201 MB (ref spread 231 MB → not established) | +0.4 | **+32 s** | no |
| `… --memory-saver-mode` | +155 MB | +0.3 | +0.1 s | null |
| `--enable-low-end-device-mode` | **−2.8 GB** (6.4 → 3.6 GB), −2.3 GB settled | **+60 (17 → 77 s/token)**, passes differ | — | memory-for-time in the wrong direction; opt-in `--low-memory` at most |

RSS (`ps`) undercounts ≈1.8 GB of compressed pages in today's swap-loaded state; footprint peaks 6.15–6.38 GB match R5A's
6.24 GB memory-infra figure. The ≈3 GB committed-but-free Oilpan heap is not reachable by any stock launch flag found.
Recommendation: launcher unchanged (`--js-flags=--heap-growing-percent=10` only).

## Round 5 — conclusions (2026-09-24 18:00)

- **New base: `combined8`** (combined7 + R5E dead-declaration removal + R5H `1ch` scores): paired **−1.0 s/token [−1.6 … −0.5]**,
  4/4 pairs, best 8-token totals 122.5 s (≈15.3 s/token); recalcs/token 436 → 71. **`combined8-c32`: 32/32 on prompt 40 in
  905.6 s** in the swap-pressured state (previous best in that state 1,008.6) — the demo bundle.
- **Closed routes**: anchor/size-container chains for hops > ≈100 values (R5C: 0.35 ms per container per layer of interleaved
  recalc; +1.6 s/token at 384 containers); head-row literal widths (R5M: +239 MB); leaf var()-substitution precat (R4W);
  every stock memory flag (R5G). The exact capacity-8 floor with view-timeline transport sits at ≈15–16 s/token: the
  fc/proj/attn carriers (3.0–3.6 s of style), PrePaint/animate/paint servicing (≈4.7 s), head (≈2.6 s), GC (1.2–1.7 s).
- **Memory**: 6.2 GB footprint = Oilpan 3.9 GB (0.92 live; the rest is swept var()-substitution garbage kept committed) +
  decoded fonts 1.23 GB (at the HVAR format floor for identical math; −52 MB font-only, −200 MB via cross-layer face merge
  needing an emitter codepoint re-allocation) + instance/shape caches 0.83 GB + strings 0.35 GB. No page-side or flag-side
  change in round 5 reduced it within one memory state. Remaining exact levers: R5F tier 2 (−200 MB), fewer registered
  properties visible at the 50k head rows (468 MB of tries), and — the big one — a transport that does not re-substitute
  ≈1 GB/token of list text (not found in stock Chrome).
- **Protocol lessons**: on a 16 GB machine the renderer's 6 GB pushes swap onto the disk; gate every Chrome launch on AC +
  free disk + swap; one build at a time and never during a benched pair; measure memory as phys_footprint, not RSS.
