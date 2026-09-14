# Mixed hot-2 block-gate A/B

Decision against gpt2-mixed-hot2-hierarchical-outer-max16: **reject-scaling**.

The B=n/a candidate passed 2/2 paired semantic checks. Its 2-sample warm mean was 2869.6 ms versus 2831.6 ms for the control page, ratio **1.013×** (-1.3% slower). Medians were 3079.2 ms versus 3196.0 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 1 rounds over 2 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
