# Hot-2 root-precomputed exact six-stage result

Decision: **reject-scaling**.

The full 10-fixture semantic screen passed **10/10 checks**. Every active stage matched the live exact baseline for selected group, fine winner and bucket, merged winner and bucket, certificate gap, stopping, and dynamic-grid visibility. Fixture 4 exercised active group **1 then 0**; fixture 1 exercised active non-hot dynamic group **5**. JavaScript only mutated fixture inputs and observed layout.

## Coverage

- Active serial stages: 18.
- Hot-cache hits: 17.
- Non-hot dynamic exact stages: 1.
- Fixture 4 active group 1 then 0: true.
- Fixture 1 active dynamic group 5: true.
- Fixed speculative work per mutation: 512 hot rows.

## Scaling decision

The clean fixture-0 diagnostic measured **932.1 ms** for root precompute versus **519.7 ms** exact, a **1.79x slowdown**. The completed full timing pass was potentially contaminated by a brief overlapping Chrome test and then failed in report post-processing, so it is not reported or repeated. The clean loss is already decisive: eagerly evaluating both hot grids does not repay shared-anchor reuse.

Generated HTML: 8,300,395 bytes; topology CSS: 703,990 bytes. Reused 79,431,996 bytes across 12 existing WOFF2 files; no fonts copied or rebuilt.

Chrome: 153.0.8010.36. Full semantic observations are in `browser-results.json`.
