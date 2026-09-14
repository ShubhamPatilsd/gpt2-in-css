# Mixed hot-2 block-gate A/B

Decision against gpt2-mixed-hot2-hierarchical-outer-max16: **reject-transport**.

The B=n/a candidate passed 0/2 paired semantic checks. Its 2-sample warm mean was 3706.6 ms versus 2798.9 ms for the control page, ratio **1.324×** (-32.4% slower). Medians were 3951.6 ms versus 3158.8 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 1 rounds over 2 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
