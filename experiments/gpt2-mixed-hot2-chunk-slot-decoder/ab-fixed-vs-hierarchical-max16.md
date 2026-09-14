# Mixed hot-2 block-gate A/B

Decision against gpt2-mixed-hot2-hierarchical-outer-max16: **reject-transport**.

The B=n/a candidate passed 0/2 paired semantic checks. Its 2-sample warm mean was 3714.3 ms versus 2936.2 ms for the control page, ratio **1.265×** (-26.5% slower). Medians were 4057.9 ms versus 2977.2 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 1 rounds over 2 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
