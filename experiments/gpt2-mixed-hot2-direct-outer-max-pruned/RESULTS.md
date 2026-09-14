# Direct outer maximum with timeline graph pruned

Decision: **retain as the cold-start profile; warm path is neutral**.

After direct maximum extraction, the original 197 group-proxy elements and
their scoped view timelines are unreferenced. This variant removes those proxy
elements and disables `view-timeline`/`timeline-scope`; score rows and every
live decoder remain unchanged.

The broad paired screen against unpruned direct-max passes 30/30 exact checks.

| Metric | Pruned | Unpruned | Ratio |
|---|---:|---:|---:|
| Mean, 30 samples | 3,140.2 ms | 3,130.6 ms | 1.003x |
| Median | 3,182.1 ms | 3,225.3 ms | 0.987x |
| p90 | 4,202.1 ms | 4,540.0 ms | 0.926x |
| Maximum | 4,474.0 ms | 5,054.8 ms | 0.885x |
| Cold load | 32,776 ms | 50,509 ms | **0.649x** |

Warm mean is statistically neutral, while median and tail improve modestly.
Cold load improves 35.1%, despite the inherited base stylesheet still
containing the now-dead timeline rules. Keep this artifact when startup matters;
the unpruned direct-max result remains the conservative warm-throughput winner.

This flat form is subsequently superseded on the warm path by a two-level
fan-in-16 maximum: 30/30 exact checks with 2.5% lower mean, 1.0% lower median,
10.6% lower p90, and 12.5% lower maximum. This artifact remains the flat and
cold-start baseline. See `../gpt2-mixed-hot2-hierarchical-outer-max16/RESULTS.md`.

Physically deleting those rules was also screened. It removes about 53 KB and
passes 6/6 exact checks, but changes cold load by less than 1% and regresses
warm mean 2.8%. Runtime graph pruning, not stylesheet byte removal, produced
the cold-start gain. See `../gpt2-mixed-hot2-direct-outer-max-stripped/RESULTS.md`.

Chrome: 153.0.8010.36. Raw results are in `ab-vs-unpruned.json`.
