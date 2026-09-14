# Mixed hot-2 block-gate A/B

Decision against the retained mixed-hot2 page: **reject-scaling**.

The B=8 candidate passed 2/2 paired semantic checks. Its 2-sample warm mean was 3911.1 ms versus 2970.3 ms for the retained page, ratio **1.317×** (-31.7% slower). Medians were 3949.4 ms versus 3933.7 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 1 rounds over 2 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
