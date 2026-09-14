# Four-shard 192-axis coarse carrier

Decision: **reject; close the shard-width sweep**.

This intermediate point tests whether four 192-axis glyphs per ordinary token
offer a better cold/warm tradeoff than the retained three 256-axis carrier.
Both narrow paired fixtures pass the complete route, bucket, and dense-winner
contract.

| Metric | 4x192 candidate | 3x256 control | Ratio |
|---|---:|---:|---:|
| Mean | 2,444.5 ms | 2,118.9 ms | **1.154x** |
| Median | 2,563.4 ms | 2,471.4 ms | **1.037x** |
| Cold load | 51,491.0 ms | 64,974.9 ms | 0.792x |

The cold numbers are single, candidate-first observations and therefore only
directional. The warm screen is sufficient to reject the candidate: restoring
one coarse glyph per 49,745 ordinary rows regresses mean 15.4%. No broad run
is warranted. Keep three 256-axis shards for loaded inference and the older
five 160-axis page as the already measured cold-start profile; do not continue
interpolating shard widths.

Raw observations are in `ab-narrow-vs-shard256.json`. Chrome:
153.0.8010.36.
