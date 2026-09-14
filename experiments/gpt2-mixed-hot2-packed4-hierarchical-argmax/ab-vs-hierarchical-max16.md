# Mixed hot-2 block-gate A/B

Decision against gpt2-mixed-hot2-hierarchical-outer-max16: **reject-transport**.

The B=n/a candidate passed 0/6 paired semantic checks. Its 6-sample warm mean was 2921.2 ms versus 1876.0 ms for the control page, ratio **1.557×** (-55.7% slower). Medians were 3143.6 ms versus 2045.4 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 3 rounds over 2 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
