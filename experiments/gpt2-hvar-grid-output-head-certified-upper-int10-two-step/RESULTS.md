# Two-step certified-group exact probe

A second 256-node exact stage inherits the masked remaining group and reuses
the first stage's global-int16 fonts and token-to-glyph dispatch CSS. A typed
CSS comparison keeps the higher exact group maximum, with lowest-token tie
breaking.

| Metric | Result |
| --- | ---: |
| Extra exact-stage HTML | 25.385 KB |
| Extra exact-stage CSS | 1.459 KB |
| Cold load + first evaluation | 52.657 s |
| Later fixture mutations | 2.954-6.379 s; 4.953 s median |
| Second group/winner agreement | 10/10 |
| Best-of-two agreement | 10/10 |
| Dense GPT-2 winner | 10/10 |

This is the strongest browser scaling result in the certified branch. An
additional exact group does not duplicate the 5 MB dispatch table or 79 MB
fine fonts; it adds only 256 candidate elements and a small namespaced
readback. Combined with the 399-element masked group router, the offline int10
median of three groups and p95 of fifteen groups are declaratively plausible.

The page is a two-step functional probe, not yet a fully rigorous stopping
cascade. Production unrolling still needs (1) a conservative upper/lower
allowance for font-axis and layout realization, (2) masking of every prior
group, and (3) a bounded fallback at the worst-case stage count.

## Reproduce

```sh
make test-gpt2-certified-int10-two-step
```
