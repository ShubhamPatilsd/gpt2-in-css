# Mixed hot-2 block-gate A/B

Decision against gpt2-mixed-hot2-direct-outer-max: **reject-scaling**.

The B=4 candidate passed 6/6 paired semantic checks. Its 6-sample warm mean was 2421.5 ms versus 2229.9 ms for the control page, ratio **1.086×** (-8.6% slower). Medians were 2722.9 ms versus 1942.4 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 3 rounds over 2 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
