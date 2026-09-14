# Aligned int10 + exact residual group probe

Decision: **reject-live-addition**.

For fixed group 0 (tokens 0–255), the browser reused a separately shaped and snapped aligned-int10 coarse width, added a live three-glyph/256-axis residual, rounded the result to the production 1/256-logit bucket, and compared it with the existing twelve-glyph global-int16 shadow.

- Exact live candidate bucket mismatches: **2397/2560**. See `exactLiveMismatches` in `browser-results.json` for each fixture/token and both realized widths.
- Group winner mismatches: **0/10**; winner-bucket mismatches: **10/10**.
- Lower-token tie checks: the aligned path passed all **355** equal-bucket adjacent pairs with zero remainder/order violations. The live control had 77 zero-width clamped candidates and 67 resulting equal-zero order violations; all are preserved in the raw report.
- Decomposition: exact for every coefficient; m=13–65, residual=-32–32.

| Warm grid metric (50 samples each) | Paid coarse + 3 residual glyphs | 12-glyph global-int16 |
| --- | ---: | ---: |
| mean | 13.254 ms | 10.558 ms |
| median | 13.421 ms | 7.919 ms |
| p90 | 14.337 ms | 24.441 ms |

Mean ratio: **1.255x** (25.5% slower). The timing excludes the coarse cache, which represents work already paid by the certified int10 head; it includes showing, shaping, adding, rounding, and reading all 256 residual candidates. Chrome 153.0.8010.36; cold side-by-side load 2402.0 ms.

Raw per-fixture semantics, any exact live mismatches, timing samples, request failures, and page errors are in `browser-results.json`. NumPy buckets in `reference.json` are diagnostic only and are not pass/fail gates.
