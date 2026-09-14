# Certified int10 batched-tail probe

## Result

The configurable batched tail works as a CSS topology. After the gated six-group
prefix, serial upper-bound routers select `B` distinct unvisited groups, exactly
`B` dynamic 256-candidate grids score them in parallel, and the existing
score/group plane followed by the token plane merges those scores with the
prefix winner. A final router applies the strict certificate
`merged_bucket - next_upper > allowance`.

`B=2` is the strongest proof-grade result on the saved fixtures. It certifies
both hard cases, matches every raw offline per-group winner, and costs much less
than `B=4` or `B=8`. The requested priority `B=4` topology is correct on the
current-range fixture, but batching four groups did not beat the equivalent
serial cascade in warm mutation time.

## Correctness

Chrome `153.0.8010.36` was tested with JavaScript disabled in the page. All four
batch sizes had these results:

- The easy fixture stopped in the prefix and effectively displayed zero batch
  scorer grids.
- Active paths displayed exactly `B` scorer grids.
- Selected groups were distinct and matched the offline set and order.
- The score/group merge geometry matched the maximum browser branch.
- The token plane selected that branch's token.
- The post-batch next group and strict certificate matched the offline oracle.
- The final winner matched the offline target and dense winner on every fixture.

Selected groups were:

| B | Current-range hard, state 579 | Forced stress, state 190 |
|---:|---|---|
| 1 | `5` | `7` |
| 2 | `5, 46` | `7, 36` |
| 4 | `5, 46, 29, 2` | `7, 36, 4, 91` |
| 8 | `5, 46, 29, 2, 18, 9, 196, 35` | `7, 36, 4, 91, 186, 47, 77, 3` |

The forced stress fixture remains uncertified after `B=1`, exactly as its
strict oracle requires, then certifies at `B=2`. The natural hard fixture
certifies for every tested batch size.

## Exact scorer boundary

The wider forced stress run exposes the known group-91 browser discrepancy at
`B=4` and `B=8`. The dynamic scorer produces token `23359`; the raw global-int16
oracle produces token `23532`. The result exactly reproduces the earlier static
six-active browser diagnostic, so selection, dynamic group dispatch, and the
merge planes are not the source of the difference. It is an existing
browser-realization limitation of the exact font scorer for this group and
fixture.

No replacement oracle was substituted. Consequently, `B=4` and `B=8` are
raw-oracle-clean on the current-range easy and hard fixtures, but their forced
stress runs are diagnostic rather than proof-grade for every non-winning
branch. Group 91 does not win the merge, and the final stress winner remains the
correct token `78`.

## Size and timing

Cold numbers are one browser load plus the first easy evaluation and are noisy;
the B=8 cold inversion should not be treated as a stable speedup. Warm is the
median of the three fixture mutations. Times are seconds.

| B | HTML MB | CSS MB | DOM | Batch cold+first | Batch warm | Serial cold+first | Serial warm | Warm delta |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 8.298 | 5.843 | 57,682 | 66.347 | 8.406 | 49.467 | 8.202 | +0.203 |
| 2 | 8.348 | 5.999 | 58,601 | 54.334 | 8.879 | 46.716 | 8.842 | +0.037 |
| 4 | 8.448 | 6.329 | 60,439 | 94.807 | 14.865 | 66.814 | 8.831 | +6.034 |
| 8 | 8.647 | 7.064 | 64,115 | 44.129 | 14.659 | 63.695 | 8.191 | +6.468 |

On the natural hard fixture specifically, mutation times were 10.084, 11.074,
16.571, and 17.267 seconds for B=1, 2, 4, and 8. Equivalent serial times were
10.310, 10.540, 11.141, and 11.542 seconds. The serial cascade gates after seven
groups on that fixture, whereas a fixed batch shapes all `B` selected groups.
This explains why larger batches lose despite reducing dependency depth.

## Implementation notes

- Every variant starts from the existing six-stage gated prefix and uses its
  scorer/font/dispatch assets.
- Batch slot 0 consumes `--remaining-group-6`; later slots use serial masked-max
  routers that exclude all prefix and prior batch groups.
- The scorer grids are generic with respect to selected group, but there are
  only `B` such grids in each generated page.
- Permanent prefix/merge anchors remain outside `display:none`; only the gated
  batch subtree is skipped on the easy path.
- The nested generated pages rewrite both inherited coarse-stylesheet and fine
  font URLs. Missing the coarse stylesheet was the cause of an initial group-0
  default result and is guarded by builder assertions.

## Reproduction

```sh
make test-gpt2-certified-int10-batched-tail
```

Machine-readable details are in `build-results.json`,
`browser-comparison.json`, and each `b*/browser-results.json`.
