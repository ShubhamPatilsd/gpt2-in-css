# Mixed hot-2 block-gate A/B

Decision against gpt2-mixed-hot2-direct-outer-max-pruned: **reject-scaling**.

The B=n/a candidate passed 30/30 paired semantic checks. Its 30-sample warm mean was 3241.8 ms versus 3152.6 ms for the control page, ratio **1.028×** (-2.8% slower). Medians were 2971.8 ms versus 3090.5 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 3 rounds over 10 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
