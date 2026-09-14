# All-block-flow maxima

Decision: **reject**.

This probe keeps the retained block-flow vocabulary groups and also changes
each conditionally active 256-row exact fine-stage reducer from Grid to block
flow. It passes 2/2 route, bucket, and winner checks, but the narrow mean is
2,421.8 ms versus 2,315.6 ms for group-only block flow (1.046x). The median is
0.943x in this two-sample screen, but fixture 1—the case that actually demands
a non-hot fine stage—regresses from 1,879.6 to 2,248.9 ms.

Block flow is retained for the always-on vocabulary groups; Grid remains the
better selectively active exact-stage reducer. Raw data:
`ab-narrow-vs-group-blockflow.json`.

