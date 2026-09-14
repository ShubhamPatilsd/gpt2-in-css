# Six-stage GSUB hybrid output-head probe

Scaling decision: **reject**; semantic decision: **pass**. Chrome 153.0.8010.36 ran one cold round and 10 warm fixture comparisons. CSS selected every route and winner; JavaScript only changed fixture inputs and observed layout.

| Metric | GSUB hybrid | Exact baseline |
| --- | ---: | ---: |
| Cold load median | 70397.8 ms | 59222.6 ms |
| Cold load + first evaluation median | 75181.6 ms | 62470.7 ms |
| Warm mutation median | 7143.6 ms | 5990.9 ms |
| Warm composed speedup | **0.84×** | 1.00× |

The split-aware hybrid activated 18 fine stages: 17 GSUB accepts and one exact fallback (5.6%). Active stages had median 2; exact fallbacks per evaluation had median 0. The route mix therefore flipped from the unsplit probe's 94.4% fallback rate to 5.6%, but warm latency was still 19.2% higher than exact. The conditional robust repeat was not run because the one-round head did not beat the baseline.

Each stage conditionally displays the split-complement top/runner grids for groups 0/1 or the full-bank grids for groups 2..196. The mutually exclusive grids feed shared winner anchors and one exact fallback grid. Group 0/1 accepts require margin >4, full-bank accepts require margin >6, and partial group 196 is always exact. Fonts are referenced from the existing banks by relative URL; none were copied or rebuilt.

Final winners matched the six-stage exact page in every comparison: true. Fine-stage route/winner checks all passed: true. The distinct-group bank-state guard passed: true. The final partial group 196 was always forced to exact.

The earlier stage-scope and router-revisit diagnostics were provisional integration bugs and are excluded from these results. The validated unsplit three-round result is preserved in `UNSPLIT-RESULTS.md` and `unsplit-browser-results.json`.

Both margin gates remain empirical for these font banks and Chrome build; they are not portable browser-independent proofs.
