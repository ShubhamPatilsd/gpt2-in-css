# Mixed hot-2 block-gate A/B

Decision against gpt2-mixed-hot2-hierarchical-outer-max16: **retain**.

The B=n/a candidate passed 6/6 paired semantic checks. Its 6-sample warm mean was 2131.8 ms versus 2312.6 ms for the control page, ratio **0.922×** (7.8% faster). Medians were 2211.1 ms versus 2584.4 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 3 rounds over 2 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
