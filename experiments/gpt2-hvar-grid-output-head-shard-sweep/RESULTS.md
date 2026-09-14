# GPT-2 output-head HVAR shard width

Measured in headless Chrome 153 on macOS on September 13, 2026. Both pages
perform the same global-int11 dot products over all 50,257 GPT-2 tokens and
use the same CSS Grid argmax. Runtime pages contain no JavaScript.

## Result

| Variant | Glyphs/token | Estimated shaped glyphs | HTML | Fonts | Settled query | 768-value mutation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 160 axes/font | 5 | 251,285 | 1.41 MB | 48.24 MB | 942.7 ms | 2,078.4 ms |
| 256 axes/font | 3 | 150,771 | 1.01 MB | 48.55 MB | 866.3 ms | 1,630.5 ms |

The three-font representation preserves the exact same quantized winners and
score error. It reduces glyph instances by 40%, improves the settled built-in
query by 8.1%, and improves the mutation that replaces all 768 inputs by
21.5%. Font bytes remain essentially unchanged because the same 38.6 million
weight coefficients are still present.

The accurate staged selective head confirms the limit of the optimization.
Its coarse phase improves from 686.7 to 628.9 ms, but total head time remains
about 1.03 seconds because the fine, near-score, dither, and CSS reduction
stages remain. Both variants return every expected dense winner.

## Decision

Use 256-axis shards for the coarse output head: it is strictly better on the
measured path and also removes about 402 KB of HTML. Do not pursue further
shard tuning as the main scaling strategy. The tested HVAR browser path accepts
at most 256 axes per font, and transformer matrices already use 256-axis
shards. Fewer glyph runs do not remove the per-axis dot-product work or the
50,257-element CSS argmax.

## Row-wise int10 follow-up

The same three-shard packing also works for row-wise int10 once the font writer
allows a valid unsigned base advance plus HVAR deltas to produce a shaped
result above 65,535. Chrome 153 preserves those advances. The standalone page
matches all 11 generated int10 winners with at most six buckets of browser
error. Composed with certification, hot-2 exact rows, block-flow groups, and
the fan-in-16 router, it passes 30/30 and improves loaded mean 2.0% and p90
11.9% over the five-shard page. See
`../gpt2-hvar-grid-output-head-int10-shard256/RESULTS.md` and
`../gpt2-mixed-hot2-blockflow-group-max-shard256/RESULTS.md`.

## Reproduce

```sh
make gpt2-hvar-grid-output-head-global11-shard256
GPT2_HVAR_GRID_HEAD_DIR=gpt2-hvar-grid-output-head-global11-shard256 \
  GPT2_HVAR_GRID_HEAD_ROUNDS=7 node tools/test_gpt2_hvar_grid_output_head.mjs
make test-gpt2-hvar-grid-output-head-cascade-near-dither7-shard256-staged
```
