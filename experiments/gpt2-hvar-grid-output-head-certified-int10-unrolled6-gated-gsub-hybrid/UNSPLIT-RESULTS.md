# Six-stage GSUB hybrid output-head probe

Scaling decision: **reject**; semantic decision: **pass**. Chrome 153.0.8010.36 ran 3 cold rounds and 30 warm fixture comparisons. CSS selected every route and winner; JavaScript only changed fixture inputs and observed layout.

| Metric | GSUB hybrid | Exact baseline |
| --- | ---: | ---: |
| Cold load median | 64051.4 ms | 70313.5 ms |
| Cold load + first evaluation median | 69080.0 ms | 73342.0 ms |
| Warm mutation median | 7643.5 ms | 5545.5 ms |
| Warm composed speedup | **0.73×** | 1.00× |

The hybrid activated 54 fine stages: 3 GSUB accepts and 51 exact fallbacks (94.4%). Active stages had median 2; exact fallbacks per evaluation had median 2.

This is the validated unsplit run after repairing per-stage bank scope and immutable visited-group state. Earlier provisional bug measurements are excluded.

Final winners matched the six-stage exact page in every comparison: true. Fine-stage route/winner checks all passed: true. The distinct-group bank-state guard passed: true. The final partial group 196 was always forced to exact.

The six-bucket GSUB gate remains empirical for this font bank and Chrome build; it is not a portable browser-independent proof.
