# Mixed hot-2 block gate, B=4

Decision against the retained mixed-hot2 page: **reject-scaling**.

The transport is exact on the route-diverse browser falsification. It passes
2/2 live exact-shadow checks against the older six-stage int10 control, and the
corrected direct A/B passes 6/6 route, bucket, winner, and dense-oracle checks.
On fixture 1 it safely certifies after groups 5/1 while the retained browser
page conservatively visits group 0 as a third stage; both return token 477 at
bucket 12,620.

The direct comparison does not improve the current winner. Across three rounds
of two distinct-input mutations, B=4 takes **2,976.2 ms mean / 3,197.5 ms
median** versus **2,848.8 / 2,937.2 ms** for retained mixed-hot2: **1.045x by
mean (4.5% slower)** and **1.089x by median**. The candidate wins three of six
individual noisy pairs but loses both aggregate criteria.

This page restores 512 five-glyph int10 center rows for hot groups 0/1 and adds
512 conditionally hidden twelve-glyph exact rows in 64 blocks per group. The
isolated block gate is fast, but paying for those extra centers and their bound
graph erases the shaping reduction in the full 50,257-row route.

Chrome 153.0.8010.36. Raw direct comparison: `ab-results.json`; concise paired
summary: `AB_RESULTS.md`; older-control semantic screen: `browser-results.json`.
