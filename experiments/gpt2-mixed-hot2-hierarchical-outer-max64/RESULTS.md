# Hierarchical outer maximum, fan-in 64

Decision: **retain only as a tail-latency profile**.

The four chunk nodes pass 30/30 exact checks against fan-in 16. Mean and median
regress 1.9% and 5.3%, while p90 improves 14.6% and maximum 16.6%. Fan-in 16 is
the balanced winner. Raw results are in `ab-broad-vs-max16.json`.
