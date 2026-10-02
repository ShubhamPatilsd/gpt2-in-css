# bundles/combined4-c32d — combined4-c32c + `R4W_V_PRECAT=1` (R4W, 2026-09-21)

**= `bundles/combined4-c32c` recipe (R4D tools: widths value layout, F4 packed banks, R4D flags) + the R4W V-leaf allocation fix**
(`work/2026-09-19/R4W/tools/r4w_precat.py`, edits in `R4W/tools/browser_gpt2_font_vector_cache.py`; the tools copy differs from
`R4D/tools` ONLY in those two files — `diff -rq`). Model, weights, operator fonts' advance tables, KV latching, scores, softmax
and the row formula are unchanged.

## Recipe

Built 2026-09-21 04:16 by `R4W_V_PRECAT=1 work/2026-09-19/R4W/compile-r4w.sh combined4-c32d 32 12` (log `R4W/compile-c32d.log`;
`compile-r4w.sh` = `R4D/compile-r4d.sh` with `R4D_VALUE_LAYOUT=widths` default and `R4W_V_PRECAT` exported; tools = `R4W/tools`).
Smoke pair: `smoke-R4W-2L` (=1) / `smoke-R4W-2L-ref` (=0), `compile-r4w.sh <name> 8 2` (2 blocks, capacity 8).

## What changed (R4V §5.1 fix; mechanism in R4W.md §1)

In c32c each of the 768·p filled V leaves declares `font-variation-settings:var(--fr-v-S-H),"P000" 1` + `width:calc-size(…var(--fw-H-S))`;
Blink re-substitutes (copies ~1.1 KB), re-tokenises and re-parses the 65-axis list and rebuilds a FontVariationSettings for every leaf
on every restyle of the leaf subtree (12 per token, one per layer), ≈4 KB of garbage per filled leaf per restyle, ∝ p.

c32d (`R4W_V_PRECAT=1`, "wrapper" mode) moves the list off the leaves without touching the numbers:
- 32 slot fonts `FvsValueSlotS` (`R4W/assets-r4w/font-vector-operators-r4w/value-sS-<digest>-r4w.woff2`): the v2 value operator with its
  64 V axes retagged to `V{S·64+i}` and its cmap shifted by S·64, `unicode-range:U+F5800+S·64…+63`. HVAR/hmtx/glyf/loca/maxp/hhea byte-identical
  to the source (asserted at build); HVAR evaluation at random locations equals the F4 head fonts (R4W.log.md 04:2x).
- Latched lists `--fc-v-S-H` carry slot tags: `--fvs-live-v-H` = `if(style(--fvs-write-slot:S):"V{S·64+i}" var(--fvn-v-H-i),…;else:…)`
  (the emitter's existing fallback-layout form); `@property` initial values `"V{S·64}" 0`.
- One head wrapper `<div class="fvs-value-head-H">` (display:contents) around the head's 64 rows:
  `font:1024px FvsValueSlot0,…,FvsValueSlot31;font-kerning:none;font-style:normal;font-variation-settings:var(--fr-v-0-H),…,var(--fr-v-31-H),"P000" 1`
  — the 65·p-axis list is substituted + parsed 12× per restyle (once per head) instead of 768·p×.
- Leaves: `<i class="fvs-v-H-S">&#x{F5800+S·64+i};</i>` with `.fvs-v-H-S{width:calc-size(max-content,calc(12320.768px + (size - 12320.768px) * var(--fw-H-S)));min-width:0;flex:none}`
  — no font property at all (Font inherited by pointer); the character selects the slot font through unicode-range.
- `.fvs-value-row{display:inline-flex;gap:0;line-height:1;white-space:pre}` (no `font:` shorthand, which would reset the inherited settings).
- The 12 `FvsValueH` faces are no longer referenced and are not emitted; the font barrier (witnesses) covers the 32 slot fonts instead.
- `R4W_V_PRECAT=alias` = R4V §5.1(a) literally (latched `--fc-v-S-H:var(--fvs-live-v-H),"P000" 1`, leaf `font-variation-settings:var(--fr-v-S-H)`) — exact,
  but saves only the 10-B literal per leaf per restyle (not built as a bundle).

Exactness: the same 6-digit numbers reach axes with the same HVAR regions in fonts with identical advance tables, P000 = 1 as before, the weight
stays in the leaf width, the row formula is unchanged → identical shaped advances, identical LayoutUnit snapping, identical row sums.

## Offline verification (R4W.log.md, R4W.md §3)

- `R4D/rule_diff.py` c32c → c32d: only `.fvs-v-N-N` (384), `@property --fc-v-N-N`/`--fr-v-N-N` (372 each; the 12 S=H initial values coincide),
  `.fvs-query` (12: the live-v `if()` lists), `.fvs-value-head-N` (+12), `.fvs-value-row` (1), `@font-face` (−12 +32) and the font barrier
  (`.font-proof-N`, `.font-all-N-N`).
- `index.html`: identical after normalising the value-row leaf characters, the 12 head wrappers and the barrier probes/proofs/reductions.
- `font-witnesses.json`: 271 shared faces identical; −12 `value-hH-…-f4`, +32 `value-sS-…-r4w` (advance 12032/1000 upem each).
- `tools/launch_browser_gpt2.py --check`: static, `runtimeJavaScript:false` (c32d and both smokes).
- NumPy reference untouched (tools diff = emitter only); prompt-40 free-running ids re-derived with the R4W tools copy = `R4P/reference_ids_32_40.json`.

## Chrome (R4W.md §4)

Pending at build time: 2-layer smoke pair ids identical, then ONE passive 32-token run with `B0_PROMPT_TOKEN=40` (`R4W/run-combined4-c32d/`).
READY is written only on 32/32.
