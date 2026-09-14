# Scrollless block-flow score bank

Decision: **reject**.

The direct anchor router no longer reads the original view timelines, so this
probe collapses their 262,144 px scroll wrapper to zero size and visible
overflow while preserving its query-norm inheritance. It passes 2/2 exact
checks, but narrow mean regresses from 2,314.8 to 2,554.6 ms (1.104x). Fixture
1 regresses from 1,705.0 to 2,257.7 ms.

The wrapper still gives Blink a favorable layout boundary even with timelines
disabled. Keep it around the block-flow row bank. Raw data:
`ab-narrow-vs-blockflow.json`.

