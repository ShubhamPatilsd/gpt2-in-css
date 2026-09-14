# Packed-mask six-stage cascade

This variant packs the 197 visited-group flags into thirteen 16-bit CSS
integers. `pow()`, `mod()`, and `round(down,...)` set and test bits exactly;
alternating A/B banks avoid custom-property self-reference across stages.

| Metric | Expanded history | Packed mask |
| --- | ---: | ---: |
| HTML | 8.248 MB | 8.248 MB |
| CSS | 5.689 MB | 5.613 MB |
| Cold load + first evaluation | 49.100 s | 61.477-66.527 s |
| Warm mutation median | 4.806 s | 4.682-5.167 s |
| Warm mutation mean | 4.517 s | 4.440-4.682 s |
| Warm mutation range | 3.023-5.862 s | 2.943-6.168 s |
| Group order / final dense winner | 10/10 | 10/10 |

The integer mask is exact and reduces CSS. One warm run was slightly faster
than expanded history and the strict-bound rerun was slightly slower, so there
is no stable latency difference. Cold variation is also large. This is the
best compact visited-set representation tested, though the six-stage expanded
form was already small.

## Deep-state stress

A forced 16-stage fixture exercised all 16 packed updates without an early
certificate stop. Chrome selected 16 unique groups, the correct fine winner for
each selected group, and the exact dense winner. An apparent stage-15 ordering
disagreement was reproduced exactly by the independent expanded-history mask;
it is browser coordinate realization drift, not packed-state corruption.

Packed cold load plus first evaluation was 131.961 s versus 137.931 s for the
single expanded control. Those are stress-test observations, not a stable
latency comparison.

## Reproduce

```sh
GPT2_CERTIFIED_STAGES=6 make test-gpt2-certified-int10-unrolled-packed-mask
```
