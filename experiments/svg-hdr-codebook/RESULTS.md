# 12-bit PQ codebook calibration

The raw 4,096-code PQ ramp is first rendered normally. Each 64-code row is
then amplified independently by a linear SVG color matrix, allowing an 8-bit
screenshot to recover distinctions that are smaller than one final display
step.

Default sRGB Chrome exposes 2,069 recovered levels across the complete ramp.
The monotonic interval used by the matvec probe contains 1,125 codes and about
970 recovered levels between filter-linear values 0.05 and 0.95.

This proves the AVIF decoder and some HDR-derived filter surfaces carry more
than eight bits. It does not prove computed SVG results do; the real matvec
comparison in `../svg-hdr-matvec/RESULTS.md` is the deciding test.
