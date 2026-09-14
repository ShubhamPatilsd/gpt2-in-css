# Forced 16-stage expanded-history control

This is the expanded-history control for the packed-mask deep-traversal stress
test. The 1,000-bucket-per-side slack forces all 16 stages to remain active.

Chrome 153 selected the same 16 unique groups, per-group fine winners, and final
dense winner as the packed-mask build. Both variants swapped offline groups 20
and 11 at stages 15 and 16. Since the mask implementations are independent,
the shared order is evidence of browser score-coordinate realization drift,
not packed bit extraction failure.

Cold load plus first evaluation was 137.931 s. This single control run is not a
latency comparison.
