# Fused QK → exponential → weighted V inside one font

Measured September 17, 2026, in Chrome 153.0.8010.48 on macOS Darwin 25.0.0.

## Decision

The font can perform the proposed fusion correctly over a bounded input
domain, but the complete attention component is slower than numeric CSS.
Do not integrate this backend into the twelve-layer runtime.

| Matched screen | CSS query change | Fused query change | CSS all-input change | Fused all-input change |
| --- | ---: | ---: | ---: | ---: |
| 64 exponential segments | 1.825 ms | 9.594 ms | 2.375 ms | 9.335 ms |
| 16 exponential segments | 1.953 ms | 7.721 ms | 1.829 ms | 7.148 ms |

These are medians from seven measured rounds after one discarded warm-up
round. Each round opens one page at a time; CSS/fused order reverses on odd
rounds. Both variants start with the same changing Q/K/V CSS input numbers and
finish with all 64 normalized context coordinates plus the denominator exposed
as geometry. Input mutation and final geometry reads are inside the wall timer.
The external harness does not calculate intermediate model values for the page.

Reducing region count improved the fused implementation, but it remained about
four times slower than its matched CSS baseline on both fresh update types.
The 64-segment screen was 5.26× slower for query changes and 3.93× slower for
all-input changes. No full-model speedup or tokens/second claim follows from
these component measurements.

## Computation and transport

The fixture is one 64-dimensional head with four cached tokens. A font instance
receives 194 axes: Q[64], K[64], V[64], one initially zero score axis, and one
constant axis. The same face serves every cached slot and every output glyph.

1. The `avar2` map uses 257 regions to form the scaled bilinear dot product and
   offset it into a normalized score coordinate. Q, K and V remain unchanged.
2. HVAR computes a piecewise-linear exponential of that score, multiplies it by
   each V coordinate, and emits 64 numerator contributions plus one denominator
   contribution. There is no score or per-token probability capture in CSS.
3. Four glyph advances sum in each output row. An anchor-size reader captures
   the denominator; 64 numerator readers capture their sums in the same
   positioning scope. CSS performs the final division.

The real function is `sum(exp(score - c) * V) / sum(exp(score - c))` with a
fixed, calibrated `c`. The common factor cancels mathematically. It is not a
runtime maximum reduction, and its usable range is bounded by the font's
fixed-point coordinates and exponential approximation.

The baseline computes 64-term QK dot products, exponentials, weighted sums and
division using registered CSS numbers, then exposes the same final result
geometry. It does not insert an artificial font/readback boundary. Dense QKV
projection, cache insertion, all twelve heads, and full-model generation are
outside this comparison.

## Numerical checks

Calibration uses GPT-2-small layer 0, head 0, positions 0–7 from the saved model.
The measured all-input change uses positions 8–11, which were not used to choose
the input scales or score interval. The independent reference computes Q/K/V
from the stored checkpoint, not from page output. No model download occurred.

| In-domain validation | 64 segments | 16 segments |
| --- | ---: | ---: |
| Largest context RMSE versus exact attention | 0.001712 | 0.001920 |
| Largest coordinate error versus exact attention | 0.004281 | 0.004555 |
| Largest coordinate error versus encoded-font reference | 0.004356 | 0.004628 |
| Largest denominator relative error versus exact exp | 0.1293% | 2.2344% |
| Input/score clipping in supported cases | none | none |

Both variants pass the declared component gates: finite outputs, maximum
transport error below 0.01, maximum true coordinate error below 0.1,
denominator relative error below 5%, and no clipping. These are local screening
tolerances, not proof that errors are acceptable through twelve layers.

Every measured round checks all coordinates for query-only changes, all-input
changes, returning to old inputs, zero query/uniform attention, zero values,
signed cancellation and the calibrated score interval's endpoints. The encoded
reference separately accounts for axis and coefficient quantization and the
piecewise exponential. Browser widths are also compared against every summed
font row; this distinguishes bad font arithmetic from bad final transport.

Two deliberately unsupported domain probes are retained separately and are
excluded from in-domain correctness/timing summaries:

- A score above the calibrated interval clips inside `avar2`. In the 16-segment
  browser run this produces 0.19739 maximum context error and an 86.80%
  denominator error. Numeric CSS handles the same input correctly.
- Two saved real layer-11 QKV samples, duplicated equally to fill four slots,
  clip 14 coordinates under the layer-0 input scales. Maximum context error is
  0.64025, versus approximately 0.000020 for the CSS baseline. This is an explicit
  counterexample to using one layer's calibration as a whole-model guarantee.

The calibrated input scales are Q=2.97242, K=4.86643, V=1.95980. The score
coordinate covers approximately [-4.88106, 1.97860]. Outside those limits the
font is not a general exact attention implementation.

## Where the extra work went

For fresh query/all-input changes, average browser counters were:

| Screen/backend | Style recalculation | Layout | Renderer task |
| --- | ---: | ---: | ---: |
| 64-segment CSS | 0.955 ms | 0.063 ms | 1.273 ms |
| 64-segment fused | 2.086 ms | 6.574 ms | 9.216 ms |
| 16-segment CSS | 0.988 ms | 0.067 ms | 1.340 ms |
| 16-segment fused | 2.084 ms | 4.497 ms | 7.006 ms |

Style and layout are categories within renderer work; do not add the task
column to them. These counters do not isolate font arithmetic from the layout
that invokes it. The actual data supports a narrower conclusion: removing
intermediate CSS scores introduced more font/layout work than the baseline
arithmetic cost. Style work also increased.

The baseline has 73 elements; the fused page has 464. Four slots require 260
shaped glyphs, 65 sum rows and 65 geometry captures. The 64-segment font contains
8,384 HVAR regions and expands to 10,111,176 bytes; 16 segments reduce that to
2,192 regions and 2,879,952 bytes. Both retain 194 axes and 257 avar2 regions.
This is a measured region-count scaling check, not a measured context-length
or head-count scaling curve.

## Failed attempts retained

- `s64/`: initial WOFF2 page used a fallback font. Its numerical failure is
  recorded. Its apparent timings are invalid and excluded.
- `s64-mapfix/`: sparse variation mappings were changed to explicit empty
  delta sets. The browser still rejected the WOFF2 with `Failed to convert
  WOFF 2.0 font to SFNT`. The font-load assertion now prevents fallback timings.
  The exact decoder cause was not established.
- `s64-ttf/`: the raw TTF loaded and all font-row sums were close to their
  encoded references, but the normalized reader failed. Numerator anchors lay
  outside the containing block created by the denominator's size container.
- `s64-anchor/`: relocating numerator anchor sources into the same positioning
  scope fixed the complete reader. Two-round diagnostics and eight-round
  confirmation are preserved separately.
- `s16-ttf/`: the single targeted follow-up reduced exponential region count.
  Eight rounds remained slower; this is the stop condition for this approach.

The high compression ratios are not presented as proof of why WOFF2 failed.
Successful measurements use raw TTF. These are approximately 45 MB of local
artifacts including failed attempts, generated pages, fonts, reference data,
source snapshots and browser results. No source/model assets were deleted.

## Reproduce

Run from the repository root. Directory labels and result filenames are
immutable; use fresh labels for new builds. The wrapper serializes cooperating
builds and browser experiments. It does not exclude unrelated machine activity.

```sh
python3 tools/run_unconventional_isolated.py --label fused-attention -- uv run tools/build_fused_attention_font_probe.py --segments 64 --label reproduce-s64
python3 tools/run_unconventional_isolated.py --label fused-attention -- node tools/test_fused_attention_font_probe.mjs reproduce-s64 8
python3 tools/run_unconventional_isolated.py --label fused-attention -- uv run tools/build_fused_attention_font_probe.py --segments 16 --label reproduce-s16
python3 tools/run_unconventional_isolated.py --label fused-attention -- node tools/test_fused_attention_font_probe.mjs reproduce-s16 8
```

Current code includes the later layer-11 domain probe for either segment count;
the original 64-segment report predates that added case. The original measured
pages and harness snapshots remain in their own directories. The final source
received formatting/import cleanup after measurements; no page was regenerated
over a measured artifact. Ruff and Node syntax checks pass.

Primary machine-readable evidence:

- [64-segment complete measurement](s64-anchor/browser-results-r8.json)
- [16-segment complete measurement and late-layer counterexample](s16-ttf/browser-results-r8.json)
- [64-segment font/reference manifest](s64-anchor/manifest.json)
- [16-segment font/reference manifest](s16-ttf/manifest.json)

Browser flags were `--allow-file-access-from-files` and
`--enable-experimental-web-platform-features`; Node was v26.5.0. All runtime
pages contain zero script elements and a `script-src 'none'` policy. The external
Playwright harness supplies case selections, loads fonts and observes geometry.
It does not provide scores, probabilities, numerators, denominators or answers.
