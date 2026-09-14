# Mixed hot-2 block-gate A/B

Decision against gpt2-mixed-hot2-blockflow-group-max-shard256: **reject-scaling**.

The B=n/a candidate passed 2/2 paired semantic checks. Its 2-sample warm mean was 2444.5 ms versus 2118.9 ms for the control page, ratio **1.154×** (-15.4% slower). Medians were 2563.4 ms versus 2471.4 ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for 1 rounds over 2 fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: 153.0.8010.36.
