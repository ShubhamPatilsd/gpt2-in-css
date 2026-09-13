# CSS Grid argmax

Measured in headless Chrome 153 on macOS on September 13, 2026. Runtime pages
contain HTML and CSS only; the Playwright scripts are external test harnesses.

## Result

A max-content Grid track can reduce all 50,257 GPT-2 vocabulary candidates to
one maximum. Encoding the score in the high bits and an inverted token ID in
the low bits also makes the winning token recoverable in CSS.

The direct encoding is limited to about 24 reliable bits. A flat 16-bit token
ID therefore leaves only eight score bits. The full-vocabulary synthetic page
was exact, but its settled mutation median was about 365 ms.

A two-level construction removes that score limit:

1. Each 256-token Grid selects a 16-bit score plus an 8-bit local token ID.
2. `calc-size()` replaces the local ID with the group ID.
3. An outer Grid selects the winning group.
4. CSS anchor geometry gates that group's original inner width back into a
   final reader, which recovers the local ID.

The final token is `group * 256 + local`. Ties select the lowest token ID, like
a conventional first-index argmax.

| Candidates | Groups | Settled mutation median | Correct |
| ---: | ---: | ---: | :---: |
| 256 | 1 | 6.2 ms | yes |
| 4,096 | 16 | 19.0 ms | yes |
| 50,257 | 197 | 178.0 ms | yes |

The 50,257-candidate hierarchy contains 50,860 elements and 2.98 MB of HTML.
Its first two mutations took 276-286 ms; the five settled mutations took
174-179 ms. Unlike the previous DOM maximum, this returns the token ID rather
than only the maximum width.

## Real output-head integration

`../grid-hierarchical-output-head/` applies the same hierarchy to the real
50,257 by 64 tied embedding table from `calum/tinystories-gpt2-3M`. Scores are
computed from the live hidden-state CSS variables, quantized at 1/1024 logit,
and reduced with the 16-bit hierarchy.

All three reference prompts select the exact dense NumPy winner:

- `Once upon a time` -> token 11
- `The little girl` -> token 373
- `One day` -> token 11

The browser's recovered winning score bucket differs from NumPy by at most one
bucket due to CSS arithmetic/layout rounding. That is far below the measured
winner margins and does not change a token.

The complete real head still takes about 4.4 seconds per mutation and loads in
about 6.7 seconds. Its HTML is 51.5 MB because it serializes all 3.2 million
embedding weights. This essentially matches the old 4.35-second DOM-layout
maximum benchmark. The new 178 ms reduction is therefore not the dominant
cost: evaluating the 50,257 live dot products as CSS expressions is.

This is still a useful architectural result. Browser-native argmax and token-ID
recovery no longer require a 170-186 MB registered-property winner graph. The
next useful integration is to feed widths from a compact font-based or other
matrix backend into this hierarchy, then select the winning embedding without
expanding another all-token arithmetic graph.

## HVAR scorer integration

`../hvar-grid-output-head/` replaces the 3.2 million serialized CSS multiply
terms with one variable font. Each of its 50,257 glyph advances computes one
64-dimensional token score. A per-row signed int8 quantizer keeps the font
compact, while each candidate's `calc-size()` converts its glyph advance into
the common score scale consumed by the hierarchy.

The quantized matrix preserves all 72 real recurrent winners in the offline
test. The browser selects the dense reference token for all three live prompts,
with at most one 1/1024-logit bucket of numeric disagreement.

| Real TinyStories head | CSS dot expressions | HVAR + Grid |
| --- | ---: | ---: |
| Browser mutation | 4.4-4.6 s | 0.87 s settled median |
| HTML | 51.5 MB | 4.07 MB |
| CSS | 53.9 KB | 54.1 KB |
| WOFF2 | none | 2.30 MB |
| Exact live winners | 3/3 | 3/3 |

Three independent nine-round browser processes produced settled medians of
954.2, 862.9, and 872.2 ms; the median of runs is 872.2 ms. Every winner was
correct and the largest score disagreement was one bucket.

This is a roughly 5x runtime improvement and an 8x raw-bundle reduction
over the direct CSS score graph. It is close to the old 0.71-second clustered
CSS winner search while reducing that implementation's roughly 171 MB source
to 6.42 MB. HVAR + hierarchical Grid is therefore the current best
full-vocabulary score-and-token backend by overall speed/size tradeoff.

## Token feedback integration

The HVAR scorer now feeds the recovered group and local token ID into the
two-axis HVAR embedding lookup in `../hvar-token-embedding-lookup/`. A 12-bit
two-plane anchor pack then gathers the 64 lookup glyph widths into variation
axes for the real first-block `64 -> 192` QKV HVAR matrix. The browser performs
this entire boundary without external help:

1. compute all 50,257 logits;
2. recover the exact winning token ID in CSS; and
3. retrieve all 64 coordinates of the winning token embedding;
4. pack them into 16 two-dimensional CSS containers; and
5. use the reconstructed vector to evaluate the next QKV matrix.

The connected page selects every dense reference winner. Its largest embedding
coordinate error is 0.000115. The QKV result differs from the expected
transported-and-quantized matrix by at most 0.000333, and from the dense
floating-point result by at most 0.00972.

Three independent nine-round runs produced a median settled mutation of 906 ms
with the feedback subtree disabled and 933 ms with embedding lookup, 12-bit
registered-property gather, and QKV enabled. The complete feedback boundary
therefore adds about 28 ms in this paired sample. The raw runtime bundle is
10.70 MB, including the
4.21 MB reusable embedding lookup font.

This closes token selection, token-to-vector lookup, and one real dense matrix
handoff for the 64-wide TinyStories model. It does not yet include positional
embedding, layer normalization, attention, or the remaining block, so it is
not a complete recurrent generation step. The important change is that the
sibling-local vector gather is no longer hypothetical at width 64; the next
question is how its nested animation chain scales toward width 768 and across
many consecutive matrices.

## Reproduce

```sh
python3 tools/build_grid_argmax_probe.py
node tools/test_grid_argmax.mjs
python3 tools/build_grid_hierarchical_argmax.py
node tools/test_grid_hierarchical_argmax.mjs
PYTHONPATH=tools python3 tools/build_grid_hierarchical_output_head.py
node tools/test_grid_hierarchical_output_head.mjs
PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
  python tools/build_hvar_token_embedding_lookup.py
node tools/test_hvar_token_embedding_lookup.mjs
PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
  python tools/build_hvar_embedding_qkv_chain.py
HVAR_EMBEDDING_QKV_VARIANT=b12 node tools/test_hvar_embedding_qkv_chain.mjs
PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
  python tools/build_hvar_grid_output_head.py
node tools/test_hvar_grid_output_head.mjs
```
