# Mixed hot-2 block-gate A/B

Decision against the retained mixed-hot2 page: **reject-scaling**.

The B=4 candidate passed 6/6 paired semantic checks. Its 6-sample warm mean was 2976.2 ms versus 2848.8 ms for the retained page, ratio **1.045×** (-4.5% slower). Medians were 3197.5 ms versus 2937.2 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 3 rounds over 2 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
