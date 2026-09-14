# Direct outer maximum with dead timeline CSS stripped

Decision: **reject; keep the runtime-pruned cold-start profile**.

The runtime-pruned direct-max page no longer references the original outer
group timelines, but it still downloads and parses their generated rules. This
variant physically removes all 197 `@property`/keyframe pairs, 197 proxy rules,
the shared proxy rule and timeline scope, plus 197 inline `view-timeline`
declarations. The inherited base stylesheet falls from 224,096 to 171,417
bytes; score rows and every live decoder remain unchanged.

A narrow alternating screen against runtime-pruned direct-max passes all 6/6
route, bucket, final-token, and dense-oracle checks.

| Metric | Stripped | Runtime-pruned | Ratio |
|---|---:|---:|---:|
| Mean, 6 samples | 2,122.3 ms | 2,064.4 ms | 1.028x |
| Median | 2,367.7 ms | 1,848.3 ms | 1.281x |
| p90 | 3,020.7 ms | 3,040.4 ms | 0.994x |
| Cold load | 50,729 ms | 51,166 ms | 0.991x |

The only intended benefit—cold load—is below 1% in this paired run, while warm
mean regresses 2.8%. The removed CSS is only about 53 KB beside an 8.23 MB HTML
document and 712 KB topology stylesheet, so a broad warm run is not justified.
Keep physical rule stripping as source hygiene only, not a latency strategy.

Chrome: 153.0.8010.36. Raw results are in `ab-vs-runtime-pruned.json`.
