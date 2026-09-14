# G128 tie-spacing transport sweep

## Decision

Reject G128 transport. None of the exact stride variants passed the isolated two-fixture live-shadow gate, so no full-10 run was performed. G512 and G1024 were not tested in this sweep because their minimum tie spacing is no better than the already-falsified transport.

Every run used one fresh browser, one fresh candidate page, and one fresh retained G256 K2 page. Load order alternated candidate-first, control-first, candidate-first. There was one round, no robust repeat, and no fixture-specific correction.

| Variant | Tie step | Layout units / token | Live semantics | Candidate mean ms | Fresh G256 mean ms | Warm ratio | Timing decision |
|---|---:|---:|---:|---:|---:|---:|---|
| g128-s8 | 1/16px | 4 | FAIL | 3,490.8 | 3,915.8 | 0.891 | discard |
| g128-s16 | 1/8px | 8 | FAIL | 2,531.4 | 2,575.4 | 0.983 | discard |
| g128-s32 | 1/4px | 16 | FAIL | 3,339.0 | 3,740.0 | 0.893 | discard |

The ratios are not scaling evidence because every candidate failed semantics. Candidate work was 128 dynamic rows versus 256 for retained G256 on these fixtures.

## Falsification detail

All score buckets matched the forced exact shadows. The remaining failure is the local-ID payload after the mixed anchor/container handoff:

| Variant | Fixture 0 final | Fixture 1 final | Representative mixed local vs shadow |
|---|---:|---:|---|
| g128-s8 | 10 vs dense 11 | 479 vs dense 477 | group 0: 10 vs 11; group 3: 95 vs 93 |
| g128-s16 | 11 (correct) | 479 vs dense 477 | group 3: 95 vs 93; later group 0: 7 vs 11 |
| g128-s32 | 11 (correct) | 475 vs dense 477 | group 3: 91 vs 93 |

Increasing tie spacing from 1/16px through 1/4px does not make the handoff semantically stable. The error is therefore not resolved by allocating more fractional width, and no per-fixture offset was fitted.

Full observations are preserved in `browser-results-g128-s8-failure.json`, `browser-results-g128-s16-failure.json`, and `browser-results-g128-s32-failure.json`. Earlier G128 transport failures remain preserved separately.

## Offline contract

The original four offline variant objects are unchanged. The appended transport sweep inherits G128-s4 retention, routes, work, and weighted proxy, changing only geometry. Bucket semantics remain 1/256 logit; the 24-bucket allowance becomes 192/384/768px and the 48-bucket stop span becomes 384/768/1,536px for s8/s16/s32 respectively. All three artifacts fit the configured Chromium geometry limits.
