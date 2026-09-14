# Block-flow group maximum

Decision: **retain as the cold-start block-flow profile; superseded for loaded throughput**.

Each vocabulary group previously used a one-column Grid with all 256 score
rows placed in the same cell. This variant keeps the score arithmetic,
fan-in-16 outer router, exact-stage cascade, and tie encoding unchanged, but
turns each group into ordinary in-flow block children with zero block-size.
The block container's max-content inline size remains the maximum child width,
so it exports the same group score without Grid track sizing.

Against the retained fan-in-16 page, the broad alternating run passes 30/30
route, bucket, and dense-winner checks.

| Metric | Block flow | Fan-in 16 Grid | Ratio |
|---|---:|---:|---:|
| Mean | 3,057.2 ms | 3,318.8 ms | **0.921x** |
| Median | 3,020.7 ms | 3,221.3 ms | **0.938x** |
| p90 | 4,299.3 ms | 4,680.2 ms | **0.919x** |
| Maximum | 4,591.1 ms | 5,031.3 ms | **0.913x** |
| Cold load | 50,427 ms | 62,513 ms | 0.807x |

The paired cold number is favorable but remains a single order-sensitive
observation. The warm distribution is the retention gate: mean improves 7.9%,
median 6.2%, p90 8.1%, and maximum 8.7%.

## Browser trace

A fixture-1 mutation was traced separately on each loaded page. The trace is a
mechanism diagnostic, not a paired benchmark:

| Complete event | Block flow | Fan-in 16 Grid | Change |
|---|---:|---:|---:|
| Wall time | 2,594.0 ms | 3,009.1 ms | -13.8% |
| Layout | 1,404.7 ms | 1,619.6 ms | -13.3% |
| Style recalculation | 432.9 ms | 620.4 ms | -30.2% |
| Text shaping | 667.1 ms / 50,522 calls | 650.1 ms / 50,523 calls | unchanged work |
| Compositing inputs | 697.7 ms | 688.3 ms | unchanged |

The improvement therefore comes from replacing Grid style/track work, not
from suppressing score rows. The remaining first-order scaling term is still
one shaped run per vocabulary token.

Adding `visibility:hidden` plus fast-text shaping hints to every candidate is
not additive. It passes 2/2 exact checks but regresses narrow mean 6.0% and
median 12.5%, so it does not receive a broad run.

Two broader applications of the simplification are also negative in narrow
screens. Block flow for the conditionally active exact fine stage regresses
mean 4.6%, and removing the now-timeline-free scroll wrapper around the score
bank regresses mean 10.4%. The first result says Grid remains useful for small
selective reducers; the second says the scroll wrapper is still a favorable
layout boundary even when its timeline is dead. See
`../gpt2-mixed-hot2-all-blockflow/RESULTS.md` and
`../gpt2-mixed-hot2-blockflow-scrollless/RESULTS.md`.

Chrome: 153.0.8010.36. Raw results are in
`ab-broad-vs-hierarchical-max16.json`; trace summaries are in
`output-head-trace.json` and the fan-in-16 experiment's trace files.

## 256-axis coarse-shard successor

Replacing each ordinary row's five 160-axis int10 glyphs with three 256-axis
glyphs passes another 30/30 end-to-end screen. It improves loaded mean 2.0%,
median 1.7%, and p90 11.9%; text-shaping time falls from 667.1 to 468.0 ms in
the fixture-1 trace. Its paired cold load is 11.1% worse, so keep this page for
cold startup and use the successor for loaded recurrent inference. See
`../gpt2-mixed-hot2-blockflow-group-max-shard256/RESULTS.md`.
