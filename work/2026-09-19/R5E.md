# R5E — element/declaration floor: what every style pass re-applies for nothing at capacity 8 (2026-09-24)

Agent R5E. Tools copy `work/2026-09-19/R5E/tools` (= `R4M/tools7` + `r5e_dead_weight.py`, 5 files edited; `R5E/tools-vs-tools7.diff`, 455 lines).
Bundles: `bundles/R5E` (12 layers, cap 8; `BUILD.md` = recipe + flags + offline results + diff), `bundles/smoke-R5E-2L-ref` / `bundles/smoke-R5E-2L`
(2 layers, cap 8, flags off / on). Scratch `R5E/` (census, checkers, harness copies, runs). Log `R5E.log.md`. Nothing under the repo's `tools/` or
`experiments/` touched; no git.

STATUS (16:05): COMPLETE — `bundles/R5E/READY` written 16:00:59 (8/8 ids, verify rc 0, residual rmse 0.016055 = combined7's). History: offline-complete at 13:05; Chrome was PENDING — `R5E/run_chain.sh` (nohup) is parked on the coordinator's machine gate (free disk ≥ 3.0 GB AND swap used
< 3,000 MB AND AC, 60 s poll; at hand-back: 0.27 GB free, swap 4.8–5.3 GB). When the gate opens it runs, unattended: smoke pair (light trace + invalidation
tracking) → token check → ONE 8-token correctness run with a 1 Hz RSS sampler → `R5E/finish.sh` appends §4 here and creates `bundles/R5E/READY` only on
8/8 ids + verify rc 0 (`R5E/CHAIN-DONE`, `R5E/FINISH-DONE` mark completion). **No READY yet.**

## 0. Headline

- **The per-pass populations of combined7 are almost all live.** Of the ≈14.4k element restyles a layer's five passes perform (163 + 2,366 + 824 + 3,141 + 800, R5A's measured
  histogram, §1a; plus 768 V rows + 6,144 leaves once per layer interleaved in Layout),
  the only *elements* that carry no value are the 768·(8−p) V glyph leaves of unfilled slots (R4D already `display:none`s them, but a `display:none`
  child of a dirtied row is still style-resolved: ≈4.45 µs each) and 7 diagnostic readback nodes. The dead weight is mostly **declarations, not elements**:
  two single elements re-apply 40,261 `--p:initial` resets (772 KB) on every restyle, of which **36,396 are provably no-ops** (`.core-reset`: all 16,156 —
  no ancestor declares any of them; `.head-isolation`: 20,240 of 24,105), plus 4,992 `--lp-i:inherit` forwards per layer pass and 9 unread list declarations.
- **Removed behind four flags (default on), all exact by construction, offline-verified (`R5E/offline_check.py`: PASS at 2 and 12 layers; flags-off build
  byte-identical to combined7; witnesses 283/283; NumPy 8/8; static no-JS):** `R5E_LEAN_WALLS` (mechanical wall shrink: keep only properties some
  ancestor-or-self declares, animates or sets inline), `R5E_LP_INHERIT` (no forwards), `R5E_DROP_DEAD_LISTS`, `R5E_KEEP_DIAG=0` (3 probe pairs +
  `#core-epoch-observer` gone; `=1` restores them for geometry-readback diagnostics). Sheet −793 KB (2 %), inline styles −51 KB, elements −7.
- **Predicted (cost law, §3): −0.17 … −0.31 s/token (16.0 → ≈15.7–15.85), i.e. 1–2 %; RSS: small (< 20 MB).** This is the whole exact, containment-free
  dead-weight budget at capacity 8. The remaining "dead per pass" work is structural: unfilled V leaves ≈0.14 s/token averaged over tokens 1–8 (0.29 at
  token 1, 0 at token 8; ≈0.65 s/token at token 1 of a capacity-32 run) with no exact CSS-containment fix at cap 8 (§5), and the in-delay latch transitions
  of the 11 non-current KV banks that every bank restyle re-examines (structural to the nested-bank design). Per-layer rule duplication (≈10.3 MB of the
  39 MB sheet is layer-invariant text repeated 12×) is a memory-only lever (R5M), not a per-pass one.

## 1. Census — what a style pass at capacity 8 restyles

### 1a. Measured pass histogram of the real 12-layer combined7 (R5A's traced run `R5A/run-combined7/mem8-3`, 8/8 ids, 138.8 s, B0's `parse_trace.py`; per token, tokens 2–8 are alike)

| `UpdateLayoutTree` elementCount | passes / token | Σ ms / token (tok 2 → tok 8) | ms / pass | µs / element | population (inferred from subtree sizes; §1b) |
|---:|---:|---:|---:|---:|---|
| 3,141 | 12 | 1,311 → 1,320 | 109 | 35 | fc stage: `.shared-fc` (+LN2 138 KB) + 3,072 fc carriers + 48 `.shared-fc-cN` (23 KB rule each) + receipt/gate |
| 824 | 12 | 1,285 → 1,335 | 107 | 130 | fc readback (rooted at the 48 `.shared-fc-cN`, 3,072 changed timelines) → proj stage: `.shared-proj` (444 KB) + 768 proj carriers + `.reused-output` (+ `#reused-probe` pair) — declaration-bound |
| **163** | 12 | 949 → 1,258 | 79–105 | **≈500** | **qkv readback → KV/score stage** (smoke census §4.1: rooted at the 36 `.shared-qkv-cN`, 2,303 changed timelines): 36 qkv chunks (10 KB decode rules each) + receipt/gate + `.fvs-query` (248 KB: 1,536 `--fvn` calcs, live lists) + 12 nested banks (write/alias rules + 37·(W+1) in-delay transitions each) + 48 `.fvs-sc` + 96 score glyphs (each substituting a 12.7 KB K list) + score reader/softmax; the V rows/leaves follow inside this frame's Layout. Grows 949 → 1,258 ms with the filled positions (more latched transitions, more filled score lists) — all live |
| 2,366 | 11 (+1 × 2,405 at layer 0) | 824 → 964 | 75 | 32 | S1 (rooted at the 12 `.loop-reader-cN`, 768 proj timelines, + `.core-pass-reader` = the `--pass`/`--layer` flip): `.loop-input` (768 decodes + forwards) → `.reused-input` (**16k dead resets**) → `.shared-qkv` (LN1 138 KB) + 2,304 qkv carriers + 36 `.shared-qkv-cN` + receipt — the pass R5E shrinks |
| 800 | 12 | 351 → 373 | 29 | 37 | ctx readback (rooted at the 12 `.cache-bridge-cN`) → attn stage: `.shared-attn` + 768 attn carriers + 12 `.shared-attn-cN` + receipt/gate |
| 50,898 | 1 | 372 → 417 | 372–417 | 7.3 | head frame |
| 895 / 791 / 39 / 6 / 1 | 1 each (1 ×2) | ≈120 | | | token boundary: export shown (770 carriers + probe + b11 chain + final LN + head bank + wall), embedding carriers (768), handshake |
| **total** | **≈62 passes** | **5.3 → 6.1 s style / token** | | | + interleaved container recalcs inside Layout (R4S chain → softmax → 768 V rows + 6,144 leaves, once per layer; `RecalcStyleCount` 134 + 65·k per token counts them, R4M §4.1) |

Two things this table shows that the round-4 notes did not: (i) **there is no ≈7k-element pass** — the V rows/leaves are restyled once per layer *inside the qkv frame's
Layout* (R4S §5), so their cost hides in `LayoutDuration`/interleaved recalcs, not in the pass histogram; (ii) **the 163-element KV/score pass is the third-largest
style item (≈1.0–1.3 s/token, ≈500 µs per element)** — a pass whose cost is declarations (query lists, bank latches, 12.7 KB score lists), not elements, and the
one that grows with the filled positions. Pass roots were identified from the invalidation-tracked smoke traces (§4.1, `R5E/runs/*/pass_census.md`).

### 1c. The per-layer declaration load of the style-container dependents (`R5E/dependents-163.txt`)

Elements matched by any rule nested in `@container corestate style(--layer:L)` or `@container loopcontrol style(--pass:N)`: **148** (48 `.shared-fc-cN`, 36 `.shared-qkv-cN`,
12 `.shared-attn-cN`, 12 banks, 2 LN, stage roots/receipts/gates, `.fvs-query`, `.reused-input`, `.loop-input`, 6 pass-reader carriers, scrollers/tracks). Each is re-applied
once per layer, in whichever pass reaches it (S1 for `.reused-input`/LN1/qkv; the KV pass for the banks/`.fvs-query`; the gate-open passes for the rest — the smoke census
showed the 163-pass is NOT this set as a whole, see §1a): **3.38 MB of declarations per layer** (one layer/pass/slot variant each; the sheet holds 29.9 MB over all variants)
→ cost law 124 ms (var law) / 64 ms (literal law) per layer. The largest
contributors: `.shared-proj` 444 KB (per-layer `--pk/--pc` constants + base decodes), **`.reused-input` 330 KB — 309 KB of it the dead `.core-reset` resets**, `.fvs-query`
248 KB, LN1/LN2 139 KB each, `.shared-fc` 126 KB, `.shared-qkv` 117 KB, **`.loop-input` 95 KB (13 KB dead forwards)**, 48 fc chunks 23 KB each. R5E removes 322 KB
(9.5 %) of this per-layer load, all of it from the S1 pass ≈ 6–12 ms × 12 = **0.08–0.14 s/token**; the rest is live per-layer arithmetic.

### 1b. Populations (R5A/census.md numbers, re-derived; restyle frequency from §1a and the R3R/R4S pass anatomy)
DOM 67,569 elements (66,239 `<i>`), max depth 164. Populations by role (elements × declared bytes applied per restyle × restyles per token):

| population | elements | declared bytes / element | restyled | live value? | dead share |
|---|---:|---:|---|---|---|
| head `.full-head` (50,257 `.head-row` + 197 groups + 256 fine rows + reductions) | 51,138 | 25 B inline + rule | 1 pass/token (head frame, ≈50.9k elements, ≈400–500 ms); display-locked (R2D) otherwise | yes | 0 (R3H's domain: the 256 `.head-fine-row:nth-child(N)` rules carry 15 KB `if()` chains each = 3.9 MB, per token) |
| stage carriers `.metric` (qkv 2,304 / attn 768 / fc 3,072 / proj 768) | 6,912 | ≈50 B inline | 1 pass per layer each | yes | 0 |
| b11 bridge carriers + probe | 770 | ≈50 B | shown only while `--held:1` (display:none otherwise → children not resolved) | yes | probe pair (19 KB calc) |
| **V glyph leaves `.fvs-v-H-S`** | 6,144 | ≈70 B rule (+12 B list when unfilled) | once per layer, interleaved in the qkv frame's Layout (R4S §5) | **768·p live, 768·(8−p) unfilled = `display:none` but still resolved** | 768·(8−p) × 12 × 4.45 µs = 0.29 s/token at p=1 … 0 at p=8; mean over 8 tokens ≈ **0.14 s/token** |
| V rows `.metric.fvs-value-row` | 768 | 180 B inline | same interleaved recalc | yes | 0 |
| KV banks `.fvs-bank-L` (nested 12 deep) | 12 | 7 KB literal transition list + write/alias rules for the current layer | every pass that dirties the bank subtree (≥1/layer) | the current layer's bank | 11 non-current banks: each restyle re-examines 37·(W+1) in-delay transitions (F4 §4: ≈5.7 µs each → ≈11 ms/pass at token 8) — structural |
| score glyphs + R4S chain | 96 + 48 | 12.7 KB list (filled) / 12 B (unfilled) | 1 pass per layer (+ interleaved container recalcs) | 12·p live | masked by `--fv-S`; 12·(8−p) elements ≈ 0 |
| consumer chunks (R4T) `.shared-*-cN`, `.cache-bridge-cN`, `.b11-bridge-cN`, `.loop-reader-cN`, `.embedding-consumer-N` | 144 | 10–23 KB (per-layer rule) | 1 pass per layer each | yes | `.loop-reader-cK`: 4,224 `--lp:inherit` forwards + 768 on `.loop-input` per layer = 103 KB of pure forwarding → **removed (R5E_LP_INHERIT)** |
| `.reused-input` = `.core-valid` = **`.core-reset`** (one element) | 1 | 769 var() (live) + **16,156 `--p:initial` = 309 KB** | every layer pass in which `--pass` advances (`@container loopcontrol` reader) + token-boundary unlock cascades ≈ 15/token | `--x-i:var(--loop-in-i)`, `--valid-*` live | **all 16,156 resets dead** (no ancestor declares `--hidden/--fcp/--qkv/--qkvp/--n1/--n2/--ctx/--r/--out/--attnp/--projp/--max/--den/--mean/--var`; legacy of the nested-block core) → **removed** |
| **`.head-isolation`** wall | 1 | **24,105 `--p:initial` = 463 KB** | ≈5/token (bridge show + hide, `--epoch`, embedding `--x`, `--embed*`) | 3,865 resets pin properties that DO change above it (`--x`, `--embed`, `--embedp`, `--bridge-p`, `--final-h` ×768, `--feedback(-p)` ×8, 9 singles) | **20,240 dead** (core-only families never reach the head branch) → **removed** |
| `.fvs-query` | 1 | 248 KB / 96 rules (`--fvn-*` 1,536 calcs, live lists) | ≥1/layer | yes | `--fvs-all-fields` + 8 `--fvs-retained-S` = 15.8 KB unread → **removed** |
| `.position-embedding` | 1 | 242 KB: 768 × 8-branch `if(style(--epoch:k))` | 2/token | yes | 0 dead; could be 8 container rules with literals (per-token lever ≈ 10–30 ms, not done) |
| `.final-normalization` / `.head-input-bank` | 2 | 158 / 71 KB | per token | yes | 0 |
| readback probes `#core-probe`, `#block-11-probe`, `#reused-probe` (+ epoch twins), `#core-epoch-observer` | 7 | 15–19 KB inline calc over 768 var() each, position:fixed (layout each change) | `#reused-probe`: every layer (proj pass, inside `.reused-output`); others per token | **no** (harness reads computed styles of `#core-result`, `.head-input-bank`, `.fvs-bank-L`, `.token-slot-N`) | **removed (R5E_KEEP_DIAG=0)** |
| font barrier (283 `.font-witness` + 283 `.font-proof` + 21) | 587 | 60 B | never per pass (body-level, no inherited writes reach them) | fonts alive | 0 |
| controller / handshake / feedback | ≈120 | small | per pass (`:has()` scoped by R2G) | yes | 0 |

Body-level inherited writes: none per pass (`--epoch`, `--token`, `--feedback-*` are F5-private; `--prompt-token` changes only on the select) → no whole-document pass.

## 2. What changed and why it is exact (`R5E/tools/r5e_dead_weight.py`; details in `bundles/R5E/BUILD.md`)

1. **`R5E_LEAN_WALLS` — mechanical wall shrink.** At build time, after the page and sheet are assembled (after R2G's `:has()` scoping), `lean_walls()` parses
   the page, takes the ancestor-or-self chain of the wall element (38 / 37 elements), and collects every custom property that (a) a rule whose rightmost
   compound can match one of them declares (pseudo-classes ignored = superset match), (b) an inline style on one of them declares, or (c) a `@keyframes`
   referenced by an `animation(-name)` on such a rule animates. Every `--p:initial` whose `--p` is not in that set is dropped. Exactness: a registered property
   that no ancestor declares, animates or sets inline is at its initial value on the wall's parent, so `initial` on the wall changes neither the wall's
   computed value nor anything its descendants inherit; every property that *can* change above the wall stays pinned, so the wall's ComputedStyle is
   unchanged by upstream writes exactly as before (the head's protection is intact). Result on combined7's page: `.core-reset` 16,156 → 0 (no `--hidden-*`,
   `--qkv-*`, … is declared above it — the reset is a leftover of the nested-block core where block k+1 sat inside block k's output); `.head-isolation`
   24,105 → 3,865 (kept: `--bridge-p-N`, `--embed-N`, `--embedp-N`, `--x-N`, `--final-h-N` ×768; `--feedback-N`, `--feedback-p-N` ×8; `--bridge-ready`,
   `--bridge-stamp`, `--embed-ready`, `--embed-stamp`, `--epoch`, `--final-mean`, `--final-var`, `--frozen-prompt`, `--token`). The kept set is the
   ancestor-declared/animated set — no hand-written list (memory rule: keep-lists must be mechanical). A first version attributed keyframes bodies to the
   *previous* prelude (nested `from{}`/`to{}` blocks close before their `@keyframes`), which dropped `--embedp-*` and one `--bridge-p-*`; caught in the dry
   run, fixed, and the checker now re-derives the kept set independently on the reference page.
2. **`R5E_LP_INHERIT`.** `--lp-*` are registered `inherits:true` by `r3r_fold_hop` and were flipped to `inherits:false` by the core's scoped_state, then
   forwarded with `--lp-i:inherit` one level (`.loop-input`, 768) and — since R4T's 12 nested chunks — on every chunk (`.loop-reader-cK` forwards k·64;
   4,224 in total). With the flag the flip and the forwards are gone. The values at `.loop-input` are identical; the elements that now inherit `--lp-*`
   (the `.loop-input` subtree) are exactly those that `--loop-in-*` (inherits:true, decoded from `--lp-*` in the same pass) already dirty, so no pass is
   added. Inherited-variable maps are shared by pointer below `.loop-input`, so no per-element memory.
3. **`R5E_DROP_DEAD_LISTS`.** `.fvs-query{--fvs-all-fields:…}` and `--fvs-retained-S` were only referenced through `var()` when `F5_BANK_LITERAL_LISTS=0`;
   with literal lists (combined7) the sheet has 0 readers (checked). Unregistered, unread → no observable effect.
4. **`R5E_KEEP_DIAG=0`.** `hybrid.probe()` emits a position:fixed `<i class="readback">` whose width is a 768-term `var()` checksum plus an epoch twin;
   three such pairs exist (`#core-probe` in `#core-result`, `#block-11-probe` in the export, `#reused-probe` in the proj output) and `#core-epoch-observer`
   reads the export twin's anchor. They were geometry readbacks for older harnesses; the current verifier and `correctness_run.mjs` read computed styles
   of elements that remain. F5's inline-reader count checks were adjusted (epoch readers 3 → 2 in the model, 6 → 5 / position 2 → 1 in the core) under the flag.

Not changed (why): the unfilled V leaves (§5), the non-current bank transitions (values live in them), the per-layer rule duplicates (memory only),
`.position-embedding` / `.head-fine-row` `if()` chains (per token; small; other owners).

## 3. Before / after and predicted saving (cost law: 4.45 µs/element + 36.5 ns/B for `var()` declarations; literals 2.83 µs + 18.7 ns/B, or ≈0.72 µs per short literal declaration, SYNTHESIS §8.1/§8.3)

| item | per restyle before → after | restyles / token | saving / token |
|---|---|---:|---:|
| `.core-reset` resets | 16,156 decl / 309 KB → 0 | ≈15 (12 layer passes + token-boundary cascades) | 5.8–11.6 ms × 15 = **87–175 ms** |
| `.head-isolation` resets | 24,105 / 463 KB → 3,865 / 79 KB | ≈5 | 7.2–14.6 ms × 5 = **36–73 ms** |
| `--lp` forwards | 4,992 decl / 103 KB → 0 (per layer pass, over 13 elements) | 12 | 1.9–3.6 ms × 12 = **23–43 ms** |
| dead `.fvs-query` lists | 15.8 KB → 0 | ≈12–24 | 0.3 ms × 12–24 = **4–7 ms** |
| probes | `#reused-probe` 16.4 KB var() calc + fixed-box layout per layer; 2 pairs per token | 12 + 2 | ≈ **15 ms** |
| **total** | sheet −793 KB, inline −51 KB, −7 elements, −36,396 + −4,992 + −9 declarations applied per token-cycle | | **≈ −0.17 … −0.31 s/token** (16.0 → ≈15.7–15.85) |

Elements per pass: unchanged except −1 (`#reused-probe`) in the proj pass and −2/−3 in the token-boundary passes; declaration bytes per pass: the loop/D1
pass −412 KB (core-reset + forwards), the proj pass −16 KB, token-boundary passes −384 KB each (head wall). RSS: ≈40k fewer parsed declarations
(≈ −5…−10 MB of rule storage) and 7 fewer LayoutObjects — not a memory lever.

## 4. Chrome

### 4.1 2-layer smoke pair (cap 8; `R5E/run_smoke.sh smoke2L`, R4T's `run_bundle.mjs` + invalidationTracking for the first 3 tokens; 15:53–15:57 under the lock, AC, load 5.5; `R5E/runs/smoke-R5E-2L{-ref,}`)

- **Tokens identical: ref = cand = [11, 3387, 3387, 3387, 3387, 3387, 3387, 3387]** (2-layer reference prefix 11, 3387 as in every prior 2-layer smoke), done markers 8/8 both, rc 0 both.
  Whole-session counters ref / cand: RecalcStyleCount 749 / 749, LayoutCount 124 / 124 (identical pass and layout counts).
- Per-pass comparison (`R5E/compare_frames.py` → `R5E/runs/compare_frames.txt`, tokens 1–3 traced): frames 36 / 36, UpdateLayoutTree 80 / 80, Layout 51 / 51;
  **elements restyled 213,760 → 213,734 (−26 = the removed probe pairs: 2,405 → 2,403, 895 → 893, 791 → 789, 2,393 → 2,391, 50,898 → 50,896, 113 → 111)**;
  style 7,462 → 7,369 ms (−1.2 %), layout 5,506 → 5,474 ms. Recurring passes (ms per pass, ref → cand): S1 2,366-el **66.9 → 59.0 (−12 %, the `.core-reset` pass)**;
  token-boundary head-wall passes 2,405-el 115 → 94, 2,393-el 108 → 88, 895-el 61 → 51; unchanged within noise: fc 3,141-el 322 → 321, KV/score 153-el 79.4 → 78.9,
  proj 824-el 115 → 120, attn 800-el 92 → 94. Scaled to 12 layers: −8 ms × 12 (S1) − ≈50 ms (boundary) ≈ **−0.15 s/token**, the low end of §3's −0.17…−0.31.
- Pass roots from the invalidation events (`R5E/runs/*/pass_census.md`; every `StyleRecalcInvalidationTracking` in the generate window is a `ScrollTimeline`
  invalidation on a consumer chunk or a `Related style rule` on the handshake nodes): 3,141-pass ← 768 `.shared-attn-cN` timelines (attn readback → fc stage);
  824 ← 3,072 `.shared-fc-cN` (fc readback → proj); 800 ← 768 `.cache-bridge-cN` (ctx → attn); **153 ← 2,303 `.shared-qkv-cN` (qkv readback → KV/score stage)**;
  2,366 ← 768 `.loop-reader-cN` + `.core-pass-reader` (proj readback = S1 + `--pass` flip); 2,405/2,393 ← 768 `.bN-bridge-cN` (+ 767 `.embedding-consumer-N`) = token
  boundary; 895/113/39 ← handshake `Related style rule` / `Affected by :has()`. 0 interleaved recalcs are tracked inside Layout (container recalcs are not invalidation-tracked).

## 5. The structural remainder (quantified, not removable exactly at capacity 8)

- **Unfilled V leaves.** R4D's `display:none` removes their boxes and layout, but Blink resolves style for a `display:none` child whenever its parent's inherited
  data changed (`StyleRecalcChange::RecalcChildren` after a `kInherited` diff; the leaf is the display:none element itself, so no lock skips it). Each row is one
  output coordinate whose max-content width sums its 8 slot glyphs, so the leaves of a slot cannot be moved under a lockable wrapper without nesting: a per-row
  suffix chain (g0, w1 > [g1, w2 > [g2, …]]) restyles 2p elements per row at fill p instead of 8 — Σ_{p=1..8} 2p = 72 > 64 (net loss at cap 8; −30 % only with
  8-slot groups at cap 32: Σ = 712 vs 1,024). Cost today: 768·(8−p) × 1 interleaved recalc/layer × 12 × 4.45 µs = 0.29 s/token at p=1, mean 0.14 s/token over 8 tokens;
  at capacity 32 the same term is ≈0.65 s/token at p=1 (23.8k idle leaves) — the largest remaining per-pass dead weight, and it is a c32 lever before a cap-8 one.
- **Non-current banks.** The 12 banks are nested ancestors of the V rows (values reach the rows only by inheritance), so every bank is restyled with the subtree;
  each restyle re-examines its 37·(W+1) retained in-delay transitions (F4 §4 ≈5.7 µs each: ≈2 ms per bank at token 8 → ≈20 ms per bank-dirtying pass, ≈0.25 s/token
  at token 8). Un-nesting was F5's plan and is impossible without a downward value path; freezing values without transitions needs state CSS cannot hold.
- **Per-layer rule duplication (memory only).** In the 576 `@container corestate style(--layer:L){.shared-fc-cN{…}}` rules 15,170 of 22,951 B are identical across
  layers (animation names/timelines + the layer-invariant decode text), ≈8.0 MB of the 13.1 MB; qkv chunks 0.76 MB, attn 0.25 MB, LN 1.34 MB → ≈10.3 MB (26 % of
  the sheet) could move to one layer-invariant rule per element with no change to what a restyle applies. Suggested to R5M.
- Per-token items left alone: `.position-embedding` (768 × 8-branch `if(style())`, 242 KB, 2 restyles/token), `.head-fine-row:nth-child(N)` (256 × 197-branch
  `if()`, 3.9 MB, once per token in the head pass).

## 6. Risks

- The wall shrink's matcher ignores pseudo-classes and matches the rightmost compound only (superset of true matches) — it can only keep too much, never too
  little, *provided the page's ancestry is what the build sees*: the DOM is static, so it is. SMIL `<set attributeName="class">` changes classes on `<g>`
  signals only (not ancestors of either wall). Inline `style` on ancestors is included.
- `--lp-*` inheriting: any future rule that reads `--lp-*` below `.loop-input` now sees live values instead of 0 — none exists (grep); R4T's offline checker
  counts forwards and will flag the change (expected).
- Removing probes changes F5's reader-count assertions under the flag only; flags-off is byte-identical to combined7.
- Timing prediction is small (1–2 %) and below B6's pairing noise for a single run; the smoke trace's per-pass ms is the measurable witness.

## 4. Chrome (filled by R5E/finish.sh at 2026-09-24 16:00:35)

### 4.1 2-layer smoke pair (cap 8, light trace + invalidation tracking; `R5E/runs/smoke-R5E-2L{-ref,}`)

- smoke-R5E-2L-ref: "tokens":[11,3387,3387,3387,3387,3387,3387,3387]; "metrics-after","RecalcStyleCount":749,"RecalcStyleDuration":18.805192,"LayoutCount":125,"LayoutDuration":14.342891,"Nodes":131683,"dRecalcSinceIdle":732,"dLayoutSinceIdle":112}
- smoke-R5E-2L: "tokens":[11,3387,3387,3387,3387,3387,3387,3387]; "metrics-after","RecalcStyleCount":747,"RecalcStyleDuration":18.503781,"LayoutCount":121,"LayoutDuration":14.192656,"Nodes":131676,"dRecalcSinceIdle":732,"dLayoutSinceIdle":112}

```

REF smoke-R5E-2L-ref: per token: frames / UpdateLayoutTree / elements restyled / style ms / layouts / layout ms
  token 1: 17 / 37 / 130982 / 4801 / 24 / 3179
  token 2: 9 / 20 / 16334 / 1070 / 13 / 592
  token 3: 10 / 23 / 66444 / 1591 / 14 / 1735
  total : 36 / 80 / 213760 / 7462 / 51 / 5506

CAND smoke-R5E-2L: per token: frames / UpdateLayoutTree / elements restyled / style ms / layouts / layout ms
  token 1: 17 / 37 / 130970 / 4775 / 24 / 3195
  token 2: 9 / 20 / 16328 / 1056 / 13 / 600
  token 3: 10 / 23 / 66436 / 1538 / 14 / 1679
  total : 36 / 80 / 213734 / 7369 / 51 / 5474

recurring pass sizes (elementCount: passes ref/cand, summed ms ref/cand):
    3141:    8/   8     2573/  2564 ms
     824:    8/   8      920/   957 ms
     800:    8/   8      732/   752 ms
   50898:    3/   0     1454/     0 ms
   50896:    0/   3        0/  1425 ms
     153:    7/   7      556/   552 ms
    2366:    4/   4      264/   236 ms
       0:   20/  20      207/   212 ms
    2405:    2/   0      229/     0 ms
    2403:    0/   2        0/   187 ms
       1:    6/   6       62/    62 ms
     895:    2/   0      122/     0 ms
     789:    0/   4        0/   114 ms
    2393:    1/   0      107/     0 ms
     791:    4/   0      101/     0 ms
     893:    0/   2        0/   101 ms
      39:    3/   3       47/    46 ms
    2391:    0/   1        0/    88 ms
       6:    3/   3       35/    33 ms
     113:    1/   0       53/     0 ms
     111:    0/   1        0/    40 ms

elements restyled total ref 213760 cand 213734 (delta -26); style ms 7462 -> 7369; layout ms 5506 -> 5474; frames 36 -> 36
```
- per-pass element census (which classes each pass restyles): `R5E/runs/smoke-R5E-2L-ref/pass_census.md`
- per-pass element census (which classes each pass restyles): `R5E/runs/smoke-R5E-2L/pass_census.md`

### 4.2 ONE 8-token correctness run of `bundles/R5E` (`R5E/run_correctness.sh R5E`, R4M harness, keyboard-free click, heap flag on; NOT a timing run)

- ids: "tokens":[11,314,1101,7926,11,475,314,1101] (required [11,314,1101,7926,11,475,314,1101]); verify rc=0; 'finalResidualError': {'finite': 768, 'rmse': 0.01605519804514142, 'maximum': 0.11651862085027176}
- capture times (5 s poll granularity; indicative only, load ≈4.8): cumulative [23.2, 40.4, 52.9, 85.8, 107.4, 125.7, 142.7, 160.4] s = per token [23.2, 17.2, 12.5, 33.0, 21.5, 18.3, 17.0, 17.7] s, total 160.4 s (combined7's correctness run: 146.8 s at load 5.5; B6 pairs decide); "metrics-after","RecalcStyleCount":3748,"RecalcStyleDuration":70.671286,"LayoutCount":524,"LayoutDuration":81.679995,"Nodes":132331}
- RSS: the script's own sampler matched only the browser process (213 MB; pattern fixed for future runs); a supplementary 1 Hz sampler over the renderer helper processes (`R5E/run-R5E/rss-renderer.log`) covered 15:58:20–16:00:27 (from mid-token 2 to the end): **renderer peak 4900 MB**, first sample 4128 MB, last sample before exit 4081 MB (per-token alignment not attempted: the sampler has no absolute timestamps). combined7 references: R5A traced run peak 4,277 MB (and 2,071 at end), B5 untraced pairs 5.6–5.95 GB at token 8 — single sessions, not comparable at this precision; R5E's change removes ≈40k parsed declarations and 7 boxes and was not expected to move RSS.
- **READY** created (2026-09-24 16:00:59).
READY written
