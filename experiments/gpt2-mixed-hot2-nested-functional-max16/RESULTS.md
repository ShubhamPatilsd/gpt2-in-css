# Nested functional maximum, fan-in 16

Decision: **reject; keep the materialized fan-in-16 tree**.

This variant nests thirteen `max()` functions of at most sixteen anchor terms
inside the original single width property. It adds no elements, anchors, or
readback levels.

The broad comparison against materialized fan-in-16 passes 30/30 exact checks.

| Metric | Nested function | Materialized tree | Ratio |
|---|---:|---:|---:|
| Mean | 3,268.7 ms | 3,134.6 ms | 1.043x |
| Median | 3,278.8 ms | 3,092.9 ms | 1.060x |
| p90 | 4,244.8 ms | 4,446.9 ms | 0.955x |
| Maximum | 4,597.6 ms | 4,856.5 ms | 0.947x |

The six-sample screen initially suggested a mean/median win, but the broad run
reverses it. Functional nesting improves tail modestly while regressing mean
4.3% and median 6.0%; Blink does not provide the balanced benefit seen with
materialized intermediate anchors.

Raw results are in `ab-broad-vs-materialized-max16.json`.
