# Mixed hot-2 block-gate A/B

Decision against gpt2-mixed-hot2-direct-outer-max-pruned: **retain**.

The B=n/a candidate passed 6/6 paired semantic checks. Its 6-sample warm mean was 1833.7 ms versus 2022.1 ms for the control page, ratio **0.907×** (9.3% faster). Medians were 2204.3 ms versus 2308.2 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 3 rounds over 2 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
