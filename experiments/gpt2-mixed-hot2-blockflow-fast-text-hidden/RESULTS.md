# Hidden fast-text score rows

Decision: **reject**.

Applying `visibility:hidden`, disabled kerning/ligatures/optical sizing and
`text-rendering:optimizeSpeed` to every block-flow score candidate preserves
2/2 exact routes and winners. It regresses narrow mean from 2,472.1 to
2,621.6 ms (1.060x) and median from 2,597.5 to 2,922.7 ms (1.125x), so it does
not receive a broad run. Raw data: `ab-narrow-vs-blockflow.json`.

