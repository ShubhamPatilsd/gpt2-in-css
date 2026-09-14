# Co-activation-partitioned hot-2 B=4 gate

Decision: **reject; keep the direct-max full hot grids**.

Fixed quartets were optimized on the first 512 corpus states to group tokens
whose conservative gates activate together. The untouched 512-state holdout
improves over contiguous quartets from 45.28 to 34.34 shaped rows for group 0
and from 99.77 to 59.09 for group 1. Certified-fixture totals fall from 78.0
to 39.2 rows. Gate count, fonts, score rows, and the direct outer maximum are
unchanged.

The browser screen passes 6/6 exact route/bucket/token checks against the
direct-max full-grid winner, but loses scaling:

| Metric | Clustered B=4 | Direct-max full grid | Ratio |
|---|---:|---:|---:|
| Mean, 6 samples | 2,421.5 ms | 2,229.9 ms | 1.086x |
| Median | 2,722.9 ms | 1,942.4 ms | 1.402x |

Even removing roughly half the fixture hot-row shapes cannot repay the 128
container gates, interval reductions, and conditional block graph. This
confirms that shaping is no longer the dominant hot-path cost after direct
maximum extraction. Raw results are in `ab-vs-direct-max.json`.
