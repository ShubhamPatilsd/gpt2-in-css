# Mixed hot-2 block-gate A/B

Decision against gpt2-mixed-hot2-hierarchical-outer-max16: **reject-scaling**.

The B=n/a candidate passed 30/30 paired semantic checks. Its 30-sample warm mean was 2969.6 ms versus 2913.4 ms for the control page, ratio **1.019×** (-1.9% slower). Medians were 3052.3 ms versus 2897.8 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 3 rounds over 10 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
