# Incremental-mask 61-stage cascade

This variant replaces each stage's expanded history expression with 197
incremental unvisited flags. Two alternating custom-property banks carry the
mask through the nested cascade:

```text
nextUnvisited[group] = previousUnvisited[group]
                       * (newSelectedGroup != group)
```

That changes generated mask source from quadratic to linear in stage count.

| Metric | Expanded history | Incremental mask |
| --- | ---: | ---: |
| HTML | 10.730 MB | 10.730 MB |
| CSS | 24.100 MB | **11.969 MB** |
| Cold load + first evaluation | 199.411 s | 228.468 s |
| Warm mutation median | 5.916 s | 5.609 s |
| Warm mutation mean | 5.359 s | 5.426 s |
| Warm mutation range | 3.560-7.204 s | 3.344-7.352 s |
| Group order / final dense winner | 10/10 | 10/10 |

The representation is exact and halves CSS bytes, but it is not a latency win.
Cold plus first result is 14.6% slower despite the smaller stylesheet, which
shows that initializing and inheriting 197 mask properties at every dormant
boundary is more expensive than parsing the repeated expressions in this run.
Warm results are effectively tied within single-run variance: median improves
5.2%, while mean regresses 1.3%.

Retain the two-bank form only if transfer/storage size becomes the constraint.
For browser inference latency, the expanded-history shallow fast path remains
better, and a full-depth fallback needs a representation that avoids both
quadratic source and hundreds of inherited properties per stage.

## Reproduce

```sh
make test-gpt2-certified-int10-unrolled-linear-mask
```
