# GPT-2 blockwise-Cauchy output-head experiment

## Decision

Reject the current **96-axis browser carrier**, but retain the blockwise-Cauchy certificate as an offline pruning result. The live carrier saves about 3.1 exact 256-row groups per query, but adds 1.714 s to the 64-group coarse mutation. It would need every avoided exact group to cost 544–547 ms to break even; the same-font one-group control costs only 32.4 ms including fixed overhead.

The original full candidate exceeded 180 s at first/full layout and was stopped. It was not retried. That run used a dead combined-axis declaration, so it is recorded only as a failed full gate, not as evidence against the mathematical bound.

## Certified offline result

The GPT-2 architecture and float checkpoint weights are unchanged. The experiment targets all 50,257 tied output rows at width 768 over 1,024 saved hidden states (512 train, 256 validation, 256 test). A fresh float64 oracle reproduced all 1,024 saved winners.

For row-wise signed int10 reconstruction `q` and residual `e = w - q`, each block configuration uses

```text
h·w <= h·q + Σ_b ||h_b||₂ ||e_b||₂.
```

Residual norms and floating interval endpoints are rounded toward positive infinity. Font coefficients use `ceil`, normalized font axes receive one full positive F2DOT14 step, and browser upper buckets use `floor + 1`. Both the global and 96-block certificates retained the original float winner on 1,024/1,024 states.

| Bound | Split | Exact rows mean / median / p95 / max | Exact groups mean / median / p95 / max | Candidate tokens mean / median / p95 / max |
|---|---|---:|---:|---:|
| Global Cauchy (1 block) | validation | 1143.90 / 768 / 3584 / 7168 | 4.484 / 3 / 14 / 28 | 92.51 / 53 / 312 / 657 |
| Global Cauchy (1 block) | test | 1163.95 / 768 / 3584 / 12544 | 4.555 / 3 / 14 / 49 | 98.70 / 52 / 422 / 693 |
| Blockwise Cauchy (96 × 8) | validation | 341.00 / 256 / 512 / 1024 | 1.332 / 1 / 2 / 4 | 4.04 / 3 / 11 / 19 |
| Blockwise Cauchy (96 × 8) | test | 364.00 / 256 / 768 / 1536 | 1.422 / 1 / 3 / 6 | 3.97 / 3 / 12 / 23 |

Thus the 96-block certificate is strong offline: it cuts mean exact work by about 70% and remains well below the requested 2,000-row budget (test max 1,536 rows).

## Live-axis repair

The first scaling attempt was invalid and discarded: `changedGroups` was zero for every blockwise page and computed `font-variation-settings` was `normal`. Two issues were fixed:

1. Chrome rejected one combined declaration containing 768 score axes plus 96 bound axes. The bound glyph now lives in a child span with its own 96-axis declaration; the parent retains the original 768 score axes.
2. The generated block norms were unregistered and then initially resolved to zero because binary `+` lacked required CSS whitespace. All 96 `--bn*` values are now registered numeric properties and the math is emitted with valid operators.

Final diagnostics show 768 resolved score axes and exactly 96 resolved bound axes. On the representative median-norm to p90-norm mutation, `--bn0` changes from 0.719875 to 6.36562 and every measured blockwise group changes width.

## Bounded Chrome scaling curve

Chrome 153.0.8010.36, fresh browser process per point, same five score fonts and the same nested first 1/4/16/64 vocabulary groups (256 rows each). The pages include only coarse score rows and the within-group CSS grid maximum; the full router is intentionally excluded. Each first layout and mutation had an independent hard 60 s process-group cutoff.

| Groups / rows | Global cold | 96-block cold | Cold ratio | Global mutation | 96-block mutation | Mutation ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 1 / 256 | 1.056 s | 1.127 s | 1.07× | 32.4 ms | 54.3 ms | 1.68× |
| 4 / 1,024 | 1.973 s | 2.379 s | 1.21× | 51.2 ms | 143.6 ms | 2.81× |
| 16 / 4,096 | 6.879 s | 8.448 s | 1.23× | 112.9 ms | 544.0 ms | 4.82× |
| 64 / 16,384 | 25.054 s | 29.362 s | 1.17× | 399.6 ms | 2113.9 ms | 5.29× |

The 64-group first layout stays below 60 s, but live mutation is decisively slower and scales approximately with the number of bound glyphs.

### Fast rejection gate

At 64 groups:

```text
extra live coarse cost = 2113.9 - 399.6 = 1714.3 ms
validation groups saved = 4.4844 - 1.3320 = 3.1523
test groups saved       = 4.5547 - 1.4219 = 3.1328
break-even exact group  = 543.8 ms validation / 547.2 ms test
```

Even crediting each saved exact group with the entire 32.4 ms one-group control time yields only 102.1 ms validation / 101.5 ms test savings. This is more than 16× short of paying for the live 96-axis coarse pass. The fast gate therefore rejects this font-carrier realization without rejecting the certified blockwise bound itself.

## Artifact shape

- Added bound font: 5,737,388 bytes WOFF2.
- Full generated candidate: 9,681,793-byte HTML and 258,875-byte CSS.
- Coarse representation: original five score glyphs plus one residual-bound glyph per vocabulary row.
- Browser curve artifacts: `scaling/control-{1,4,16,64}.html` and `scaling/blockwise-{1,4,16,64}.html`.
- Machine-readable evidence: `offline-results.json`, `browser-results.json`, and `reference.json`.
