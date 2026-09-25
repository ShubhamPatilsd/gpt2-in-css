# R5H — the attention-score hop read back with `1ch` on the elements that instantiate the score fonts (R4X §6.1): no carriers, no chain, no timelines; RecalcStyleCount flat in the filled positions

Agent R5H, 2026-09-24. Tools copy `work/2026-09-19/R5H/tools` (= `R4M/tools7` = combined7's emitter + `r5h_ch_scores.py`, flag `R5H_CH_SCORES` default ON, which forces
`R4S_SMALL_HOPS` off; `R5H_CH_SCORES=0` reproduces combined7 / combined7-c32 byte-for-byte, §4). Fonts: `R5H/assets-r5h/font-vector-operators-r5h/` (12 F4 dot fonts + one cmap
entry, built and asserted by the emitter at build; nothing under `experiments/` touched). Bundles: `bundles/R5H` (cap 8, runs) and `bundles/R5H-c32` (cap 32, widths, R4D flags, R4T chunk 64
as combined7-c32, no R4S) with `BUILD.md` (recipe, flag, offline results, embedded `diff -ruN R4M/tools7 R5H/tools`, 401 lines); smoke trio `bundles/smoke-R5H-2L{,-r4s,-off}` (2 blocks,
capacity 2). Scratch/harness/logs: `work/2026-09-19/R5H/`, append-only `R5H.log.md`. No repo `tools/` or `experiments/` edits, no git.

## 0. Headline

**Built and offline-verified; Chrome NOT run (disk 1.0–2.8 GB < the 3 GB rule and CHROME.lock held by R5M for the whole session) — §5 has the exact ready-to-run commands and acceptance criteria; no READY created.**
The 96 (cap 8) / 384 (cap 32) score carriers per layer become EMPTY `display:block` elements carrying today's `font: 512px FvsDotH` + `font-variation-settings: var(--fr-k-S),
var(--fvs-query-H)` and `--fs-H-S: calc((1ch / 1px − 15351.808) · var(--fqs-H) · var(--fr-ks-S-H) · 5.21668e-4)` — the same decode as the carrier width minus the 262144 / 128 encoding
(§1.3). `1ch` is the advance of glyph U+0030 of the element's own primary font instance with HVAR applied (Blink `FontSizes::Ch` → `PrimaryFontWithDigitZero()` →
`FontMetrics::ZeroWidth()` = `SkFontGetWidthForGlyph(zero_glyph)`, the same Skia call HarfBuzz uses for the shaped advance on macOS fonts without `trak`, §3), so the fonts are rebuilt
with `cmap U+0030 → dot` and every other table byte-identical (asserted at build and by `R5H/font_check.py`). Per head the `capacity` slot elements nest inside the ctx scroller's `.track`
and the chain bottom `.fvs-score-reader.fvs-sr-H` carries head H's softmax + weights (declarations byte-identical to the old single-element rule, split by head) and hosts head H's 64
V rows (position:absolute against `.track`: geometry unchanged). Depth grows by capacity + 1 (bottoms at depth 104 / 128 for cap 8 / 32; max depth 165 unchanged) instead of R4S's
12·capacity/2 fixed size containers (reader at 140 / 238). The scores, softmax and V-row widths are now plain style dependencies of the qkv-readback pass that restyles `.fvs-query`:
no shaping of score glyphs, no score layout, no interleaved container recalcs, no timelines/keyframes/stamp/receipt/gate. Expected: 5 passes / 2.5 frames per layer like R4S (§2.3) with
RecalcStyleCount flat ≈ 84/token at cap 32 (R4S: 126 + 70.8·k) — the cap-32 penalty that excluded R4S from combined7-c32 disappears, so the −12 score-readback passes / −6 frames per
token (≈ −0.7 s/token, R4S §7) become available at capacity 32 too. Precision (§3): strictly finer than both predecessors at the transport (float32 advance instead of a 1/64-px
LayoutUnit or a float view-timeline progress), one 6-significant-digit `var()` crossing at the softmax as in R4S (two in the timeline path); exact-class, NumPy ids unchanged (8/8, 32/32
prompt 40). Offline: flag-off byte identity with combined7 and combined7-c32, rule/HTML diffs confined and counted, witnesses identical modulo the 12 dot paths, no JS (§4).

## 1. The score hop in tools7 and what replaces it (steps 1–2)

### 1.1 Today (combined7 = R4S on at cap 8; combined7-c32 = flag off) — `browser_gpt2_font_vector_cache.attention()`

| | view-timeline path (`R4S_SMALL_HOPS=0`, combined7-c32) | R4S chain (combined7) |
|---|---|---|
| producer per (H,S) | `<i class="metric fvs-score-H-S" style="view-timeline:--fvs-score-H-S inline">&#xF5800;</i>` in `.fvs-score-source>.track` | `<i class="fvs-score-a fvs-score-H-S" style="anchor-name:--fsa-H-S">&#xF5800;</i>` in a fixed `.fvs-score-stage` |
| rule | `.fvs-score-H-S{font:512px FvsDotH;line-height:1;font-kerning:none;font-variation-settings:var(--fr-k-S),var(--fvs-query-H);width:calc-size(max-content,calc(262144px + (size − 15351.808px)·var(--fqs-H)·var(--fr-ks-S-H)·0.0667735042735))}` | same rule |
| transport | 12·cap timelines + stamp; `.fvs-score-reader` with 12·cap animations → `--fsp-H-S` → `--fs-H-S:calc((1572864/(var(--fsp)+2) − 786432)/128)`; `.fvs-score-receipt` stamp → `--fvs-score-ready` → `.fvs-score-gate` (`content-visibility`) | 6·cap nested `position:fixed;container-type:size` `#fvs-scK{width/height:anchor-size(--fsa-…)}`, publishers `--fs:calc((100cqw/1px − 262144)/128)` on the next container, bottom `.fvs-score-reader` |
| consumer | `.fvs-score-reader{--fv-S; --fm-H; --fe-H-S; --fd-H; --fb-H; --fw-H-S}` (one element) > `.fvs-softmax` > `.cache-bridge-source` scroller > 768 V rows | same, inside the last container |
| passes/layer | 6 (score readback is its own pass, B1) = 3.0 frames | 5 = 2.5 frames; the interleaved container recalcs are counted by RecalcStyleCount (≈ 6 per filled position per layer → 70.8·k/token at cap 32, R4M §4.1) |

The adapter (`browser_gpt2_reused_adapter.py`) lists `.fvs-score-receipt` among the `--native-pass` receipts and expects 7 inline `var(--epoch)` readers (6 under R4S); `.fvs-score-reader` is
a pass reader (`--native-pass`, `--position` stamps, class selectors). Nothing else in the runtime path references the reader/softmax (grep in §4 of the log).

### 1.2 R5H design (flag on)

- **Fonts** (`r5h.ch_dot_font`): for each F4 dot font `dot-hH-<digest>-f4.woff2`, add `U+0030 → dot` to every unicode cmap subtable (formats 4/0-3, 4/3-1, 12/3-10), save as
  `R5H/assets-r5h/font-vector-operators-r5h/dot-hH-<digest>-f4-r5h.woff2`, and on EVERY call assert: table set identical; every table except `cmap` byte-identical (`head` identical
  except `checkSumAdjustment` bytes 8–12); cmap subtables = original + {0x30: dot}; glyph order identical. `@font-face{font-family:FvsDotH}` points at the new file. Value fonts untouched.
- **Slot elements** (`r5h.slot_rule`): `.fvs-score-H-S{display:block;font:512px FvsDotH;line-height:1;font-kerning:none;font-variation-settings:var(--fr-k-S),var(--fvs-query-H);
  --fs-H-S:calc((1ch / 1px - 15351.808) * var(--fqs-H) * var(--fr-ks-S-H) * 0.000521668002137)}` — the font declarations are the carrier's, byte for byte (checker); the decode
  constants are the carrier's `base·unit` and `k/128` (§1.3). `--fs-H-S` registered `<number>` `inherits:true` (as R4S). No content, no width, no anchor, no timeline.
- **Structure** (`row()` in `attention()`): the ctx carrier's 768 rows arrive in coordinate order (asserted); at `local == 0` of head H the emitter opens
  `<div class="fvs-score-H-0"><div class="fvs-score-H-1">…<div class="fvs-score-H-{cap−1}"><div class="fvs-score-reader fvs-sr-H">`, at `local == 63` it closes cap + 1 divs. So inside
  `.fvs-softmax > .scroller.cache-bridge-source > .track` there are 12 sibling chains, each `capacity` nested empty blocks + one bottom hosting the head's 64 `.metric.fvs-value-row`
  (position:absolute; left:0; top:0 → containing block `.track{position:relative}` as before; the wrappers are unpositioned zero-height blocks). The ctx `--epoch` marker stays last in
  the track. The outer `.fvs-score-reader` wrapper is gone; `.fvs-softmax` (no rules) stays.
- **Softmax split**: the old `.fvs-score-reader{--fm-0…--fb-11}` and `{--fw-…}` rules are emitted per head as `.fvs-sr-H{…}` with the identical declaration text (checker concatenates
  the 12 and compares to the reference rule byte for byte). `--fv-S` (inherits:false) stays on `.fvs-score-reader` (class → all 12 bottoms), as do the adapter's `--native-pass` /
  `--position` stamps (class selectors: 12 elements instead of 1).
- **Removed**: score scroller/track, 12·cap+1 keyframes and timelines, reader animations, `--fsp/--fss/--fvs-score-ready` registrations, stamp/receipt/gate, `html{timeline-scope}` score
  names, R4S stage/anchors/containers/publishers; the adapter drops `.fvs-score-receipt` and expects 6 inline epoch readers (shared helper `r5h.no_score_hop()`); `R4D_GATE_SCORES`
  and `prewarm_values` are refused under the flag (no score scroller / gate to act on).
- **Fonts inherited downward**: the bottoms and the scroller/track now inherit the last slot's `font`/FVS; they have no text, and `.fvs-value-row{font:1024px FvsValue0;…}` is a `font`
  shorthand, which resets `font-variation-settings` (R4W relied on the same fact), so the V leaves' computed fonts are unchanged.

### 1.3 The decode is the carrier's, without the encoding

Carrier: `width = 262144px + (size − base·u)·fqs·frks·128/(8·coef·u)` with `size` = the shaped advance (max-content), `base = 29984` units, `coef = 468`, `u = 512/1000`; readback `--fs = (width − 262144)/128 = (size − base·u)·fqs·frks/(8·coef·u)`. R5H: `--fs = (1ch/1px − base·u)·fqs·frks/(8·coef·u)` with `1ch` = the same advance. Constants emitted with `.12g` as today
(`15351.808`, `0.000521668002137`; the carrier's `0.0667735042735` = 128× that, checked to 1e-12 relative).

### 1.4 Which element resolves `ch` against which font

Blink (`css_to_length_conversion_data.cc`): `FontSizes` is built from the element's own `FontSizeStyle`; `Ch()` = `font_->PrimaryFontWithDigitZero()->GetFontMetrics().ZeroWidth()` (× zoom).
`PrimaryFontWithDigitZero` walks the fallback list to the first face that maps '0' — which is exactly why the cmap entry is needed: without it `ch` would silently come from a fallback face.
`ZeroWidth` is set in `SimpleFontData::PlatformGlyphInit`: `zero_glyph_ = GlyphForCharacter('0'); SetZeroWidth(ZeroInlineSize())` = `WidthForGlyph(zero_glyph_)` = `SkFontGetWidthForGlyph(font_, glyph)`
on the instance's `SkFont` (variation coordinates applied). A custom property declared on the element uses the element's own font (E1 #70/#73, R4X §1 and its fixture arm M, which used exactly
`font:512px X; font-variation-settings: …var()…; --fs: calc(1ch / 1px / 0.512)` on one element); font properties would use the parent's — the slot's FVS depends only on `--fr-k-S`/`--fvs-query-H`,
never on `--fs`, so there is no cycle, and the cascade applies the font-affecting properties before a custom property that carries font units (`StyleCascade::ApplyHighPriority` +
`HasFontSizeDependency` cycle detection). The font instance (`FontFallbackList` → `FontCache` → `SkTypeface` clone at the FVS coordinates) is the one the carrier's shaping created today;
it is now created at style time instead of in layout (R4X §5: ≈ 0.3 ms per new instance either way).

## 2. Passes, frames, recalcs (predicted; §5 has the measurements that ran)

### 2.1 Where the values are born and die (R3R §1.1 / R4S §2.1 cascade)

S1 (proj readback of P−1) restamps `--native-pass` and the qkv receipt closes the qkv gate; A2 (qkv readback) opens it → `.fvs-query` and everything below is restyled with the new
`--qkv-*`: `--fqs-H`, `--fvs-query-H`, the live K/V lists, the bank write. **In that same style pass** each slot element gets its new FVS → Blink resolves its Font → `1ch` → `--fs-H-S`
→ inherited into the head's bottom → `--fm/--fe/--fd/--fb/--fw` → the V leaves' `--fw`-dependent widths (runs: P axis / widths: calc-size width). A2's Layout lays out the 768 rows
with the new weights (the score glyphs are no longer laid out or shaped at all), the rows' view-timelines snapshot after that layout, and the ctx readback is B1. Same 5-pass period as
R4S — `[proj+S1 | qkv+scores+softmax+V] [ctx | attn] [fc | proj+S1'] …` = **2.5 frames/layer** — but WITHOUT R4S's interleaved container recalcs: R4S resolved the scores inside A2's
*Layout* (48 / 192 container layouts each resuming a size-container subtree recalc, 1 + p V glyphs per row restyled per container), R5H resolves them inside A2's *style* pass. Flag-off
(view-timeline) is 6 passes = 3.0 frames/layer.

### 2.2 Gates and staleness

No score gate is needed for the same reason as R4S §2.2: the scores can never be stale relative to the fonts they come from (same style pass, same element). The qkv gate still closes the
attention subtree in S1 (nothing under it restyles between A2 and the next S1); `--fv-S` masking of unfilled slots is unchanged; the cache-bridge receipt/gate for the ctx hop is unchanged
(opens in B1 as in R4S). Load state: before the first A2 the slot elements hold the default-instance advance → `--fs` = garbage masked by `--fv-S` = 0 for all slots (epoch 0), exactly
like the initial `--fs = 0` today.

### 2.3 Expected counters

| | combined7 (R4S, cap 8) | combined7-c32 (flag off) | R5H / R5H-c32 |
|---|---|---|---|
| passes / frames per layer | 5 / 2.5 | 6 / 3.0 | 5 / 2.5 |
| RecalcStyleCount per token | ≈ 470 (84 + 48 interleaved × 8 layers…; measured 3768 / 8 tokens) | 84 flat | **≈ 84 flat** (no containers) |
| LayoutCount per token | ≈ 68 (544 / 8) | 76 (cap 32: 64–76) | ≈ 68 / 64 (R4S's count: the score readback layout is gone) |
| live timelines / animations per layer | +0 (R4S) | +97 / +385 | +0 |
| shaped score glyphs per layer | 96 / 384 | 96 / 384 | **0** |
| score font instances | 12·p new per layer (unfilled slots share one per head) | same | same, created in style instead of layout |
| DOM | stage + 96 rows + 48 containers + reader | scroller + 96 carriers + stamp + reader/receipt/gate | 12·cap empty blocks + 12 bottoms (cap 8: −38 elements vs combined7; cap 32: +6 vs combined7-c32) |

Predicted s/token: at cap 8 vs combined7 the difference is second order (−96 shaped runs ≈ −2 ms/layer, −48 interleaved recalcs ≈ −0.02 s/token, no separate score layout; the font
instantiations move from layout to style): ≈ **−0.05 … −0.1 s/token**, i.e. combined7's ≈ 16.0 stays; the point is capacity 32. At cap 32 vs combined7-c32 (flag off): −12 score-readback
passes and −6 frames per token (R4S's −0.7 s at cap 8) plus −385 timelines/animations per layer (≈ −0.1 s), **without** the 70.8·k interleaved recalcs that cost combined6-c32 +114 s over
32 tokens: predicted **≈ −0.7 … −0.9 s/token flat in k** (758.7 s → ≈ 730 s on the clean-memory Hello reference; memory state dominates absolute cap-32 wall-clock, R4V).

## 3. Precision (exact-class; where the value is quantised and where it crosses a `var()`)

| stage | view-timeline path (combined7-c32) | R4S chain (combined7) | R5H |
|---|---|---|---|
| glyph advance | Skia `SkFont::getWidths` float32 → HarfBuzz position 1/65536 px (truncation) → float sum | same | `SkFontGetWidthForGlyph` float32, **no HarfBuzz step** (same Skia call/instance: on macOS Blink hands advances to HarfBuzz from Skia unless the font has `trak`; the dot fonts have none) |
| max-content | LayoutUnit 1/64 px (`FromFloatCeil`) | same | — (not laid out) |
| encoding | `262144px + 128·score` → LayoutUnit 1/64 px (→ 1/(64·128) score units) | same | — |
| transport | scroller 1572864 px / progress float, `--fsp` 6-digit `var()` crossing, decode `(1572864/(p+2) − 786432)/128` | `100cqw` exact LayoutUnit → number (48 bits) | `1ch / 1px` in a typed calc (double from float32) |
| `var()` crossings of the score | 2 (`--fsp` → `--fs`, `--fs` → softmax) | 1 (`--fs` → softmax) | **1** (`--fs` → softmax) |
| digits per crossing | 6 significant (`CSSNumericLiteralValue::FormatNumber` = `%.6g`; a registered property's computed value is re-serialised to a `CSSVariableData` before substitution, `StyleCascade::ResolveTypedExpression` → `ConvertRegisteredPropertyVariableData`) | 6 | 6 |
| max error, score units, at fqs·frks = g | ≈ (1/64 px)·g/1917 + float-progress rounding ≈ 8e-6·g + 2e-4…; R4X fixture: 0.09 units ≈ 13× R5H | (1/64 px)·g/1917 = **8.2e-6·g** (+ 1/(64·128) from the encoding) | float32 ulp at ≤ 2^15 px = 0.002–0.004 px → **1.0e-6·g … 2.0e-6·g** — 4–8× finer than the LayoutUnit path; the 6-digit crossing (5e-6 × |score|) is the same in all three |

Advance range at 512 px: 16 … 30 687 px (base 15 351.8 px ± 64·468·0.512); float32 ulp 2^-9 … 2^-8 px there; `fqs·frks` = max|q|·max|k| of the head (tens to hundreds for GPT-2's
layer-0 heads), so the transport error is ≤ 2e-4 score units at g = 100 versus ≤ 8e-4 (R4S) — and both are below the `var()` crossing's 5e-6·|score| ≈ 5e-4 at |score| = 100. Nothing else
changes: `--fqs`, `--fr-ks` cross a `var()` in the carrier width expression today exactly as in the slot rule; the softmax arithmetic (`exp`, sums) runs on the same declarations. As for
R4S, the numbers are not bit-identical to the predecessor's (a different rounding point), strictly no coarser, ids identical offline; `finalResidualError` is expected to move at the 1e-3
level (R4S: 0.0176 → 0.0172 rmse when it moved from timelines to the chain).

## 4. Offline verification (step 4; logs in `R5H/logs/`)

| check | result |
|---|---|
| **flag off = combined7** — `R5H_CH_SCORES=0 compile.sh R5H/scratch/off-8 8 12` vs `bundles/combined7` (`R4M/compare_bundles.py`) | index.html byte-identical (6,517,186 B); runtime.css identical after URL-depth normalisation; manifest +`r5hChScores:false` only; witnesses 283/283 |
| **flag off = combined7-c32** — `R5H_CH_SCORES=0 R4S_SMALL_HOPS=0 VALUE_LAYOUT=widths … off-32w 32 12` vs `bundles/combined7-c32` | index.html identical (7,198,924 B); css identical (normalised); manifest +1 key; witnesses 283/283 |
| fonts — `R5H/font_check.py` (12 R5H dot fonts vs F4 sources) | **PASS**: only `cmap` differs (head: checksum only); cmap = source + {U+0030: dot} in all 3 subtables; glyph order `['.notdef','dot']`; HVAR-instanced advances of `dot` equal at 6 random 128-axis locations per font (fontTools `VarStoreInstancer`); the emitter's own assertions ran at every build |
| `R5H/offline_check.py smoke-R5H-2L smoke-R5H-2L-r4s` (2 blocks, cap 2) | **PASS**: +24 slot rules, +12/+12 per-head softmax/weights; −24 carrier rules, −12 container sizes, −12 publishers, −4 chain structure, −1/−1 single-element softmax/weights; nothing else; 12 chains `.track > slot 0,1 > bottom`, 64 rows per bottom; elements 62,358 vs 62,360 (−2 = 37 − 39); max depth 165 (= ref), bottoms at 88 |
| `offline_check.py smoke-R5H-2L smoke-R5H-2L-off` | **PASS**: additionally ±24 `--fs` registrations (true/false), −26 progress/stamp/ready registrations, −50 keyframes, −scroller/−reader anims/−receipt/−gate, pass-reader/epoch lists −`.fvs-score-receipt`, `.head-isolation` reset −`--fsp/--fss/--ready`, html scope −score names; view-timeline delta 25; elements +6 |
| `offline_check.py R5H combined7` (cap 8) | **PASS**: 96 slot rules (each = carrier font declarations + decode with base 15351.808 / k 0.000521668002137 = carrier k/128), −48/−48 containers/publishers, softmax/weights identical concatenated; elements 67,531 vs 67,569 (−38); depth 165, track 95, bottoms 104; witnesses 271 identical + 12 dot entries same advance/upem (codepoint U+0030 vs U+F5800 — the witness generator renders the lowest cmap codepoint, i.e. the R5H witness itself renders '0' in the dot font and expects 29984 units) |
| `offline_check.py R5H-c32 combined7-c32` (cap 32, widths) | **PASS**: 384 slot rules, ±384 registrations, −386 scratch registrations, −770 keyframes, 384 pass-reader lists; elements 86,445 vs 86,439 (+6); depth 165, bottoms 128 |
| NumPy ids (R5H tools; `R5H/reference_ids.py`, `numpy_ids_40.py`) | 8-token `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected; prompt-40 free-running 32 ids = `R4P/reference_ids_32_40.json` (32/32, = teacher-forced). The reference does not model the transport (as for R4S/R4W) |
| static check `tools/launch_browser_gpt2.py --check` | `runtimeJavaScript: false` for R5H (285,592,810 B assets), R5H-c32, the smoke trio |
| a bug the checker caught | the first build emitted 24 stray `@keyframes fvs-score-*` (the keyframes guard tested `r4s.SMALL_HOPS`, which R5H forces off) — guard → `r5h.no_score_hop()`, rebuilt; a zsh `env $e` word-splitting slip built the first `-r4s/-off` smoke twins with the flag on (caught by `compare_bundles.py`: identical to the on-bundle), rebuilt with explicit assignments |

Sizes: R5H runtime.css 39,063,265 B / index.html 5,606,549 B (combined7 39,073,102 / 5,612,552); R5H-c32 50,382,553 / 6,272,279 (combined7-c32 50,502,747 / 6,294,290).

## 5. Chrome (step 5)

**Not run in this session.** The whole session (12:10–12:50) had 1.0–2.8 GB free disk (rule: ≥ 3 GB) and `CHROME.lock` held by R5M (`fixtures-main` from 12:30,
`fixtures-inst2` from 12:41); the machine was on AC (battery 21–25 %, charging), swap 3.7 / 4.0 GB used, ≈ 900k compressor pages (memory-pressured — a cap-32 wall-clock would be
confounded, R4V). A chain that waits for both conditions was armed and then stopped at hand-back (no unattended lock holder left behind). Everything is ready to run, in order,
each under `R5H/with_lock.sh` (owner marker `R5H <label> <pid> <time>`, `touch -c` 30 s, 5 s poll, AC + ≥ 3 GB required, watchdog, rmdir only own):

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
R5H/run_chain.sh            # = the three steps below with disk/lock waits and retries; logs to R5H.log.md, outputs under R5H/runs, R5H/run-R5H, R5H/run-R5H-c32
# (1) smoke trio, one lock hold, light trace: ids must be [11, 3387] for all three; R5H/frames.py writes runs/<b>/frames.md (passes/frames per token; expect the R5H and R4S
#     arms at 10 layer passes in 5 frames, the off arm at 12 in 6; RecalcStyleCount +≈0 interleaved for R5H vs R4S's ≈12/layer at cap 2)
R5H/with_lock.sh smoke-trio 1200 zsh -c 'for b in smoke-R5H-2L smoke-R5H-2L-r4s smoke-R5H-2L-off; do TRACE=1 R5H/smoke_inner.sh $b $b 2; done'
# (2) ONE passive 8-token correctness run of bundles/R5H (R4M's correctness_run.mjs + verify_browser_gpt2_runtime.py with the R5H tools) → 8/8 ids, verify rc 0 → then `touch bundles/R5H/READY`
R5H/with_lock.sh correctness-R5H 1500 R5H/correctness_inner.sh R5H
# (3) ONE 32-token prompt-40 run of bundles/R5H-c32 (R4M's bench_native.mjs, keyboard trigger, heap=1, RSS/token, vm_stat + swap recorded before/after) → R5H/run-R5H-c32/c32-p40.summary.md
B0_PROMPT_TOKEN=40 REF_JSON=R4P/reference_ids_32_40.json R5H/with_lock.sh c32-R5H-c32 2760 R5H/c32_inner.sh R5H-c32 c32-p40 2400000
```
Acceptance: smoke ids identical across the trio; 8/8 ids + verify rc 0 (READY); 32/32 = `R4P/reference_ids_32_40.json`; **RecalcStyleCount per token ≈ 84 flat at cap 32** (the
summary table's ΔRecalcStyle column; combined6-c32 with R4S: 126 + 70.8·k), LayoutCount ≈ 64 flat; RSS per token in the same table. `bundles/R5H*/READY` are deliberately NOT created.

## 6. Prediction, risks, follow-ups

- **Predicted**: cap 8 ≈ combined7 (−0.05 … −0.1 s/token; the R4S saving is retained, the interleaved recalcs and 96 shaped score glyphs per layer go); cap 32 ≈ −0.7 … −0.9 s/token flat
  in k vs combined7-c32 / combined4-c32c (the score readback pass and 385 timelines per layer are gone and, unlike R4S, nothing scales with p) — to be confirmed by the RecalcStyleCount per
  token (must be ≈ 84 flat) and B6's pairs; absolute cap-32 wall-clock is memory-state dominated (R4V).
- **Chromium behaviours relied on**: `ch` resolves in a custom property against the element's own primary font *with digit zero* (`PrimaryFontWithDigitZero`; hence the cmap entry — without
  it the value would silently come from a fallback face and every score would be a constant), at style time, with variation coordinates applied (R4X arm M measured this on 153; Blink's
  `ZeroInlineSize` = `SkFontGetWidthForGlyph` on the instance); the font-affecting properties are applied before a custom property with font units (`ApplyHighPriority` /
  `HasFontSizeDependency`); Skia advances feed both `ch` and HarfBuzz for these fonts (no `trak`). If a future Chrome changes `PrimaryFontWithDigitZero` semantics the witness rows
  (which now render '0' in FvsDotH and expect 29984 units) still pass, but the scores would all read the same base advance → `--fs` = 0 for every slot → uniform attention → wrong ids: the
  8-token correctness run is the guard.
- **Structure**: 12 in-flow empty blocks per head inside the ctx scroller's track (position:relative) — the rows are absolutely positioned, so nothing moves; `contain:strict` on the scroller
  is unchanged. Depth +cap+1 only, so the R5X merge with R5C's chains has headroom (max depth stays 165 at both capacities).
- **Memory**: −(stage + 48/192 fixed containers at 262144-px sizes ≈ 35 KB each, R4S) or −(scroller + 96/384 timelines); +12·cap tiny blocks; instance counts unchanged (12·p per layer;
  unfilled slots share one instance per head since their FVS are equal). Expected within noise; R5M/B6 measure.
- **Not done / follow-ups**: (i) unfilled-slot elements could get `font-variation-settings:normal` under `@container fvscache style(--fvq-S:0)` to skip even the shared instance (masked by
  `--fv-S`; not in the brief); (ii) `test_browser_gpt2_font_vector_cache.py` still expects the scroller (it already failed under R4S); (iii) the 12 bottoms each evaluate the
  `@container loopcontrol style(--pass:N)` stamp rules (cap·blocks of them) — Blink caches the query result per container, so this is a rule-match, not an evaluation, per bottom.

### 5.4 c32 run (auto-appended by run_chain.sh 2026-09-24 14:54:19; node rc=0)

# c32-p40 — 32/32 tokens, stopReason=token-limit, trigger=keyboard, heapFlag=True, load 33.8 s, Run at 36.8 s after nav

ids 32/32 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4P/reference_ids_32_40.json; prompt token 40); ids=[13, 198, 198, 464, 717, 1517, 314, 750, 373, 284, 467, 284, 262, 1957, 16918, 3650, 290, 2822, 257, 6131, 286, 12912, 32132, 13, 314, 373, 523, 6568, 284, 1949, 340, 13]
first mismatching position: None; mismatches at []

RecalcStyleCount per token (must be flat ≈ 84):  75   72   70   74   72   70   72   72   70   74   72   72   72   72   72   72   72   72   72   72   72   70   74   72   72   72   72   72   72   72   72   68  

RSS max MB per token:  3468   3899   4111   4096   4101   4143   3812   4173   4321   4080   4179   4149   3968   3845   3917   4111   4078   4186   4110   4469   4066   4043   3994   3832   3770   3670   3654   3585   3493   3640   3690   3718  

Memory state (before/after, R5H/run-R5H-c32/c32-p40.memstate.txt):
```
14:38:18 url=http://127.0.0.1:46194/work/2026-09-19/bundles/R5H-c32/index.html prompt=40 vm_stat: Pages free: 99094. Pages inactive: 293894. Pages speculative: 1626. Pages occupied by compressor: 160000. Pageouts: 1846729.  swap: total = 4096.00M  used = 2820.44M  free = 1275.56M  (encrypted)
14:54:17 node rc=0 vm_stat after: Pages free: 422813. Pages occupied by compressor: 243670. Pageouts: 1848911.  swap: total = 4096.00M  used = 3117.44M  free = 978.56M  (encrypted)
```

Full table: `R5H/run-R5H-c32/c32-p40.summary.md`.
