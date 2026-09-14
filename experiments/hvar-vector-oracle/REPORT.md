# HVAR vector-primitive upper bound

## Result

This result describes the older projection that repeated sparse `avar2` GELU
inside every output run. It is retained as evidence, but its 5.02x ceiling has
been superseded by the compute-once exact-GELU architecture. The corrected
oracle measures a 26.6x boundary-free ceiling and a 64.2 ms pure projection;
see `../exact-gelu-vector-oracle/REPORT.md`.

With every expensive upstream boundary replaced by exact case-selected CSS
numbers, the unchanged real block-1 `3072 -> 768` HVAR projection still takes a
median **476.6 ms**. The full then-current two-block graph takes **2,392.0 ms** under
the same controlled fresh-graph mutation method. This is a best-case **5.02x**
speedup, not 13x.

All runtime pages are HTML/CSS/fonts only. The oracle vectors were captured
offline from Chrome's actual typed CSS state at the current baseline's
boundaries. Every validated page reproduces all 768 baseline output widths
exactly for all four cases: maximum width error and output RMSE are both zero.

## Controlled timings

Chrome 153.0.8010.36, five runs per topology. Shared browser, HTTP, and font
caches were prewarmed. Every timing uses a fresh page graph, first materializes
case 0, then measures one mutation to a non-default case. A fresh graph avoids
the near-zero shaped-result cache hits seen when a previously rendered case is
revisited in the same page.

| Topology | Real work left | Elements | Median |
|---|---|---:|---:|
| Current baseline | Two full blocks and both transports | 23,528 | 2,392.0 ms |
| Free block-0 output/state boundary | Full block 1 | 6,598 | 1,068.6 ms |
| Free block-1 FC/preactivation boundary | Block 0, block-1 attention, final projection | 18,870 | 1,630.2 ms |
| Both boundaries free | Block-1 attention and final projection | 1,939 | 539.4 ms |
| Everything through block-1 preactivation free | Final projection only | 783 | 476.6 ms |

Observed architectural deltas:

- Removing block 0 plus its state transport: 1,323.4 ms (55.3% of baseline).
- Removing block-1 FC plus its preactivation transport while block 0 remains:
  761.8 ms (31.8%).
- Removing that same FC path after block 0 is already free: 529.2 ms.
- Block-1 attention/LN above the projection-only floor: 62.8 ms in the reduced
  graph.
- Real projection-only floor: 476.6 ms (19.9% of the full baseline).

These differences compare different dependency graphs. They are useful upper
bounds, not additive profiler attribution; layout work changes when graph
topology changes.

## What remains real in the strongest oracle

The projection-only page injects the exact 3,072 normalized FC preactivations
and the exact 768 residual values as ordinary CSS numbers. It leaves the
existing projection shadow tree and fonts unchanged. GELU is still evaluated
inside the projection HVAR path, and the real GPT-2 `3072 -> 768` weight matrix
still produces all 768 outputs. Each output contains 13 projection glyphs, so
Chrome still shapes 9,984 glyphs even though only 783 elements remain.

That 476.6 ms floor exceeded a two-block 13x target of about 184 ms because it
still repeated the nonlinear map 768 times. It should not be interpreted as
the cost of the linear matrix backend. Computing GELU once reduces the same
projection tail to 88.6 ms, of which 64.2 ms is the pure projection.

## Pages

- `oracle-block0-handoff.html`: injects the exact block-0 output state; block 1
  remains live.
- `oracle-b1-fc-preactivation.html`: injects exact block-1 FC preactivations;
  block 0, block-1 attention, and projection remain live.
- `oracle-block0-and-b1-fc.html`: injects both boundaries; block-1 attention and
  projection remain live.
- `oracle-b1-projection-only.html`: injects preactivations and residuals; only
  GELU plus the real projection remains.

## Reproduction

```sh
node tools/capture_hvar_vector_oracle.mjs
PYTHONPATH=tools uv run --with fonttools --with numpy --with pillow --with brotli \
  python tools/build_hvar_vector_oracle.py
HVAR_ORACLE_ROUNDS=5 node tools/benchmark_hvar_vector_oracle.mjs
```

Raw measurements are in `benchmark-results.json`; captured boundary values are
in `captured-boundaries.json`.
