# Exact-GELU two-block topology experiments

## Result

The current serial block-1 projection topology remains the best exact runtime
shape. Parallel branches do not make the browser execute the FC slices like CPU
threads. They trade a shorter dependency chain for hundreds or thousands of
additional addressable layout objects, and those objects cost more than the
removed serialization.

All valid pages contain no runtime JavaScript. The Playwright harness changes
one of four real input cases and forces all 768 final widths. Every reported
valid topology has the same maximum RMSE to the floating reference (about
0.03792) and agrees with the established exact-CSS-GELU page coordinate for
coordinate.

## Parallel and hybrid screen

Chrome 153, warm HTTP/font/browser caches, fresh page graph per timed mutation.
These are one-round topology screens; the leading one-branch candidates were
then retested for eight rounds.

| Block-1 projection topology | Elements | Screen median | Correct? |
| --- | ---: | ---: | --- |
| Exact serial | 23,528 | 1,688 ms | yes |
| 4 same-tree branches | 26,583 | 1,749 ms | yes |
| 5 same-tree branches | 27,353 | 1,869 ms | yes |
| 7 same-tree branches | 28,893 | 1,936 ms | yes |
| 13 parallel branches | 33,487 | 2,266 ms | yes |
| Old 13-branch avar2 projection | 33,487 | 2,837 ms | lower precision |

The 2- and 3-branch same-tree pages appeared competitive but are invalid.
Their branches nest roughly 7 and 5 FC readback trees, exceeding Chromium's
effective HTML nesting depth. The parser silently reparents descendants and the
maximum output errors rise above 700.

Resetting parser depth with one shadow root per FC slice fixes that failure.
Slotted light-DOM outputs retain anchor visibility in the shared outer shadow
tree, which is a useful browser capability, but extra branches still add 768
partial-output elements apiece:

| Shadow-reset topology | Elements | Screen median | Correct? |
| --- | ---: | ---: | --- |
| 1 branch, direct output | 23,531 | 1,747 ms | yes |
| 2 branches + anchor sum | 25,069 | 1,747 ms | yes |
| 3 branches + anchor sum | 25,839 | 1,763 ms | yes |
| 4 branches + anchor sum | 26,609 | 1,776 ms | yes |

The apparent one-branch win did not survive the controlled eight-round run:

| Variant | Median | p10 | p90 |
| --- | ---: | ---: | ---: |
| Exact serial | 1,807.9 ms | 1,701.0 ms | 1,913.7 ms |
| Shadow-reset one branch | 1,790.5 ms | 1,664.0 ms | 1,891.3 ms |

That is a 1.0% difference inside the observed run-to-run spread, so the two
forms should be considered equivalent rather than a new optimization.

## Registered versus inline GELU state

Inlining the typed GELU calls directly in `font-variation-settings` removes
3,310 registered intermediate properties and 351 KB of transferred CSS/HTML.
It is exactly numerically equivalent, but it is not faster:

| Variant | Resources | Median | p10 | p90 |
| --- | ---: | ---: | ---: | ---: |
| Registered GELU values | 19.819 MB | 1,765.7 ms | 1,653.5 ms | 1,809.8 ms |
| Inline GELU calls | 19.468 MB | 1,803.2 ms | 1,661.9 ms | 1,863.8 ms |

Inlining is useful as a bundle-size option, but the registered form is 2.1%
faster in this eight-round run. Registered custom properties are not the main
transport cost and may help Chromium cache typed function results.

## Conclusion

Keep the registered, one-branch serial exact-GELU graph as the performance
baseline. More parallel projection branches, extra shadow boundaries, and
removing registered GELU values do not attack the measured bottleneck. The
exact vector-boundary oracle still shows that FC geometry readback and the
block-output handoff account for roughly 1.5 seconds of the 1.71-second reduced
benchmark, while exact GELU plus the final linear projection need only about 89
milliseconds.

Raw measurements:

- `exact-css-gelu-parallel-two-block-results.json`
- `exact-css-gelu-hybrid-deep-screen.json`
- `exact-css-gelu-shadow-hybrid-screen.json`
- `exact-css-gelu-shadow-hybrid-one-results.json`
- `exact-css-gelu-inline-results.json`

