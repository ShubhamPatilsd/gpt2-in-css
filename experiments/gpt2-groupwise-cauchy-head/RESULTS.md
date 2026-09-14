# GPT-2 group-level blockwise-Cauchy output-head experiment

## Decision

**Retain the 96-block group-level carrier for an integrated cascade test.** It keeps GPT-2-small's architecture and checkpoint weights unchanged, retains the exact float winner on all 1,024 saved states, cuts test exact work from 4.555 groups / 1,164 rows to 2.215 groups / 567 rows on average, and adds only one 96-axis residual glyph per 256-row group (197 total).

Unlike the rejected per-row 96-axis carrier, this representation does not impose a measurable full-scale coarse-pass penalty. At all 197 groups, median live mutation was 1,049.8 ms versus 1,085.3 ms for the retained global-Cauchy control; cold layout was 40.40 s versus 41.27 s. These single-process differences are small enough to treat as performance parity, not a claimed speedup. The useful result is that stronger pruning is now available without the prior 1.7 s incremental cost.

This is not yet an end-to-end output head. The strict pages cover all coarse score rows, within-group maxima, and certified group residual additions, but exclude the iterative router and exact follow-up groups. Integration is the next required gate.

## Certified group bound

For signed int10 reconstruction `q_i`, residual `e_i = w_i - q_i`, 256-row group `G`, and 96 blocks of width 8, the experiment uses

```text
max_(i in G) h·w_i
  <= max_(i in G) h·q_i
     + sum_b ||h_b||₂ max_(i in G) ||e_i,b||₂.
```

Each row dot product is widened before the group maximum. Residual and query block norms include float64 product/sum envelopes and are rounded toward positive infinity. Radius reductions and final upper endpoints are also rounded upward; exact comparison values are rounded downward. The browser font uses `ceil` coefficients, one positive F2DOT14 axis step, and one positive 4 px score bucket at both the reconstructed-score and group-radius stages.

A fresh float64 tied-head oracle reproduced all 1,024 saved winners. Every tested groupwise block count retained 1,024/1,024 winners.

## Offline pruning

Best-first exact work means groups are sorted by certified group upper, evaluated exactly in that order, and stopped when the incumbent exact lower bound reaches the next group upper.

| Certificate | Split | Exact groups mean / median / p95 / max | Exact rows mean / median / p95 / max |
|---|---|---:|---:|
| Global per-row Cauchy, 1 block | validation | 4.484 / 3 / 14 / 28 | 1,143.9 / 768 / 3,584 / 7,168 |
| Global per-row Cauchy, 1 block | test | 4.555 / 3 / 14 / 49 | 1,163.9 / 768 / 3,584 / 12,544 |
| Per-row Cauchy, 96 blocks | validation | 1.332 / 1 / 2 / 4 | 341 / 256 / 512 / 1,024 |
| Per-row Cauchy, 96 blocks | test | 1.422 / 1 / 3 / 6 | 364 / 256 / 768 / 1,536 |
| **Group-level Cauchy, 96 blocks** | **validation** | **1.980 / 2 / 4 / 10** | **507 / 512 / 1,024 / 2,560** |
| **Group-level Cauchy, 96 blocks** | **test** | **2.215 / 2 / 6 / 12** | **567 / 512 / 1,536 / 3,072** |

The group maximum costs 0.648 validation and 0.793 test groups relative to the stronger per-row 96-block certificate, but still saves 2.504 validation and 2.340 test groups relative to the retained global bound.

The groupwise block sweep shows that the gain is genuinely blockwise rather than a side effect of grouping:

| Blocks × width | Validation mean exact groups | Test mean exact groups | Test maximum rows |
|---:|---:|---:|---:|
| 1 × 768 | 20.410 | 22.227 | 43,601 |
| 3 × 256 | 9.566 | 10.383 | 26,624 |
| 6 × 128 | 5.785 | 6.363 | 13,568 |
| 12 × 64 | 4.770 | 5.293 | 11,776 |
| 24 × 32 | 3.207 | 3.453 | 6,400 |
| 48 × 16 | 2.398 | 2.684 | 4,352 |
| **96 × 8** | **1.980** | **2.215** | **3,072** |

## Live carrier and clamp repair

The browser candidate contains the same five score glyphs per vocabulary row as the control, removes the global scalar residual term from each row, and appends one group-residual glyph after each 256-row grid maximum. The group glyph has 96 nonnegative HVAR axes and contributes directly to the group's width.

The first carrier encoding was invalid and its timings were discarded. It used a large positive base advance plus 800% `size-adjust`; Chrome clamped the shaped advance to 32,768 px before `calc-size`, so subtracting the intended base collapsed every residual width to zero. Computed variation strings changed, but `changedBounds` was zero.

The repaired font has zero default advances. This is valid because all axes and deltas are nonnegative; the varied HVAR advance is the radius itself, with no base subtraction and no shaped-advance clamp. The final WOFF2 is 14,772 bytes.

The verifier requires more than changing computed CSS:

- all 96 registered `--bn*` values change between the median- and p90-norm fixtures;
- all 96 computed bound-font axis coordinates change;
- bound glyph geometry changes;
- the first eight measured bound widths equal independently predicted outward 4 px buckets.

At full scale, all 197 bound glyphs changed width. Representative predicted/measured widths were exactly `668, 600, 432, 404, 464, 392, 464, 392` px before and `700, 632, 460, 424, 492, 416, 488, 416` px after. Thus the retained timings measure a live HVAR contribution, not a dead declaration.

## Chrome scaling and payoff gate

Chrome 153.0.8010.36, fresh browser process per point, five alternating state mutations with the median reported. The pages are script-free; Playwright is only the external verifier. Each first layout and mutation batch has a hard 60 s process cutoff, and `page.goto` uses the same 60 s limit so no shorter navigation default can misclassify a point.

| Groups / rows | Global cold | Groupwise cold | Cold ratio | Global mutation | Groupwise mutation | Mutation ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 1 / 256 | 0.993 s | 1.016 s | 1.02× | 8.83 ms | 9.35 ms | 1.06× |
| 4 / 1,024 | 2.000 s | 1.888 s | 0.94× | 24.26 ms | 23.33 ms | 0.96× |
| 16 / 4,096 | 6.635 s | 6.758 s | 1.02× | 84.69 ms | 104.63 ms | 1.24× |
| 64 / 16,384 | 24.190 s | 24.694 s | 1.02× | 353.82 ms | 360.41 ms | 1.02× |
| 197 / 50,257 | 41.269 s | 40.398 s | 0.98× | 1,085.29 ms | 1,049.80 ms | 0.97× |

The predefined 64-group early gate passes:

```text
extra groupwise coarse cost = 360.408 - 353.815 = 6.593 ms
validation exact groups saved = 4.484 - 1.980 = 2.504
test exact groups saved       = 4.555 - 2.215 = 2.340
break-even exact-group cost   = 2.63 ms validation / 2.82 ms test
one-group same-font control   = 8.83 ms
maximum credited savings     = 22.10 ms validation / 20.65 ms test
```

The candidate was neither at least 2× and 100 ms slower nor above the same-font payoff allowance, so the full 197-group point ran. It also completed within 60 s and was 35.5 ms faster on the median mutation in this run. Given timing noise, the conservative conclusion is parity plus materially better certified pruning.

## Artifacts

- `offline-results.json`: all 1,024-state certificates, block sweep, and prior-certificate comparisons.
- `group-residual-norms-96.npy`: exact outward-rounded 197 × 96 group coefficient source.
- `group-bound-96.ttf` / `.woff2`: zero-base, nonnegative 96-axis carrier.
- `reference.json`: fixture vectors, expected font radii, safety contract, and gates.
- `browser-results.json`: authoritative corrected timing and geometry evidence.
- `scaling/`: nested 1/4/16/64/197-group script-free control and candidate pages.

Nothing was committed or pushed.
