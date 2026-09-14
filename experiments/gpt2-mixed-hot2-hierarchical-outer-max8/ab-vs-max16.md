# Mixed hot-2 block-gate A/B

Decision against gpt2-mixed-hot2-hierarchical-outer-max16: **reject-scaling**.

The B=n/a candidate passed 6/6 paired semantic checks. Its 6-sample warm mean was 2030.8 ms versus 1964.2 ms for the control page, ratio **1.034×** (-3.4% slower). Medians were 2261.0 ms versus 1900.0 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 3 rounds over 2 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
