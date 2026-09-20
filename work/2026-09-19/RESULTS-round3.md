# Round 3 (2026-09-20) — CLOSED at `combined4` = 18.2 s/token; Round 4 (2026-09-21): best exact capacity-8 bundle `combined7` ≈ 16.0 s/token (paired −2.3 vs combined4; −60 % vs baseline 40.2); 32-token demo verified (see Round 4 section)

Base: `combined3` (R2F lean handshake + R2C hoist + R2D knobs), paired −8.7 s/token vs `combined`;
absolute ≈ 24–27 s/token depending on machine load (23.6–24.6 in the cleanest sequential rows).
Bench protocol now: paired interleaving vs `R2F`, no quiet-gate wait (load logged), pointer off page,
**Run triggered by keyboard** (R3K: removes 42–44 forced hover passes ≈ 0.7 s/token; ids/frames
identical). Rows tagged `trigger=keyboard` are ≈0.7 s lower than earlier rows for the same bundle.

## Attribution of the remaining ≈23.6 s (R3A trace of R2F)

| Block | s/token | Lever |
|---|---:|---|
| changed view-timeline carrier animations (102k/token × 40 µs) | 4.1 | R3P: 2 values per carrier (exactness-gated) |
| per-frame fixed servicing (46 × ≈117 ms; timelines serviced 3×/frame) | 4.9 | fewer hops (R3R) → fewer frames; fewer live timelines (R3P) |
| latch transition starts (9,228 × 218 µs) | 2.0 | R3L: pack loop-bank latches |
| per-pass fixed (136 × 12.7 ms) | 1.7 | fewer passes (R3R) |
| head frame | 3.0 | near floor (R3H); block-flow group max −0.3 (in combined4) |
| element floor, unchanged anims, GC, hover pass, selectors | ≈3.5 | R3K (−0.7 hover), GC arms |

## Findings so far

- **R3F**: frame folding is saturated — every hop frame already carries Blink's two style/layout passes;
  3.5 frames/layer is the floor at 7 hops/layer. Bundle = `:has()` scoping only (≈ −0.05 s); skipped in bench.
- **R3H**: the exact 50,257-row head is ≈2.9 s and 53 % per-glyph font work; certified cascades trade
  median for tails/cold; best exact option (block-flow group max) ≈ −0.3 s.
- **R3K**: keyboard-triggered Run removes the per-frame hover recompute (harness artifact) −0.7 s.
- **R3A**: rule matching is 0.25 s/token; the carriers and their servicing dominate (see table).
- **R3L**: numeric packing across var() is impossible (registered numbers substitute as 6-significant-digit text);
  per started transition ≈ 250 µs in the real page (28 µs style + 20 µs paint in isolation); a font-list latch
  (2 transitions/bank) works (−1.8 s predicted) but the hop it latches is gone in R3R.
- **R3R**: the loop-transport hop is removable exactly (proj carriers publish the next layer's input);
  6 hops/layer, 3.0 frames/layer, −9,228 transition starts/token, 8/8 ids.
- **Precision budget is nearly spent** (R3P): further approximations (fused/approximate GELU, lossy packing)
  risk token flips; any such step needs an explicit decision.

## Bundles

| Bundle | Change | Status |
|---|---|---|
| R3F | `:has()` scoping (+ frame analysis) | READY, 8/8; not benched (≈0) |
| R3L | loop-bank latch packing (769 → ≈257 transitions/layer) | superseded by R3R (no loop banks left); fixture data kept as cost-model evidence |
| **R3R** | loop-transport hop removed: proj carriers publish the next layer's input directly; no loop banks, no `--saved-*` latches (−9,228 transition starts/token), −768 anims/layer; 3.0 frames/layer; RecalcStyle 982 / Layout 625 per 8 tok (R3F 1116/720) | **READY, 8/8**, residual rmse 0.0176 (combined3 0.0201); coarse 17–24 s/token; predicted ≈ −3 s untraced vs combined3; benching first (B4) |
| R3P | 2 values per view-timeline carrier | **CLOSED — exactness gate failed for all 8 hops**: every field crosses one 6-significant-digit var() substitution (≤ ~10 exact bits/field); k=12/14 flips ids on qkv/fc/proj/loop; the pinned run's token 4 is 4 q-units from a flip. Lossy variant ≈ −2 s at 2.6× RMSE — not taken without user approval |
| combined4 | combined3 + R3R + R3F `:has()` scoping + R3H block-flow max | READY, 8/8, benched: 18.2 s/token |

Paired results (B4, vs R2F, keyboard trigger both arms; `bench/paired-round3.md`):

| Candidate | Median s/token | Paired Δ vs R2F (3 pairs) | Δ total / 8 tok | ids |
|---|---:|---:|---:|---|
| **R3R** | **19.4** | **−5.0 [−5.4 … −4.5]** (R2F refs 23.8 / 24.0 / 24.5) | −42 s | 8/8 ×3 |
| R3L (font-list latch, superseded) | 22.2 | −3.3 | −28 s | 8/8 ×3 |
| **combined4** (R3R + `:has()` scoping + head block-flow max) | **18.2** | **−6.2 [−6.4 … −6.0]** (4 pairs; R2F refs 24.1–24.9) | −52 s | 8/8 ×4 |

Absolute progression (clean/paired medians): baseline 40.2 → combined 30.3 → R2F 23.6 → R3R 19.4 → **combined4 18.2** (−55 %). Frames 85 → ≈40/token; style passes 175 → ≈123; layouts 109 → ≈78; transition starts 9,228 → ≈312/token.

## Targets

Exact path after round 3: R3R (≈ −3) + R3K (−0.7) + head/`:has()`/GC small items (≈ −0.8) from 23.6
→ ≈ 19–20 s/token. R3P (carrier packing) and R3L (latch packing) are closed/superseded.

**R4A (fused MLP font) — CLOSED**: only a 768-axis font removes the fc boundary; stock Chrome rejects
>256 axes, Fontations accepts them but an exact-class fusion (K≈48 knot GELU, two-level glyphs) needs
≈15 GB of font tables and 200–600 s per layer of evaluation vs the 0.35 s hop removed. Sub-256-axis
variants keep the hop and add error. R3A lever (2) is withdrawn.

**Where this leaves the exact path**: ≈18–19 s/token after combined4 + GC arm + token-carrier detach.
The remainder is Blink's per-carrier animation cost (≈40 µs × ≈90k/token), per-frame servicing of all
live timelines (≈117 ms × ≈40 frames), the exact head (≈3 s) and fixed per-pass costs — all tied to
transporting ≈8k values per layer through view-timelines. Reaching 12 s needs ≈3× fewer transported
values or a cheaper carrier primitive; every primitive in the catalog has been measured (containers/
anchors: quadratic restyle above ≈500 values; font metrics: memory; counters: scope; SVG: 8-bit).
Below that line the options are non-exact or outside the constraints (bounded KV window = model change;
Chromium-side animation/timeline changes = not stock; JS = excluded). Beyond that: fuse fc→proj in one
avar2 font (drops the 3,072-carrier hop; Codex's fused GELU was approximate, so an exact variant is
required) or a lower-cost carrier primitive.


## Round 4 (2026-09-21) — 32-token feasibility (R4C)

`combined4-c32` = combined4's emitter at capacity 32. ONE passive run (AC, keyboard trigger, heap flag ON):
**32/32 ids match the GPT-2 greedy reference; total 1,133 s (18.9 min)** vs Codex's 3,177 s.
Per-token: 25.6 → ≈24 (k=2–7) → 30–32 (k=8–18) → step to ≈45 (k=19–22) → 48–58 (k=23–32);
fit 16.3 + 1.14·k. Style 8.6 → 26 s/token, layout 4.3 → 21.6 s/token (attention work grows with
filled positions), RSS 2.4–5.8 GB (peak at k=9). Capacity step vs cap-8 ≈ +5 s/token from 24,576 V
glyph leaves substituting 8–10 KB lists even for unfilled slots. R4D is implementing: empty lists for
unfilled slots, leaner per-position latches, a heap-flag-off arm to test whether the k≈19–22 step is GC.

### Round 4 — capacity-8 paired results (B5, bench/paired-round4.md; keyboard trigger both arms, valid pairs only)

| Candidate | Valid pairs | Cand median s/tok | Δ median vs combined4 [range] | Δ / 8 tok | Machine | Verdict |
|---|---:|---:|---:|---:|---|---|
| R4S (scores hop → anchor chain) | 3 | 16.4 | −0.6 [−0.9 … −0.4] | −3.2 s | load 5.6, hog on both arms | REAL |
| R4T (chunk 64, all sites) | 3 | 19.1 | 0.0 [−2.5 … +2.3] | −4.7 s | user active (load to 35) | inconclusive → R4T-b |
| combined5 (combined4 + R4D) | 3 | 18.2 | −0.9 [−1.4 … −0.3] | −5.9 s | load 4.3 | probably real |
| combined6 (combined4 + R4S + R4D) | 4 | 17.1 | −0.6 [−1.4 … +0.6] | −5.6 s | load 3.6 | not distinguishable |
| **combined7** (combined6 + R4T) | 4 | **16.0** | **−2.3 [−2.7 … −1.1]** | **−15.9 s** | load 3.6, 0/8 contended | **REAL** |
| R4T2 (chunk 64, matvec+bridge only) | 3 | 16.9 | −1.0 [−2.1 … −0.5] | −10.5 s | load 4.0 | probably real |
| R4T-b (R4T re-benched, quiet) | 3 | 17.0 | −1.3 [−1.8 … −0.4] | −8.4 s | load 4.0, 0/6 | probably real |

combined4 refs drifted 16.9–21.1 s/token across the night (18.2 in B4) — only paired Δ is read. Absolute progression
(paired): baseline 40.2 → combined 30.3 → R2F 23.6 → R3R 19.4 → combined4 18.2 → **combined7 ≈ 16.0 (−60 %)**.

### Round-4 findings so far (2026-09-21)

- **R4T** (report R4T.md, 24 depth variants + 42 sweep trials): per-frame idle servicing does NOT depend on DOM
  depth (0.23 ns/level, R² 0.00); idle = 0.14 ms/frame + N × (3.06 µs + 0.08 µs × wrappers between scroller and
  subject). Real knob: cost per CHANGED carrier = 14.1 µs + 45.8 ns × (animations on its consumer element), R² 0.996
  (107 µs at 2,000; 38 µs at combined4's 512 — matches R3A's 40 µs; 16.5 µs at 64 = knee). Cause: PendingAnimations::
  Update re-walks the element's animation list per changed animation (paint lifecycle self). Implemented
  `R4T_CONSUMER_CHUNK=64` (matvec/bridge 512 → 64, loop-reader 768 → 12 × 64, embedding 256 → 64); bundle `R4T`
  offline-verified vs combined4 (same timelines/declarations, +124 wrapper elements, 283/283 witnesses); Chrome smoke +
  8-token correctness queued; predicted ≈ −2.0…−2.3 s/token (18.2 → ≈16). Flattening carriers: ≤ 0.1 s, not pursued.
  **00:44 — 2-layer smoke FAILED**: bundle emits tokens [44873, 9890] vs ref [11, 3387] (first pass already wrong;
  token-1 frames 22/48/30 vs 20/44/29) → no READY; R4T debugging via the per-hop verification vectors, bisecting the
  four chunked sites. Root cause (01:00): the loop-reader's `--lp-*` are registered `inherits:false` and forwarded ONE
  level with `inherit`; the 12 nested chunk wrappers left the innermost with 64 of 768 values (decode of 0). Fix: each
  chunk level forwards all `--lp-*`. **Fixed smoke PASS**: ids [11, 3387]; frames/UpdateLayoutTree/Layout 26/53/32
  identical to the ref; paint-lifecycle 396 vs 1,018 ms (−61 %, the predicted term). 12-layer `R4T` rebuilt, offline
  PASS; **READY 01:38 — 8-token correctness 8/8 ids, verify rc 0.** B5 pairs it after combined5; R4M builds
  combined7 (= combined6 + R4T) at both capacities.
  Lesson for capacity-32 emitters: any `inherits:false` set forwarded one level breaks under wrapper insertion.
- **R4S**: the 97-value attention-score hop moved onto an anchor→size-container chain inside the qkv
  pass → 2.5 frames/layer (was 3.0), LayoutCount 629 → 535 per 8 tokens, 8/8 ids; predicted −0.8 s.
  Bundle `R4S` READY. 2.0 frames/layer would need the 768-value ctx hop as a 384-deep chain (depth ≈496
  of the 512 cap) — feasible only after flattening the 12 nested bank wrappers.
- **R4C**: 32 tokens in 1,133 s, 32/32 ids; slope 1.14 s/token/position = per-pass cost of the filled V
  glyph population (+9,216 distinct 768-axis font instances per position whose weight axis changes
  every pass; ≈36 µs style + 58 µs layout each per token); latches 13 %; memory not the slope.
- **R4D** — `combined4-c32b` (capacity 32 + empty lists for unfilled slots, hidden unfilled V glyphs, leaner
  per-position latches): ONE passive 32-token run **32/32 ids, 905.9 s (−227 s, −20 % vs 1,133)**; fit
  14.4 + 0.845·k s/token (was 16.3 + 1.14·k); tokens 2–6 at 17.8–19.8 s (cap-8 parity → the capacity step is gone);
  machine load 7–10 during the run (R4P/R4X CPU work), so this is an upper bound. RSS peak 7.5 GB (was 5.8).
  Remaining slope 0.85 s/token/position = filled-position V glyph work. `combined5` (cap 8, same flags): 8/8 ids,
  150.8 s single run (B5 pairs it). **`combined4-c32c`** (= c32b + `--value-layout widths`: constant font instance per
  filled slot, weight in a calc-size width — not bit-identical, ids verified only on this trajectory): **32/32 ids,
  758.7 s (−33 % vs 1,133)**, fit 13.9 + 0.60·k, max 37.3 s/token, RSS peak 7.2 GB → current 32-token demo candidate.
- **R4X** (R4X.md): **no readback primitive outside the catalog exists in stock Chrome 153.** Style can read geometry
  through exactly four channels — container-query units (2 values per size-container level, frameless), font-metric
  units ch/ic/ex/cap/lh (5 per font instance, frameless, no layout), anchor-size() (only into sizing/insets of
  positioned boxes), and scroll/view-timelines (one frame per hop). Probe: container-progress()/media-progress() parse
  but evaluate to 0 (stubs); anchor-size() still rejected in font-size/letter-spacing/font-variation-settings;
  inherit()/random()/style range queries absent; ::before pseudo-elements are valid timeline subjects (halves carrier
  elements, not timeline costs). Fixture (97-score hop): view-timeline 2 passes/2 frames 37 ms; `1ch` metric readback 1
  pass/1 frame 35 ms with 13× better precision; anchor→fixed-container chain 17.7 ms. Only new application: read the 97
  scores via `1ch` on the elements that already instantiate the score fonts (−0.25…−0.3 s/token, exact-class; overlaps
  R4S's anchor chain). Re-probe container-progress() on each Chrome release.
- **Run C and the "trajectory-dependent slope" — resolved by R4V as MEMORY STATE, not the prompt.** `combined4-c32c`
  with prompt 40 "I": 32/32 ids, 1,008.6 s vs 758.7 s on Hello — identical pass counts and intercepts, slope doubled.
  R4V (R4V.md) counted, emitter-exactly, what the page instantiates per step on both trajectories: score-font instances
  (144·k, 0 repeats), V-leaf instances (144·k, all distinct), K/V lists (0 repeats; position embeddings rule out
  collisions) — identical within 1 %, so there is nothing trajectory-dependent to reuse. What does match: the renderer's
  RSS. Hello's run grew 1.7 → 7.2 GB untouched; the prompt-40 run peaked at 5.0 GB at k=6 and was reclaimed down to
  2.8 GB while the machine (16 GB) was under memory pressure from the user's apps (kernel memorystatus idle-exit kills
  at 03:14 = its tokens 16–17). corr(Δwall, ΔRSS) = −0.88; pooled law `t = a + b·k + c·RSS` cuts rmse 4.9 → 1.5 s;
  across all 7 widths-family runs corr(slope, mean RSS) = −0.84; the combined7-c32 pair reverses sign, which a prompt
  effect cannot. Mechanism: each style pass re-substitutes a 65-axis V list into 768·p filled leaves (+832-axis lists
  into 12·p score glyphs) ≈ 650 B garbage per leaf per pass ≈ 40 MB per position per token; live heap is constant, so
  GC/purge work per token ∝ p with a coefficient set by memory pressure (forced GCs + font/shape-cache invalidation →
  the 144·p instances rebuilt at the next layer). Predicted prompt-40 time at Hello's memory state: ≈ 760–800 s.
  **Consequence for earlier round-4 wall-clock comparisons**: every capacity-32 run after ≈01:30 (combined6-c32, both
  combined7-c32 runs, run C) ran with depressed RSS (3.9–6.2 GB peaks vs 7.2–7.5 before) → their slopes are inflated by
  memory state. R4S's cap-32 extra RecalcStyle work (70.8·k recalcs/token) is structural and stands; the SIZE of its
  and R4T's cap-32 wall-clock penalties is confounded and unconfirmed.
  **Exact fix (R4V §5)**: cut the ∝ p allocation — one pre-concatenated `*` property per (slot, head) so the leaf
  substitution is a single var() copy, or the emitter's existing `fallback` value layout (per-head font-variation-
  settings with per-slot tags; leaves var()-free) after porting F4 packed banks; numerics unchanged; predicted
  −0.15…−0.3 s/token/position and a state-independent slope. Demo protocol: ≥ 8 GB free, no concurrent Chromes.
- **R4W (V-leaf allocation fix, R4W.md)**: mechanism confirmed and refined from R4V's trace — the leaf subtree (25,351
  elements) is restyled 12×/token (once per layer); Blink redoes var() substitution per restyled leaf: ≈1,070 B list copy
  + re-tokenise + 65-entry CSSValueList (~3 KB) + FontVariationSettings + uncached 65-axis FontDescription hash → 9.85 MB
  substituted text per filled position per token (≈40 MB with parsed values); GC = 11.6 % of the traced window (1.6–3.8
  s/token at k=5–10). Fix built as `combined4-c32d` (`R4W_V_PRECAT=1`): 32 per-slot value fonts (V axes retagged per
  slot, protected tables byte-identical), ONE `display:contents` wrapper per head carrying the whole font-variation-
  settings (32 slot lists + P000), leaves with NO font property (Font inherited by pointer), weight still in the leaf
  width → **1,069 B → 8 B per leaf per restyle; parsed axes per restyle at p=32 1,597,440 → 24,960**. Offline PASS (rule
  families as intended, witnesses, HVAR instancer spot checks, NumPy 32/32 on prompt 40, no JS). Chrome smoke + ONE
  32-token prompt-40 run queued behind B5; success = slope ≤ 0.45 with flat RSS.
  **c32d run 1 (prompt 40): 32/32 ids but 1,045.4 s, fit 15.3 + 1.05·k — the slope did NOT move** (run C 1.09), intercept
  +1.5 s (wrapper fvs), RSS still reclaimed 5.6 → 4.0 GB at load 3.9. Machine memory at the time: swap 4.5/5 GB used,
  ≈1M compressor pages — the pressure is memory (user's apps + other sessions), persistent since ≈01:30. Either the
  substitution garbage is not the ∝ p term, or the reclaim cadence is set by system-wide pressure regardless of the
  page's own garbage rate. Decisive control queued: c32c with Hello NOW (same memory state).
  R4W's provisional verdict (R4W.md §5): the predicted consequence is refuted — removing 99 % of the leaf-side
  substitution left slope, RSS decline and GC noise unchanged (style slope −8 %, layout intercept +1.5 s from the
  wrapper). Remaining ∝ p streams: 12·p score glyphs each re-substituting a ≈12.7 KB packed K list per restyle, bank
  aliases, and layout-side shaping/flex ∝ p (0.42–0.44 s/token/position) that no style-side fix touches. c32d is
  READY for correctness only; not adopted for timing.
  **Control (05:40–05:57): `combined4-c32c` with Hello in today's memory state = 969.7 s, fit 14.3 + 0.97·k** (early-night
  Hello 758.7 s, 13.9 + 0.60·k; prompt 40 today 1,008.6 s, 13.6 + 1.09·k). Memory state accounts for ≈210 of the 250 s
  gap; the prompt itself ≈40 s (4 %). **Conclusion: capacity-32 wall-clock is dominated by the renderer's memory state;
  all 32-token comparisons must be made in one session with swap empty and ≥8 GB free.** The clean-state demo number
  for prompt 40 is therefore predicted at ≈780–800 s (13–13.5 min); measured today 1,009 s (16.8 min).

### Round 4 — where the 32-token demo stands (2026-09-21 06:00)

| Bundle (capacity 32) | Prompt | ids | Total | Fit s/token | Memory state |
|---|---|---|---:|---|---|
| combined4-c32 (R4C) | Hello | 32/32 | 1,132.9 s | 16.3 + 1.14·k | clean (00:0x) |
| combined4-c32b (R4D, runs layout) | Hello | 32/32 | 905.9 s | 14.4 + 0.85·k | clean |
| **combined4-c32c (R4D + widths)** | Hello | 32/32 | **758.7 s** | 13.9 + 0.60·k | clean (00:30) |
| combined4-c32c | "I" (40) | 32/32 | 1,008.6 s | 13.6 + 1.09·k | swap 4.5/5 GB |
| combined4-c32c (control) | Hello | 32/32 | 969.7 s | 14.3 + 0.97·k | swap 4.4/5 GB |
| combined4-c32d (R4W fix) | "I" | 32/32 | 1,045.4 s | 15.3 + 1.05·k | swap 4.5/5 GB |
| combined6-c32 (+R4S) | Hello / "I" | 32/32 | 872.7 / 936.6 s | 11.7 + 0.93·k / 1.05·k | degrading (01:38–02:09) |
| combined7-c32 (+R4T, no R4S) | "I" / Hello | 32/32 | 1,050.1 / 929.7 s | 16.5 + 0.99·k / 12.3 + 1.02·k | pressured (02:46–03:02) |

Demo recommendation: `bundles/combined4-c32c`, prompt "I" selected in the page's dropdown (or bake 1858 "There" /
3260 "After" via the 3 prompt literals, R4P), run alone on AC with swap empty — expected ≈13 min, 32/32 ids verified.
Next exact levers for capacity 32 (untested): keep R4T's chunking at the matvec site only; attack the remaining ∝ p
streams (12·p score-glyph K-list substitution ≈12.7 KB each per restyle; layout-side shaping ∝ p); re-measure c32d and
combined7-c32 in a clean-memory session before dropping them.
- **R4P** (prompt screen, offline NumPy through the same q9/q16 reference; R4P.md): the demo's "Hello" prompt loops
  after 14 distinct tokens. 60 single-token prompts screened; 22 flip between quantized and float (fragile). Best
  prompts (quantized == float at all 32 steps, no repeated bigram, min top-1/top-2 margin ≥ Hello's): **40 "I"** (25
  distinct; already in every bundle's prompt dropdown → zero recompile; "…The first thing I did was to go to the local
  grocery store and buy a bag of frozen yogurt…"), 1858 "There" (26 distinct, needs recompile of 3 literals), 3260
  "After" (25 distinct). Reference ids in R4P/reference_ids_32_{40,1858,3260}.json; only one prompt token is
  structurally supported (multi-token prompts need an emitter prefill path). Chrome verification pending (combined6-c32 run 2).
- **B5 paired (bench/paired-round4.md), R4S vs combined4**: **−0.6 s/token [−0.9 … −0.4], −3.2 s / 8 tokens, n=3, all same
  sign, ref drift 0.3** → REAL (predicted −0.8). Layouts −12/token, recalcs +353/token (container-query interleaving,
  structural). Today's combined4 refs run 16.9–17.2 s/token (B4: 18.2) → absolute R4S ≈ 16.3–16.5. All six runs were
  flagged CONTENDED by an orphaned R4C `populations.py` at 100 % CPU since 23:30 (killed 01:17; incidents file).
- **B5 paired, R4T vs combined4 (lock held per pair from pair 3)**: pair 1 +2.3 (load 30), pair 3 +0.3 (ref 18.7 / cand
  19.0), pair 4 −2.5 (ref 20.1 / cand 17.6) → **mean 0.0, range −2.5…+2.3, NOT distinguishable from noise** while the
  machine is in use. The fixture's −2.3 s/token paint saving is not visible as wall-clock at 12 layers; needs quiet-
  machine pairs (queued at the end of B5's list) before R4T is accepted or dropped.
- **B5 paired, combined5 (R4D flags at capacity 8) vs combined4**: −1.4, −1.1, −0.3 s/token → **mean −0.9 [−1.4 … −0.3],
  −5.9 s / 8 tokens, all same sign; "probably real" (largest adjacent-ref swing 1.3)** — the R4D capacity fixes also help
  at capacity 8 (leaner latches, 12 B unfilled-slot substitutions), on top of their −33 % at capacity 32.
- **B5 paired, combined6 (R4S + R4D) vs combined4**: +0.6, −0.9, −1.4, −0.6 → **mean −0.6 [−1.4 … +0.6], n=4, not
  distinguishable from noise**; candidate medians 16.5 in the two latest pairs vs refs 17.9 / 17.1. R4S (−0.6) and R4D
  (−0.9) do not add up in the merge within today's ±1 s noise (machine in use throughout).
- **B5 paired, combined7 (R4S + R4D + R4T, capacity 8) vs combined4 — REAL: −2.3 s/token [−2.7 … −1.1], −15.9 s / 8
  tokens, n=4, all same sign, no contention (load 3.7–3.9), ref drift 1.5.** Candidate medians 14.9 / 16.1 / 15.9 / 16.1
  vs refs 17.6 / 17.2 / 18.6 / 18.7. Absolute: **≈16.0 s/token, best 8-token total 120.0 s** (combined4 ≈18.2 → −12 %; baseline
  40.2 → −60 %). Read with R4T alone (0.0 ± 2.4, in-use machine) and combined6 (−0.6, in-use): R4T's contribution shows
  up once the machine is quiet; the clean R4T-b pairs at the end of B5's queue will separate it.
- **B5 paired, R4T2 (chunk 64 on matvec+bridge only, no loop chain) vs combined4**: −2.1, −0.5, −0.6 → **mean −1.0
  [−2.1 … −0.5], −10.5 s / 8 tokens, n=3, all same sign, uncontended; "probably real"**. So consumer chunking does pay
  at 12 layers on a quiet machine (R4T's own 0.0 ± 2.4 was measured while the machine was in use).
- **B5 paired, R4T-b (R4T re-benched on the quiet machine)**: −1.8, −0.4 (≈−1.3 median), n=3, all same sign →
  **−1.3 s/token [−1.8 … −0.4], "probably real"**; consistent with R4T2's −1.0. R4T's earlier 0.0 ± 2.4 was the in-use
  machine. B5's queue is complete (05:40).
- **combined6** (= combined4 + R4S + R4D, capacity 8; R4T excluded pending its correctness run): READY 01:22, 8/8 ids,
  verify rc 0, residual rmse 0.0161 (combined4 0.0176), LayoutCount 527 per 8 tokens (combined4 629). B5 pairs it next.
  **`combined6-c32` (widths) run 1 (Hello): 32/32 ids, 872.7 s — SLOWER than c32c's 758.7 s** although tokens 2–4 are
  faster (16.0–16.9 vs 17.7–18.4): fit 12.6 + 0.89·k (c32c 13.9 + 0.60·k); layout slope 0.44 vs 0.27; RecalcStyleCount
  per token = 126 + 70.8·k → R4S's interleaved container recalcs grow with filled positions at capacity 32 (chain 192,
  depth 238). R4S is a cap-8 win and a cap-32 loss. Demo path: combined7-c32 rebuilt WITHOUT R4S (= c32c + R4T).
  **Run 2, prompt 40 "I" (selected in the page's own prompt dropdown by the harness before Run): 32/32 ids == R4P's
  NumPy reference** — the non-looping demo text is verified in Chrome ("I.\n\nThe first thing I did was to go to the
  local grocery store and buy a bag of frozen yogurt. I was so excited to try it."); 936.6 s on this (R4S-penalised)
  bundle, fit 12.6 + 1.01·k. combined7-c32 (no R4S, + R4T) runs prompt 40 next.
- **combined7** (= combined6 + R4T, capacity 8): READY 02:17, 8/8 ids, verify rc 0, LayoutCount 544, residual 0.0161.
  **combined7-c32** = combined4-c32c + R4T (widths, NO R4S): built, flag-off byte-identical to c32c; prompt-40 and Hello
  32-token runs queued (the demo decision).
  **combined7-c32 run A (prompt 40): 32/32 ids but 1,050 s** (c32c 758.7 on Hello; combined6-c32 936.6 on prompt 40); style
  intercept 8.1 s/token vs c32c's 4.5 — R4T's chunking costs more style time at 12 layers than it saves in paint
  (2-layer smoke had hinted +7 % UpdateLayoutTree). Machine was in active use (load 6.5–8; B5's concurrent R4T pair 1
  +2.3 s/token, both arms contended). R4T asked to attribute the style delta per chunk site and build a variant
  without the 4,224-declaration inherit fan-out (R4T2). Demo candidate remains **combined4-c32c** (758.7 s Hello) with
  prompt 40 to be verified on it, or combined6-c32 (936.6 s, prompt 40 verified).
  **Run B (combined7-c32, Hello): 32/32, 929.7 s** vs c32c's 758.7 s on the same prompt (load 5–6.5 vs 6–8): style
  intercept 4.0 (= c32c) but style slope 0.56 vs 0.30 and layout slope 0.38 vs 0.27 — the R4T penalty at capacity 32
  grows with filled positions rather than being a fixed style cost; run A's doubled intercept was contention. Whether
  R4T helps at capacity 8 is left to B5's lock-held pairs; at capacity 32 it is excluded from the demo bundle.
  R4T mechanism fixture (17 variants): per chunk element per restyle +21 µs nesting, +33 µs for 12 @container layer
  rules, ≈0 from a 30k-entry inherited map; animated head-to-head under 12-layer conditions (48×64 vs 6×512 animations,
  3,072 changed carriers): style equal (84.8 vs 85.3 ms), task −71 ms (≈ −23 µs per changed carrier). No mechanism
  reaches 0.5 ms/element → R4T stands at capacity 8 pending B5's lock-held pairs; the capacity-32 slope increase is an
  open question (safe cap-32 setting: chunk the matvec site only). Fallback bundle `R4T2` (matvec+bridge sites only,
  no loop chain) built, offline PASS, smoke/correctness queued.
- Merge plan: `combined6` (cap 8) and `combined6-c32` (32) = combined4 + R4S + R4T + R4D → B5 paired
  bench at cap 8; one 32-token run as the demo candidate.
