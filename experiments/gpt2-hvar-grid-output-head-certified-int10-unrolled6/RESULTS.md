# Six-stage certified int10 cascade

This fixture unrolls six best-first search steps in HTML/CSS. Each step selects
the highest unvisited row-wise-int10 group upper bound, exact-scores that
256-token group with the shared global-int16 font bank, and retains the best
exact token seen so far. A final masked router exposes the next unvisited upper
bound for the stopping test.

| Metric | Result |
| --- | ---: |
| HTML / CSS | 8.248 MB / 5.689 MB |
| Cold load | 59.668 s |
| Cold load + first evaluation | 64.268 s |
| Later fixture mutations | 4.599-10.178 s; 7.936 s median |
| Group order vs offline oracle | 10/10 |
| Per-group exact winners vs offline oracle | 10/10 |
| Accumulated best winner vs offline oracle | 10/10 |
| Final dense GPT-2 winner | 10/10 |
| Browser groups before the empirical stop | 1-3; 2 median |

The structural result is positive: all six routers and exact stages compose,
every selected group is unique, tie-breaking remains deterministic, and every
fixture reaches its dense winner. Additional exact stages continue to reuse the
same roughly 5 MB token dispatch CSS and fine font bank; the incremental work is
the 399-element masked router plus 256 candidate elements per stage.

The present 24-bucket allowance per side is an empirical placeholder, not yet a
proof. Chrome and NumPy disagree about the first safe stopping stage for 2/10
fixtures near the 48-bucket threshold: one browser run delayed a stop from one
group to two (gap 46), while another advanced it from three groups to two (gap
50). This does not affect the six-stage winner, but it confirms that production
stopping must use a browser-realization error bound rather than the current
screening constant.

The ungated page evaluates all six stages even after `--done-N` becomes one.
The follow-up gated build removes the later nested subtree from style/layout,
retains 10/10 winners, and cuts warm median latency from 7.936 to 4.806 seconds.
See `../gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated/RESULTS.md`.

## Reproduce

```sh
make test-gpt2-certified-int10-unrolled
```
