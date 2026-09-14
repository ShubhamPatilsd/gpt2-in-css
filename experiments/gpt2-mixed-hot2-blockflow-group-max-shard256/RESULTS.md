# Mixed hot-2 block-flow head with 256-axis coarse shards

Decision: **retain as the balanced loaded-throughput and tail winner**.

This page composes the retained mixed hot-2 exact head, block-flow vocabulary
group reducers, and fan-in-16 outer maximum with a three-face 256-axis int10
coarse carrier. Non-hot rows fall from five glyphs to three; the 512 exact hot
rows intentionally retain their twelve-glyph exact representation.

Every route, bucket, and final winner passes the broad paired screen: 30/30
checks across ten fixtures and three alternating rounds.

| Metric | 3x256 candidate | 5x160 block-flow | Ratio |
|---|---:|---:|---:|
| Mean | 2,741.0 ms | 2,795.5 ms | **0.980x** |
| Median | 2,709.1 ms | 2,756.2 ms | **0.983x** |
| p90 | 3,810.3 ms | 4,325.3 ms | **0.881x** |
| Maximum | 4,379.5 ms | 4,395.6 ms | 0.996x |
| Cold load | 56,693.5 ms | 51,027.3 ms | 1.111x |

The candidate improves loaded mean by 2.0%, median by 1.7%, and p90 by 11.9%.
Its single paired cold observation is 11.1% worse, so the older five-shard
block-flow page remains the cold-start profile.

## Browser trace

A separate loaded fixture-1 trace isolates the mechanism. Event count stays at
roughly one shaped text run per vocabulary token, but each ordinary coarse run
contains three glyphs instead of five.

| Complete event | 3x256 candidate | 5x160 control | Change |
|---|---:|---:|---:|
| Wall time | 2,146.6 ms | 2,594.0 ms | -17.2% |
| Layout | 1,214.1 ms | 1,404.7 ms | -13.6% |
| Style recalculation | 366.9 ms | 432.9 ms | -15.2% |
| Text shaping | 468.0 ms / 50,521 calls | 667.1 ms / 50,522 calls | -29.8% time |
| Compositing inputs | 480.2 ms | 697.7 ms | -31.2% |
| Pre-paint | 516.1 ms | 735.1 ms | -29.8% |

The result confirms that glyph multiplicity remains observable even when text
run count is fixed. It does not remove the first-order 50,257-row scan, but it
is the best measured exact loaded profile so far.

Raw paired results are in `ab-broad-vs-shard160-blockflow.json`; trace events
are summarized in `output-head-trace.json`. Chrome: 153.0.8010.36.

## Intermediate-width falsification

A four-glyph 192-axis candidate passes 2/2 narrow checks but is 1.154x by mean
and 1.037x by median against this page. Its candidate-first cold load is lower,
but a separate five-shard profile already serves startup. Close the shard-width
sweep rather than optimizing between constant-factor points; see
`../gpt2-mixed-hot2-blockflow-group-max-shard192/RESULTS.md`.
