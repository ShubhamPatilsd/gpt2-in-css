# Production batch-17 exact tail

## Decision

**Reject for latency.** The page is semantically valid but scales worse than
the production serial-23 cascade. GPT-2-small architecture and checkpoint are
unchanged, and the page reuses the existing production q10/q16 font banks.

After six serial stages, the candidate selects the next 17 unique groups with
masked upper routers and scores their 4,352 rows in one exact wave. This cuts
the worst abstract dependency chain from 46 to 30 levels, but any of the 63
corpus states that miss the prefix evaluates all 17 tail groups. The resulting
corpus work estimate rises from 2.402 to 3.169 groups on average.

Chrome 153 passes 6/6 difficulty-selected fixtures: prefix and batch routes,
17-way uniqueness, independent exact shadows, incumbent merge, calibrated
49-bucket stop, and final token all match. The runtime page has no JavaScript
and loads with JavaScript disabled.

Four paired mutations are decisive:

| Fixture | Batch-17 | Serial-23 |
|---|---:|---:|
| Worst 23-group state | 26.76 s | 21.01 s |
| Mid tail | 23.17 s | 14.65 s |
| Seven-group state | 24.95 s | 8.79 s |
| One-group state | 3.84 s | 2.63 s |

Batch-17 mean is 19.68 s versus 11.77 s serial (1.672x); median is
24.95 s versus 14.65 s (1.703x). Parallel exact shaping fanout dominates the
shorter dependency chain even on the hardest state. Do not build the proposed
multi-wave tail until a wave can share or reduce exact row shaping; smaller
batches have already shown the same direction in earlier probes.

Nothing was committed or pushed.
