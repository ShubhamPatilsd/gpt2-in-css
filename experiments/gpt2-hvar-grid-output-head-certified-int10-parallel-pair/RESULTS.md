# Parallel two-group exact refinement probe

## Result

The parallel branch structure works, but the requested single-width
score/token merge does not.

The coarse-selected group's exact scorer and the masked next-group router are
siblings under `#result`. The second exact scorer is nested only under that
router. Chrome produced the correct first exact winner, second group, and
second exact winner for all 10 fixtures, proving that the two expensive paths
do not need to be serially nested.

The merge carrier

```text
scoreBucket * 1024px + (50256 - tokenId) / 64px
```

correctly selected the wider branch and decoded its score bucket on all 10
fixtures. It decoded the token incorrectly on all 10. At the observed
4.13M–12.92M px widths, Chrome quantized away part of the 1/64 px token field:
the maximum measured carrier error was 0.234375 px. Examples include token 11
decoding as 17 and token 477 decoding as 465.

This is a precision blocker, not an anchor-scoping blocker or a failure of the
parallel routing idea.

## Browser evidence

Chrome 153.0.8010.36, headless, 800×200 viewport, JavaScript disabled in the
page:

| Check | Result |
|---|---:|
| First exact winners | 10/10 |
| Masked second groups | 10/10 |
| Second exact winners | 10/10 |
| `max()` chose the wider branch | 10/10 |
| Merged score bucket vs browser branch max | 10/10 |
| Merged token vs browser branch max | 0/10 |
| Browser branch-max winner vs dense winner | 10/10 |
| Final decoded dense winner | 0/10 |
| Maximum merge width | 12,923,658 px |
| Nominal Chrome layout headroom | 20,630,770 px |
| Maximum carrier precision error | 0.234375 px |

`allPairBucketsCorrect` in `browser-results.json` is also false because it
compares browser buckets with NumPy buckets. That is the already-observed
browser score-bucket drift. The more relevant in-browser check,
`allMergedBucketsDecodeBrowserBranchMax`, is true; only the token subfield is
lost.

The geometry cannot be repaired by simply enlarging the tie step while keeping
the same one-plane encoding. A globally ordered 50,256-token tie field needs a
score stride larger than the whole tie band. At a 1 px token step that means a
stride above 50,256 px, which would put fixture 1 near 634 million px—far above
the approximately 33.55 million px layout cap. The requested 1/64 px step fits
inside a 1024 px stride, but is below Chrome's effective precision at the
resulting multi-million-pixel width.

## Timing

The final run is compared with the existing saved runs; these are single-run
wall-clock measurements and should be treated as directional.

| Probe | Load | Load + first | Median loaded mutation | Mutation range |
|---|---:|---:|---:|---:|
| Parallel pair | 51.283 s | 56.033 s | 5.486 s | 4.750–7.484 s |
| Serial two-step | 49.702 s | 52.657 s | 4.953 s | 2.954–6.379 s |
| Gated six-stage | 46.077 s | 49.100 s | 4.806 s | 3.023–5.862 s |

Against serial two-step, the parallel pair was 3.2% slower to load, 6.4%
slower through the first result, and 10.7% slower at the median loaded
mutation. It was 14.1% slower than the gated cascade's median mutation, and
that cascade can also evaluate a third group with the same source graph.
This does not show a scaling win from sibling layout; Chrome still resolves the
dependent anchor/container graph in its layout pipeline, and the merge adds
large-width geometry.

## Decision

Retain the parallel sibling routing structure as a viable graph
reorganization, but reject the one-plane global-token geometry merge.

A follow-up merge should use two planes: first select the winning branch using
score geometry plus a compact branch/group tie, then read that branch's
already-small token geometry. That avoids asking one float-width value to hold
both a multi-million-pixel score and 1/64 px token detail.

## Reproduction

```sh
PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
  python tools/build_certified_int10_parallel_pair_probe.py
node tools/test_certified_int10_parallel_pair_probe.mjs
```

The complete measured output is in `browser-results.json`; generated fixture
expectations and geometry bounds are in `reference.json`.
