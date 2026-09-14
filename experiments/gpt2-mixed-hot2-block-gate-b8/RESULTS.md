# Mixed hot-2 block gate, B=8

Decision against the retained mixed-hot2 page: **reject-scaling**.

The two route-diverse browser cases pass every generated-route, final-bucket,
final-winner, and dense-oracle check. Warm inference is nevertheless slower:
**3,911.1 ms mean** versus **2,970.3 ms** for retained mixed-hot2, a **1.317x
ratio (31.7% slower)**. Medians are nearly tied at 3,949.4 versus 3,933.7 ms,
but there is no aggregate scaling win.

B=8 halves the B=4 gate count to 32 blocks per hot group while shaping more
exact rows. It therefore closes the plausible block-size knee: neither the
lower-row B=4 point nor the lower-gate B=8 point displaces the retained in-place
mixed-hot2 construction.

Chrome 153.0.8010.36. Raw direct comparison: `ab-results.json`; concise paired
summary: `AB_RESULTS.md`.
