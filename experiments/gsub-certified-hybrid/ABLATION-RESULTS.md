# GSUB-certified hybrid topology ablation

Chrome **153.0.8010.36** (/Applications/Google Chrome.app/Contents/MacOS/Google Chrome), headless on darwin 25.0.0 (arm64). 7 measured rounds after 2 warm-up rounds; 21 accepted-case samples per bank/topology cell. The adversarial mixed-transition stress phase used 7 measured rounds after 2 warm-ups, all 10 reference cases, and 70 samples per target.

Correctness: **36/36 checks passed**. For every selected accepted case, the measured GSUB top matched the offline winner, the two-grid variants' runner matched the offline runner, the route remained accepted, and final geometry returned the expected token. Selected cases: fixture 0/group 2 (clear-accept; top 20, runner 41); fixture 0/group 128 (clear-accept; top 77, runner 72); fixture 2/group 195 (clear-accept; top 24, runner 33).

## Adversarial mixed-transition stress

This is deliberately **not production-weighted**: the ten reference cases are adversarial and route 7/10 cases to fallback, versus 226/1,970 (11.47%) on the full screen.

Correctness: **20/20 hybrid final-winner comparisons matched the separate exact page**. That exact CSS page is the authoritative baseline. Its fixture 9/group 96 winner is 24755; the offline 24794 value appears stale or incorrect for that selected pair (the other 9/10 offline entries match).

| Bank | Target | Overall median | Accepted median | Fallback median |
| --- | --- | ---: | ---: | ---: |
| bounded | Current full hybrid | 285.75 ms | 41.00 ms | 440.00 ms |
| bounded | Exact baseline | 231.85 ms | 233.30 ms | 231.80 ms |
| full | Current full hybrid | 288.75 ms | 45.10 ms | 452.70 ms |
| full | Exact baseline | 231.85 ms | 233.30 ms | 231.80 ms |

| Bank | Hybrid − exact overall | Hybrid − exact accepted | Hybrid − exact fallback | Hybrid beats exact overall? |
| --- | ---: | ---: | ---: | --- |
| bounded | 53.90 ms | -192.30 ms | 208.20 ms | no |
| full | 56.90 ms | -188.20 ms | 220.90 ms | no |

| Bank | Route transition | Samples | Hybrid median | Exact median |
| --- | --- | ---: | ---: | ---: |
| bounded | accept->accept | 8 | 30.70 ms | 246.10 ms |
| bounded | accept->fallback | 14 | 456.80 ms | 232.55 ms |
| bounded | fallback->accept | 13 | 224.70 ms | 225.40 ms |
| bounded | fallback->fallback | 35 | 431.60 ms | 230.70 ms |
| full | accept->accept | 8 | 38.10 ms | 246.10 ms |
| full | accept->fallback | 14 | 446.50 ms | 232.55 ms |
| full | fallback->accept | 13 | 232.40 ms | 225.40 ms |
| full | fallback->fallback | 35 | 454.10 ms | 230.70 ms |

Every stress sample is timed inside its page from the first of 768 input writes through the score-offset/group writes and a forced final geometry read (hybrid) or exact-result geometry read (baseline). Case order reverses on odd rounds and rotates every round; the three page targets are likewise reversed and rotated. Route classification and transition bookkeeping happen after the timed geometry read. The adversarial mixed-transition stress set does not favor the hybrid in either bank.

## Full-screen route-rate projection

Using the full-screen rate P(accept)=1,744/1,970=88.53% and P(fallback)=226/1,970=11.47%, an independent-consecutive-route weighting of the four measured transition medians projects **98.95 ms bounded** and **104.79 ms full**. The simpler accept/fallback route-median weighting projects **86.77 ms bounded** and **91.86 ms full**, versus 231.85 ms exact.

Both projections favor the hybrid: transition weighting gives 2.34× bounded and 2.21× full; route-median weighting gives 2.67× and 2.52×. This is roughly a **2.2–2.6× projected speedup** (the unrounded bounded route-median ratio is 2.67×), but remains empirical and depends on the real transition distribution and on stress-set medians transferring to the full screen. It is not a direct 1,970-case performance measurement.

## Mutation medians

| Topology | Bounded bank | Full bank |
| --- | ---: | ---: |
| Pure one-grid GSUB (existing baseline) | 6.10 ms | 9.10 ms |
| Two-grid top+runner; exact DOM removed | 12.90 ms | 20.20 ms |
| Two-grid top+runner; exact DOM and stylesheet removed | 13.20 ms | 21.10 ms |
| Two-grid; exact DOM hidden and input inheritance reset | 15.00 ms | 21.50 ms |
| Two-grid; exact DOM forced hidden, direct final readback | 14.80 ms | 21.90 ms |
| Current full hybrid | 14.50 ms | 24.10 ms |

Each in-page sample starts immediately before 768 hidden-vector custom-property writes plus score-offset and group, and ends after a synchronous `getBoundingClientRect().width` on the final/readback geometry. Page load, font readiness, topology mutations/removals, warm-up, correctness scans, and Playwright round trips are outside the clock. Variant order alternates and rotates by round.

## Differential attribution

| Median difference | Bounded bank | Full bank |
| --- | ---: | ---: |
| Second grid + top/runner/direct-final readback | 7.10 ms | 12.00 ms |
| Unused exact stylesheet with exact DOM absent | -0.30 ms | -0.90 ms |
| Hidden/reset exact DOM | 2.10 ms | 1.30 ms |
| Inherited exact-subtree style invalidation | -0.20 ms | 0.40 ms |
| Current final gating over forced-hidden/direct-final | -0.30 ms | 2.20 ms |
| Current full hybrid over pure one-grid | 8.40 ms | 15.00 ms |

These are differences of medians, so they are diagnostic contrasts rather than additive accounting. The exact-DOM-removed required variant retains the exact dispatch stylesheet; the additional no-exact-assets variant removes that otherwise unused stylesheet to give the cleanest second-grid contrast. The hidden/reset variant blocks the exact subtree from inheriting the 768 mutated inputs; comparing it with forced-hidden/inheriting DOM isolates inherited style invalidation. Comparing forced-hidden/direct-final with the unchanged full hybrid isolates the current conditional display/final-width gating layer.

## Conclusion

The adversarial stress medians do not favor the hybrid: bounded measured 285.75 ms and full measured 288.75 ms, versus 231.85 ms exact. They must not be treated as production-weighted because fallback is overrepresented 7/10. At the full-screen 11.47% fallback rate, the empirical projections favor the hybrid at about 87–105 ms, or roughly 2.2–2.6× faster than exact, subject to transition-distribution assumptions. The largest positive accepted-path component was **second grid + readback** in the full bank (12.00 ms).

## Scope

The topology decomposition times only the three previously certified accepted fixture/group pairs; the adversarial stress phase times all ten reference cases, including route transitions. The full-screen figures are projections, not direct timings. This does not broaden the empirical six-bucket certification claim. JavaScript mutates benchmark inputs, performs one-time topology setup, forces geometry, and checks results; it does not choose the winner or route.
