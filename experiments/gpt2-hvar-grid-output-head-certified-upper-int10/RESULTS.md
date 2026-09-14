# Certified row-wise int10 upper head

The existing five-shard row-wise int10 GPT-2 head now ranks the rigorous
Cauchy upper bound

```text
h·wq + ||h||₂ ||w-wq||₂
```

instead of the approximate score alone. Each token carries one precomputed
error-norm factor. CSS evaluates the 768-term query norm once on the group
scroller, then adds the inherited scalar bound to every candidate width.
Upper buckets use outward `round(down, x + 1 bucket)` encoding and bound
factors are serialized upward.

Chrome 153 matches the offline upper token and group on all 10 browser
fixtures. Eight selected groups contain the dense GPT-2 winner.

| Metric | Result |
| --- | ---: |
| Cold load + first evaluation | 36.655 s |
| Later fixture mutations | 2.141-3.174 s; 2.346 s median |
| Upper token/group agreement | 10/10 |
| Dense winner in first group | 8/10 |
| Added bound metadata | 1.316 MB |

The first implementation exposed two useful Chrome constraints. A 768-term
`sqrt(sum(h²))` is supported, but evaluating it on the same element as the
768-axis `font-variation-settings` expansion returns the registered initial
value. Moving the norm to a child fixes it. The head's readback container
queries also remain intentionally nested through EOF, so new top-level rules
must be inserted before that chain rather than appended.

Retain. This validates the low-precision half of a rigorous best-first head.
The remaining rigor item is a conservative allowance for variable-font axis
normalization and layout realization when comparing upper and exact buckets.

## Reproduce

```sh
make test-gpt2-certified-int10-upper-head
```
