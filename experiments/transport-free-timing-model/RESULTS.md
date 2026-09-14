# Transport-free timing model

## Verdict

Removing vector handoffs and their connected-graph invalidation is necessary,
but it is not sufficient.  In the matched context-16 measurements it can
remove at most 241.9 ms from a 1,017.7 ms block update: a **1.31x** speedup.
The separately working attention and MLP stages still consume 775.7 ms per
block.  Repeating only that isolated work over 12 blocks gives **9.31 s before
the final LayerNorm and vocabulary head**.

This is the strongest comparison available in the saved artifacts because the
attention mutation and MLP replay change the same roughly 605-coordinate live
residual vector.  It avoids the earlier mistake of comparing a one-coordinate
MLP mutation with a full attention update.

## Definition of “transport free”

The primary model removes the measured premium caused by connecting two
otherwise working dependency graphs:

```text
transport-free block = isolated attention median + isolated full-vector MLP median
connection tax       = connected block median - transport-free block
```

It does not pretend that existing artifacts can measure a fictional browser in
which every internal width, packet, and font output costs zero.  Font shaping
is both the matrix calculation and the act of exposing its result, so current
traces cannot cleanly separate all local transport from arithmetic.  The
numbers below are therefore an **empirical floor for the current stage
implementations**, not a mathematical lower bound on a future fused backend.

## Matched multi-token results

All values are warm mutation medians in Chrome 153.  Runtime pages contain no
JavaScript; the external harness only mutates inputs and forces the dependent
result.

| Context | Attention | Full-vector MLP | Isolated sum/block | Connected block | Removable premium | Max speedup | 12-block sum |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 16 | 474.9 ms | 300.9 ms | **775.7 ms** | 1,017.7 ms | 241.9 ms (23.8%) | **1.31x** | **9.309 s** |
| 32 | 533.4 ms | 330.1 ms | **863.4 ms** | 1,070.8 ms | 207.4 ms (19.4%) | **1.24x** | **10.361 s** |

Even summing the fastest individual samples rather than medians leaves 8.339 s
at context 16 and 9.582 s at context 32 for 12 blocks.  These totals exclude
the final LayerNorm, vocabulary scoring, winner selection, and token feedback.

The accurate staged output head separately measures 1.031 s, making the
stage-isolated estimates 10.340 s at context 16 and 11.393 s at context 32.
The faster global-int11 coarse head measures 527.7 ms, but retained only 63 of
64 screened winners, so it is not the accurate end state.

## Context-16 attention decomposition

The isolated stage-demand fixtures measure:

| Demand | Median |
| --- | ---: |
| live 768 -> 2,304 QKV | 138.1 ms |
| score/softmax/value work and internal carriers, by subtraction | 202.9 ms |
| 768 -> 768 attention output projection | 133.9 ms |
| complete attention | 474.9 ms |

The 202.9 ms value is diagnostic rather than an independently timed stage: it
is the complete attention median minus the separately measured QKV and output
projection medians.  It must not be treated as a precise exclusive profile.

Relative to the requested 13x direction, the context-16 connected block would
need to fall to 78.3 ms.  Removing its entire connection premium still leaves
775.7 ms, **9.91x above that target**.  Transport elimination alone therefore
cannot supply the 13x gain.

## One-token evidence and the absolute trace floor

Older exact fixtures measured block 0 at 363.4 ms and block 1 at 383.4 ms in
isolation.  Their average extrapolates to 4.481 s for 12 blocks.  The best
geometry-normalized block-0 fixture measures 231.1 ms, which would extrapolate
to 2.773 s if every later block behaved identically.

Those are optimistic proxies, not the main model.  With one token, attention
degenerates to selecting V; the result does not pay realistic multi-token
Q/K/softmax costs.  The 231.1 ms implementation was also measured only on block
0.

A current optimized two-block trace reports 206.9 ms inside font shaping.  If
layout, style calculation, timelines, nonlinear CSS work, and every handoff
were all assigned zero cost, simply scaling the observed shaping work gives a
maximally optimistic **1.241 s for 12 one-token blocks**.  This is not a latency
prediction, but it shows that the font calculations themselves are already
material even under an unrealistically generous transport counterfactual.

## Conclusion

There are two distinct problems:

1. Cross-stage transport/invalidation adds about 19-24% to a live block and
   becomes superlinear when more stages share one document.  Fixing it is still
   required for scaling.
2. Isolated attention and MLP computation is itself far too slow.  After the
   connection tax is set to zero, the measured stages remain roughly ten times
   above a 13x per-block target.

The next architecture therefore must both keep vectors inside one backend
across boundaries **and** reduce the stage-local font/layout work.  A transport
primitive by itself only removes the first problem.

Reproduce the arithmetic with:

```sh
python3 tools/analyze_transport_free_timing.py
```

The script reads the saved JSON artifacts directly and emits the complete
machine-readable model to stdout.
