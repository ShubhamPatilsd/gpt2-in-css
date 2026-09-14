# Parallel pair two-plane merge probe

## Result

The two-plane merge works in Chrome 153 and removes the precision failure from
the one-plane experiment.

The parallel computation graph is unchanged: the first exact scorer and the
masked next-group router are siblings, while the second exact scorer depends
only on its router. The merge now uses:

1. A score/group plane whose width is
   `scoreBucket * 1024px + (197 - group) * 4px`.
2. A token plane that selects one of the two existing exact-result token
   anchors, whose widths are at most 50,255px.

The first plane's 788px group-tie band fits below the 1024px score stride. Its
4px resolution is well above the 0.234375px maximum precision error measured
by the failed packed-token experiment. Since the two branches always represent
different contiguous 256-token groups, choosing the lower group on an equal
score is exactly equivalent to choosing the lower global token range. Each
exact scorer has already resolved ties within its own group.

The decoded winning group is compared with the inherited first group to make a
0/1 branch selector. A small second-plane width then chooses between
`anchor-size(--pair-token-anchor-1 width)` and
`anchor-size(--pair-token-anchor-2 width)`. This proves that sibling anchor
geometry can be selected from a descendant of the first-plane readback; no
cross-sibling custom-property inheritance is needed.

## Correctness

Chrome 153.0.8010.36, headless, 800×200 viewport, JavaScript disabled in the
page:

| Check | Result |
|---|---:|
| First exact winners | 10/10 |
| Masked second groups | 10/10 |
| Second exact winners | 10/10 |
| First-plane `max()` branch geometry | 10/10 |
| Score bucket decoded from browser branch max | 10/10 |
| Winning group decoded from browser branch max | 10/10 |
| Second-plane branch/token selection | 10/10 |
| Final winner vs browser branch max | 10/10 |
| Final winner vs offline pair oracle | 10/10 |
| Final dense winners | 10/10 |
| Synthetic equal-bucket group ties | 2/2 |

The two synthetic tie cases force both branches to bucket 5000. One has group
3 defeat group 5 and returns token 1018; the other has group 2 defeat group 7
and returns token 700. This exercises both second-plane branch directions.

The largest first-plane fixture width is 12,926,736px, leaving 20,627,692px
below the probe's 33,554,428px Chrome layout limit estimate.

## Timing

The final correctness run measured:

| Metric | Two-plane pair |
|---|---:|
| Load | 72.477s |
| Load + first fixture | 78.181s |
| Median loaded mutation | 7.819s |
| Mutation range | 4.675–8.608s |

An immediately preceding full 10-fixture run, before adding only the synthetic
tie assertions, measured 56.500s load, 61.459s load plus first fixture, and a
5.814s median mutation. Both runs had identical 10/10 model correctness. The
large run-to-run spread means these wall-clock results are directional rather
than evidence of a regression caused by the tiny tie test.

For context, the currently saved comparison runs are:

| Probe | Load | Load + first | Median mutation | Mutation range |
|---|---:|---:|---:|---:|
| Failed one-plane parallel pair | 51.283s | 56.033s | 5.486s | 4.750–7.484s |
| Serial two-step | 49.702s | 52.657s | 4.953s | 2.954–6.379s |
| Gated six-stage | 46.077s | 49.100s | 4.806s | 3.023–5.862s |

There is no demonstrated latency win from parallel sibling placement. The
important positive result is structural and exactness-related: both exact
branches can be laid out as siblings and merged without serially nesting the
first exact result into the second-group route.

## Decision

Accept the two-plane merge as the browser-exact global winner/tie primitive for
a parallel pair. Reject the packed one-plane score/token encoding and retain
its experiment as the precision-blocker record.

Scaling this to more branches would require either an N-way first-plane group
selection followed by one token-anchor selection, or a reduction tree of these
pair merges. Timing should be re-benchmarked with repeated runs before choosing
between that approach and the existing gated cascade.

## Reproduction

```sh
python3 tools/build_certified_int10_parallel_pair_twoplane_probe.py
node tools/test_certified_int10_parallel_pair_twoplane_probe.mjs
```

The final machine-readable run is in `browser-results.json`; fixture geometry
and offline expectations are in `reference.json`.
