# Six-stage certified int10 prefix plus parallel uncertainty tail

## Result

The full constant-depth topology works in Chrome 153. The page contains all
197 tail gates, permanent score/token carriers, and one 198-way merge (the
six-stage prefix candidate plus 197 group branches). Only exact scorer grids
whose unvisited coarse upper can still tie or beat the current refined lower
are displayed.

The official browser run is all green for 0, 1, and 2 simultaneously active
tail groups:

- the easy fixture displays no tail scorer;
- the natural hard fixture activates exactly group 5;
- the forced multi-branch fixture activates exactly groups 7 and 36;
- every active group winner matches its offline global-int16 oracle;
- the score/group max and token-selection planes match the browser branch max;
- all three final winners match both the offline target and dense GPT-2 winner.

| Metric | Result |
| --- | ---: |
| Chrome | 153.0.8010.36 |
| Static tail branches | 197 |
| Total DOM elements | 159,005 |
| HTML / CSS | 13.348 MB / 6.011 MB |
| Cold load | 37.827 s |
| Cold load + first evaluation | 41.953 s |
| Warm mutation range | 4.125-10.073 s |
| Warm median | 8.592 s |
| Active tail groups | 0 / 1 / 2 |

Cold timing varies substantially between Chrome processes and should not be
read as faster than the smaller six-stage page. Relative to that source, this
probe adds about 5.1 MB HTML and 0.32 MB CSS while reusing its fonts and group
dispatch table. Its fallback mutations are also slower than the six-stage
gated page's prior 4.806 s median, so the constant-depth tail buys completeness
and bounded dependency depth, not lower latency.

## Fixture and certification details

Only 70 of the saved 1,024 states fit the existing ±135.309 font-axis range.
Under the current realized-coordinate allowances (10 coarse buckets and 5 fine
buckets) the offline screen has 69 states certified within six groups and one
natural seven-group state, corpus index 579.

Chrome realizes that natural fixture's sixth gap as 16 buckets rather than the
offline 12. The probe adds one outward browser-boundary bucket to that fixture,
making the runtime threshold 16 and preserving a strict stop (`gap > bound`).
This is conservative: equality remains unresolved. It activates only group 5,
whose browser winner is token 1321, exactly matching the offline oracle. The
prefix still wins globally with token 930.

The multi-branch fixture uses a deliberately larger declared 48-bucket total
allowance. It activates groups 7 and 36 together, with exact winners 1990 and
9232. The permanent zero-width carriers for all other groups keep the full
198-way score reduction and token plane valid without shaping dormant grids.

## Additional six-active diagnostic

`browser-results-six-active.json` preserves a wider 128-bucket stress run. It
completed rather than crashing: six groups activated in 11.015 s, activation
matched offline exactly, both merge planes were correct, and the final winner
was correct. However, one non-winning active branch (group 91) produced browser
token 23359 instead of raw global-int16 token 23532. Therefore the six-active
run is diagnostic evidence, not the official correctness pass. It reinforces
the existing constraint that browser-exact group scoring needs calibration or
a browser-realized oracle before arbitrary wide uncertainty sets can be called
proof-grade.

## Implementation notes

- Router six already exposes one permanently named upper-source anchor per
  group with the six visited groups masked to zero. Tail gates reuse those
  anchors and apply the strict upper-versus-best threshold.
- The registered allowance defaults to a disabled negative sentinel so the
  source page's unrelated initial radio fixture cannot wake a large tail during
  cold parse. The harness sets the declared allowance before each evaluation.
- Every cloned scorer has an inline unique anchor name. This was necessary in
  the large cascade: a class declaration resolved to the source's generic
  `--fine-winner`, colliding across branches.
- Score carriers encode `bucket * 1024px + (197 - group) * 4px`; the second
  plane selects the winning group's small token-width anchor. The maximum saved
  fixture geometry is 8.198 million px, below Chrome's approximately 33.55
  million px layout limit.

## Reproduce

```sh
make test-gpt2-certified-int10-parallel-tail
```

The default test omits the forced stress fixture and exercises only the natural
easy and hard current-range paths.
