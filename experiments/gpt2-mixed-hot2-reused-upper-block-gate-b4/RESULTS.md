# Reused-upper hot-2 block gate, B=4

Decision: **superseded by the direct outer maximum with full hot grids**.

This is the first block-gate integration that beats the retained mixed-hot2
head without changing its exact browser score contract. It does not add a
second coarse-center bank. The 512 int10 upper rows already needed for routing
also supply token bounds; the 512 exact hot rows are present only behind
conditional four-row block gates.

## Topology

For each paid upper width

```text
A = floor4(center + norm*r_float + 4px)
```

the gate reuses the identical serialized `r_float` literal and derives

```text
target upper = A - norm*r_float + norm*r_target + allowance
target lower = A - norm*r_float - norm*r_target - 4px - allowance
```

The extra `-4px` covers the exact-multiple case of the outward upper rounding;
the existing 27-bucket allowance remains an empirical Chrome transport bound.

The original group-wrapper timeline could not consume the gated exact maximum:
`anchor-size()` either formed a descendant sizing cycle or resolved to zero
across the wrapper's containing-block boundary. The working form replaces only
the outer bucket extraction with one direct 197-way `max(anchor-size(...))`
node. The existing match, group-index, local-token, best-first, and certificate
decoders remain unchanged. The exact hot maximum supplies `--group-0/1`; a
rounded proxy supplies `--score-group-0/1`.

## Offline screen

All target winners are retained.

| Screen | Group | Mean exact rows | Median | Maximum |
|---|---:|---:|---:|---:|
| 10 certified fixtures | 0 | 20.4 | 18 | 40 |
| 10 certified fixtures | 1 | 57.6 | 60 | 68 |
| 1,024 corpus states | 0 | 55.21 | 48 | 124 |
| 1,024 corpus states | 1 | 112.57 | 104 | 256 |

## Browser correctness

The strict two-fixture falsification passes 2/2 cases and all four active
stages against live exact shadows. It checks the generated group route,
per-stage score bucket and winner, recomputed best state, certificate gap,
stopping condition, route visibility, and dense final winner.

The decisive paired A/B passes **30/30** semantic checks over three alternating
rounds and all ten certified fixtures. Every route, final bucket, and token
matches the retained mixed-hot2 page, the generated route, and the dense oracle.

## Paired warm timing

| Metric | B=4 candidate | Retained mixed-hot2 | Ratio |
|---|---:|---:|---:|
| Mean, 30 samples | 3,850.1 ms | 4,186.3 ms | **0.920x** |
| Median | 3,227.2 ms | 3,903.1 ms | **0.827x** |
| p90 | 5,946.0 ms | 6,590.1 ms | 0.902x |
| Maximum | 12,098.3 ms | 7,995.1 ms | 1.513x |

The aggregate mean improves 8.0% and the median improves 17.3%. Browser timing
is noisy and includes one 12.1-second candidate outlier, so this is a warm
throughput result rather than a tail-latency claim.

Cold load regresses: 51.33 seconds for the candidate versus 40.06 seconds for
the retained page in the broad A/B. A later direct head-to-head holds the direct
maximum constant and shows the full-hot-grid form is 5.8% faster by mean and
5.2% by median, with better p90 and maximum. The B=4 result remains evidence
that the bound derivation is exact, but is no longer the deployment choice; see
`../gpt2-mixed-hot2-direct-outer-max/RESULTS.md`.

Generated size is 8,379,597 bytes of HTML and 936,946 bytes of topology CSS;
all fonts are reused. Chrome: 153.0.8010.36. Raw strict and paired observations
are in `browser-results.json` and `ab-results.json`.
