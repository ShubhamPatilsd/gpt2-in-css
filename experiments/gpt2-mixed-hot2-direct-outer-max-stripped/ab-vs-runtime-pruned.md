# Mixed hot-2 block-gate A/B

Decision against gpt2-mixed-hot2-direct-outer-max-pruned: **reject-scaling**.

The B=n/a candidate passed 6/6 paired semantic checks. Its 6-sample warm mean was 2122.3 ms versus 2064.4 ms for the control page, ratio **1.028×** (-2.8% slower). Medians were 2367.7 ms versus 1848.3 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 3 rounds over 2 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
