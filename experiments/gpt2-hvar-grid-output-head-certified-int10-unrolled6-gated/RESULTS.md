# Gated six-stage certified int10 cascade

This variant uses each certificate flag to set the next exact stage and its
nested continuation to `display:none`. The hidden subtree reopens when a later
input needs more groups, so one loaded page remains reusable.

| Metric | Ungated | Gated |
| --- | ---: | ---: |
| Source HTML / CSS | 8.248 MB / 5.689 MB | 8.248 MB / 5.689 MB |
| Cold load + first evaluation | 64.268 s | 49.100 s |
| Warm mutation median | 7.936 s | **4.806 s** |
| Warm mutation mean | 7.825 s | **4.517 s** |
| Warm mutation range | 4.599-10.178 s | **3.023-5.862 s** |
| Active exact groups | Always 6 | 1-3; 2 median |
| Final dense GPT-2 winner | 10/10 | 10/10 |

Every gated fixture is faster than its ungated counterpart, by 23.8-63.4%.
Mean warm latency falls 42.3% and median falls 39.4%. The fixture sequence also
proves re-arming: a one-group stop is followed by two-group cases, and the
previously hidden branch recomputes correctly.

The corrected gated harness stops forcing layout on hidden descendants. Its
latest cold process was faster, but an earlier process took 75.381 seconds with
identical source, so cold-start variation is too large for a strong claim.
Both pages still parse the full 8.25 MB source and load the same fonts. Gating
is primarily a lifecycle optimization, not a source-size optimization.

The 24-bucket-per-side stop margin remains conditional on the
browser-realized-coordinate target described in
`../gpt2-browser-certification-budget/RESULTS.md`. The gate mechanics are
valid independently of that constant; a production build should substitute
the chosen conservative bound.

## Reproduce

```sh
make test-gpt2-certified-int10-unrolled-gated
```
