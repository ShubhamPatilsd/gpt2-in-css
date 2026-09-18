# Reading one saved vector instead of two

**The selective reader is numerically correct on this test, but slower.** All
four paired runs lose. The median paired increase is **25.5%** from navigation
to completion, or **28.7%** from the first observed capture to the final capture.
Do not enable this option as a speed optimization on the strength of its smaller
animation count. This is a 768-wide native handoff test, not a token benchmark.

## What we changed

The existing loop alternates between two stored vectors. On each pass, one bank
supplies the previous answer; the other receives the new answer. Both banks also
hold a pass number, so the loop can distinguish a fresh answer from an old one.

The default reader has `2*(768+1) = 1,538` animated channels. The existing
`selective=True` branch reads the previous bank's 768 numbers and both pass
numbers: `768+2 = 770`. It selects the corresponding animation names and
timelines on every change of phase. The banks, width carriers, acknowledgement
checks, native pass control, and arithmetic remain the same.

We call the repository's actual `loop_parts` implementation. The fixture also
mirrors the reusable core's private progress, saved-value and output properties,
explicit forwarding, and local pass controller. This matters: a tiny unscoped
two-number example would not exercise the same volume of registered CSS state.

## Workload and numerical gate

For coordinate `i` in `0..767`, the initial input is `(i mod 31 - 15)/64`.
Pass `p`, numbered from one, calculates:

```
next[i] = -previous[i]/2 + ((13*i mod 37)-18)/128 + (p mod 3)/32
```

This recurrence requires the previous result and changes signs and values.
It uses exact binary fractions before the browser's width/readback rounding.
It does not contain matrix fonts, normalization, attention, vocabulary scoring,
or token selection. Its cost must not be multiplied by twelve to claim a model
runtime.

Separate fresh-browser fixtures stop after **1, 2, 3, 4, 8 and 24 passes**. At
each endpoint we check all 768 input values, all 768 calculated outputs, both
768-value saved banks, and both generation stamps. Thus both early phase
directions and later feedback are exercised. Intermediate states between these
checkpoints are not all read numerically.

The thresholds were saved before running: maximum oracle error 0.003 and
maximum matched baseline/candidate difference 0.0001. Timing requires all
checkpoints to pass with the same fixture manifest. Every timed case repeats
the complete final checks after the timing boundary.

| Check | Correctness runs | Timing runs | Total |
| --- | ---: | ---: | ---: |
| Fresh browser cases | 12 | 8 | 20 |
| Coordinates checked against the recurrence | 36,864 | 24,576 | 61,440 |

All cases passed. The largest observed coordinate error was **0.000162792**.
All final stamps exactly matched their expected pass numbers. Matched candidate
and baseline vectors were **identical** at every checked endpoint, including
every timed case. These are observations on the stated recurrence and finite
checkpoints, not a proof for arbitrary numerical transforms.

A separate audit recomputed all 61,440 coordinate errors with exact rational
arithmetic, checked all 40 final stamps, and compared 30,720 matched coordinates.
It also verified that each candidate HTML is byte-identical to its baseline and
that removing exactly the two phase-selected animation-list rules makes the CSS
byte-identical. This checks that the intended reader change is the only variant
difference, rather than relying only on the generator's option name.

## Timing boundary

Chrome **153.0.8010.48**, headless, fresh process/profile per case, with
`--js-flags=--heap-growing-percent=10` in both variants. Cooperating experiments
use the common lock. Other machine activity is not controlled.

The browser performs all feedback and iteration itself. Page scripts are
prohibited by CSP and execution is disabled. The external Python harness makes
no writes after navigation and supplies neither iteration ticks nor intermediate
answers. It observes the native capture elements through DOM queries every
20 ms. No computed-style or geometry read occurs before native completion.
Browser counters are collected at the timing boundaries; the full numeric
readout occurs afterward.

The navigation interval includes parsing and startup. The second interval
starts at the first *observed* capture; every timed case first observed pass 1,
so it covers the remaining 23 captures. It includes polling, DevTools gaps and
scheduling variation. It is not a precise internal timestamp for each handoff.

Four fresh-process pairs use AB, BA, AB, BA order. A denotes the baseline and
B the selective reader. Times below are **seconds** for 24 passes or the
23-pass continuation, not averages over unrelated cases.

| Pair/order | Navigation baseline → selective | Change | Continuation baseline → selective | Change |
| --- | ---: | ---: | ---: | ---: |
| 1 / AB | 9.912 → 11.785 | +18.9% | 9.344 → 11.368 | +21.7% |
| 2 / BA | 9.616 → 11.802 | +22.7% | 9.061 → 11.403 | +25.9% |
| 3 / AB | 9.708 → 13.438 | +38.4% | 9.154 → 13.049 | +42.5% |
| 4 / BA | 9.819 → 12.589 | +28.2% | 9.270 → 12.197 | +31.6% |

The spread is reported rather than hidden. Four pairs do not provide a formal
confidence interval, but every pair loses in both intervals; this candidate
does not earn a longer full-model trial.

## What the browser counters say

Across the complete navigation interval, **both variants perform 119 style
recalculations and 71 layouts in every timed case**. The selective implementation
does not remove a pass through the browser's update process.

| Pair | Style seconds, baseline → selective | Layout seconds, baseline → selective |
| --- | ---: | ---: |
| 1 | 6.375 → 7.040 | 0.0261 → 0.0273 |
| 2 | 6.235 → 7.058 | 0.0254 → 0.0276 |
| 3 | 6.267 → 7.058 | 0.0259 → 0.0304 |
| 4 | 6.313 → 6.991 | 0.0268 → 0.0264 |

Style work increases in every pair despite fewer active animations. These
counters describe work within the measured interval, not an exclusive additive
decomposition of wall time. Layout arithmetic is cheap in this synthetic page;
that observation cannot be transferred to real matrix-font stages.

The source establishes that the candidate changes its animation lists every
pass, while the default keeps the lists fixed. It also leaves both banks and
the explicit progress forwarding in place. Changing lists and replacing which
properties are animated could offset the savings. This is a **mechanism to
investigate**, not a traced attribution of the slowdown: this experiment did
not isolate animation creation, cancellation, sampling and property propagation.

## Evidence and decision

- [Frozen protocol, source hashes and fixture hashes](manifest.json)
- [Separate correctness gate](gate-r0/results.json)
- [Eight timed runs and browser counters](timing-r0/results.json)
- [Paired timing summary](summary-r0.json)
- [Final hash, coordinate and paired-result audit](audit-r0.json)
- [Independent exact-rational and fixture-difference audit](independent-audit.json)
- [Driver](../../../tools/benchmark_selective_loop.py)
- [Reproduction commands](../README.md)

Source snapshots and all generated pages are retained. No run failed, no
threshold changed, and no production default was modified. The next handoff
idea would need to remove an update cycle or avoid switching reader state;
halving the list of active channels alone has now failed its measured test.
