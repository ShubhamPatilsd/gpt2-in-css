# Mixed hot-2 block-gate A/B

Decision against gpt2-mixed-hot2-hierarchical-outer-max16: **retain**.

The B=n/a candidate passed 30/30 paired semantic checks. Its 30-sample warm mean was 3096.0 ms versus 3247.1 ms for the control page, ratio **0.953×** (4.7% faster). Medians were 3182.1 ms versus 3113.4 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 3 rounds over 10 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
