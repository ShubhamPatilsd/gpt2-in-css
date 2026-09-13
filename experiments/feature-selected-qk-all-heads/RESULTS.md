# Feature-selected QK and mixed-V results

## Question

Can one font-shaping operation expose substantially more useful matrix work than the
one-output-per-metric HVAR graph?

## Method

For each GPT-2 attention head, each query coordinate is rounded to one of 32 values.
An OpenType alternate-selection feature chooses a glyph containing the corresponding
pre-scaled K row. HVAR axes carry the 768 normalized source values. The advance of a
short glyph run is therefore the complete 64-value Q·K dot product, including K bias.

Chromium stops applying a long sequence of independent GSUB alternate lookups. A
64-feature run only produced correct values for its first few coordinates. Splitting
each head into groups of five features is reliable; groups of six intermittently omit
the sixth substitution.

The runtime artifacts contain HTML, CSS, and fonts only. JavaScript is used only by
the external benchmark harness.

## Isolated score results

- 12 real GPT-2 heads, 16 source tokens, 192 scores.
- Fresh-query update median: 174.7 ms.
- Matched existing geometry-score update: 2,278.7 ms.
- Score-stage speedup: 13.0×.
- Maximum browser shaping RMSE against the 5-bit-query reference: 0.0574.
- 36 WOFF2 fonts: 19,016,992 bytes.
- HTML fixture: 3,212,780 bytes.

Five-bit query binning itself is the larger accuracy cost on several heads. Per-head
score RMSE against the 8-bit-query reference ranges from about 0.03 to 0.33 in this
fixture. The font computation is more accurate than that quantization choice.

Across 160 held-out random-token sequences, the all-5-bit projected residual RMSE is
0.01489 and attention-winner agreement is 97.55%. Upgrading selected heads to 6-bit
does not give a sharp sparse win: three upgraded heads reduce RMSE to 0.01175 while
increasing alternate-glyph data by approximately 25%; nearly every head must be
upgraded to approach the all-6-bit RMSE of 0.00752.

Narrowing the existing conservative query range is more efficient. Using 0.6× the
current range with the same 32 bins produced 0.00951 projected-residual RMSE, 98.18%
winner agreement, and clipped 0.52% of query coordinates. This beats upgrading six
heads to 6-bit while adding no glyphs. It still needs broader natural-text validation
before replacing the conservative range.

A complete parallel 0.6× font set and connected browser fixtures were subsequently
built. The font payload remained effectively unchanged (19.03 MB versus 19.02 MB).
Against the conservative 1.0× range, block-0 projected-residual RMSE improved at
context 2 (0.03356 to 0.01621) and context 8 (0.01956 to 0.00803), but regressed
slightly at context 16 (0.01269 to 0.01306) and context 32 (0.01118 to 0.01452).
This confirms that 0.6× is not a universal replacement despite its better aggregate
calibration result.

Warm navigation time was also effectively unchanged: 1.39/2.49/4.06/6.63 seconds at
context 2/8/16/32. A matched persistent-page A/B showed no update-time win; the
narrower range can trigger more feature substitutions during small query changes.
Range selection should therefore be treated as an accuracy policy, not a speed
optimization.

## Connected attention

The fused score was connected to the existing real Q projection, softmax, V mixing,
attention output projection, residual, and 12-bit context transport. Registering the
192 score variables is required: without that numeric materialization boundary, CSS
substitutes the full score expression into every max/exp term and exceeds Chromium's
expression-complexity limit.

Folding K bias into the selected glyph advance removed 12,288 repeated CSS arithmetic
terms. The resulting projected residual is finite and matches the feature-query
reference with RMSE 0.0067 at context 16.

## Mixed-input V fusion

V projection is linear, so for each head:

`sum_s p_s * (Wv * x_s + b) = Wv * (sum_s p_s * x_s) + b`

The mixed-input fixture therefore combines the normalized source vectors first and
runs V projection once per head. It reduces projected V metric outputs from 12,288 at
context 16 to 768.

In a controlled trace at context 16:

| Backend | Wall time | DOM nodes | Layout | Text shaping |
| --- | ---: | ---: | ---: | ---: |
| Per-coordinate K and per-source V | 6,680.6 ms | 53,575 | 5,045.3 ms | 495.3 ms |
| Feature-selected QK | 4,509.9 ms | 33,992 | 3,406.2 ms | 369.0 ms |
| Feature-selected QK + mixed-input V | 3,654.0 ms | 10,963 | 2,689.0 ms | 257.9 ms |

The final variant is 1.83× faster in this controlled trace and removes 79.5% of the
nodes. Its projected residual RMSE is 0.0068.

## Context scaling

Three-round warm medians for feature-selected QK + mixed-input V:

| Context | Time | Browser RMSE |
| ---: | ---: | ---: |
| 2 | 1,421.1 ms | 0.00338 |
| 4 | 1,546.9 ms | 0.00683 |
| 8 | 2,398.2 ms | 0.00841 |
| 16 | 3,859.6 ms | 0.00683 |
| 32 | 6,334.8 ms | 0.00692 |

A subsequent baseline sweep in the same environment measured
1,247.7/1,999.9/2,678.3/6,876.6/15,086.2 ms. The new backend has higher fixed cost,
loses at context 2, and scales much better as context grows. The context-32 speedup in
that sweep is 2.38×.

Persistent-page query invalidation is a stronger result. Changing one live query-stage
input, waiting for the CSS lifecycle, and reading all 768 projected residual outputs
measured:

| Context | Previous backend | Feature QK + mixed V | Speedup |
| ---: | ---: | ---: | ---: |
| 2 | 343.4 ms | 251.1 ms | 1.37× |
| 8 | 967.4 ms | 283.4 ms | 3.41× |
| 16 | 3,105.5 ms | 632.4 ms | 4.91× |
| 32 | 8,431.7 ms | 719.2 ms | 11.72× |

The output changed and remained finite in every case. This is the clearest evidence so
far that fusing many useful outputs into each shaping operation improves the
autoregressive update curve, rather than only reducing initial page construction.

## Bundle tradeoff

At context 16, the connected mixed-input fixture contains approximately:

- 0.74 MB HTML
- 7.17 MB generated CSS
- 0.30 MB query-stage CSS
- 21.87 MB fonts

At context 32 the total is about 36.7 MB, compared with about 18.3 MB for the previous
backend. This approach currently trades a roughly 2× bundle for a much better
long-context runtime curve.

The mixed-V fixture still embeds its cached normalized source vectors as generated CSS
constants. It proves the algebra and browser cost for a fixed fixture. Fully dynamic
prompt inference still needs a reusable way to expose those cached vectors at the
global mixing scope without reconstructing thousands of per-number layout transports.

A nested-cache variant now tests that interface. Each token wrapper defines uniquely
named `--cache-token-dimension` values, and the attention mixer is nested inside all
wrappers so it inherits every prior vector. At context 16 it remains exact relative to
the embedded fixture (0.00683 browser RMSE). A three-round navigation run measured
4.24 seconds versus 3.86 seconds for embedded constants, with about 0.8 MB of extra
markup/CSS.

More importantly, live persistent-page mutations work without rebuilding the graph:

- query-stage coordinate update: 751.6 ms median
- cached-source coordinate update: 655.7 ms median
- simultaneous query and cached-source update: 830.4 ms median

All 768 projected residual outputs remained finite and changed in every case. This
does not yet compute and append an arbitrary new cache vector, but it establishes a
working CSS-only storage interface for reusable live vectors in the required
inheritance direction.

The nested-cache mutation curve remains controlled through context 32:

| Context | Query update | Cached-source update |
| ---: | ---: | ---: |
| 2 | 318.4 ms | 468.2 ms |
| 8 | 467.8 ms | 581.5 ms |
| 16 | 784.6 ms | 764.3 ms |
| 32 | 1,034.4 ms | 1,064.5 ms |

These numbers include two animation frames and reading all 768 outputs. The wrapper
interface adds overhead compared with embedded constants, but avoids the old
multi-second/superlinear invalidation curve.

## Next experiments

The projected-KV cache experiment in `../projected-kv-qk/RESULTS.md` supersedes the
mixed-input V architecture for autoregressive inference. It reduces the score font
bank from about 19 MB to 0.168 MB and removes the 12 by 768 mixed-input expressions.

1. Derive and validate per-head query ranges on a broader natural-text calibration set.
2. Test 6-bit query selection only if calibrated 5-bit ranges still miss the accuracy target.
3. Materialize the 12×768 mixed inputs more compactly; their repeated weighted sums
   now dominate generated CSS and style evaluation.
4. Measure persistent-page token append/update, not only warm navigation.
5. Reuse the same linear-before-mixing transformation for other projection/mixing
   boundaries where it is algebraically exact.
