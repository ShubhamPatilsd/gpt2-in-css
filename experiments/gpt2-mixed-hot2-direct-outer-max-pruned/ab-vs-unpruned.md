# Mixed hot-2 block-gate A/B

Decision against gpt2-mixed-hot2-direct-outer-max: **reject-scaling**.

The B=n/a candidate passed 30/30 paired semantic checks. Its 30-sample warm mean was 3140.2 ms versus 3130.6 ms for the control page, ratio **1.003×** (-0.3% slower). Medians were 3182.1 ms versus 3225.3 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 3 rounds over 10 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
