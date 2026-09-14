# Packed-mask 61-stage cascade

Packing visited groups into thirteen 16-bit CSS integers removes the quadratic
history expressions and avoids the 197 inherited properties used by the first
linear-mask attempt.

| Metric | Expanded history | 197-property linear | 16-bit packed |
| --- | ---: | ---: | ---: |
| HTML | 10.730 MB | 10.730 MB | 10.730 MB |
| CSS | 24.100 MB | 11.969 MB | **11.354 MB** |
| Cold load + first evaluation | 199.411 s | 228.468 s | 214.558 s |
| Warm mutation median | 5.916 s | 5.609 s | 5.910 s |
| Warm mutation mean | 5.359 s | 5.426 s | 5.483 s |
| Group order / final dense winner | 10/10 | 10/10 | 10/10 |

Packed masks are the strongest compact visited-set encoding, but full-depth
one-shot scaling is still rejected. They halve CSS versus expanded history and
avoid the linear mask's property explosion, yet cold first result remains above
three minutes. The remaining cost is the duplicated 197-source/197-match router
at every dormant stage, not visited-set state.

This result strengthens the case for a constant-depth parallel tail rather
than any 61-stage representation.

## Reproduce

```sh
make test-gpt2-certified-int10-unrolled-packed-mask
```
