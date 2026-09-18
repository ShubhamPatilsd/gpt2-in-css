# A matched connected MLP test, with limits on runtime prediction

The connected avar2 candidate does not earn a model replacement on this test.
On first visits to changed inputs, layer 0 is 17–19% slower than the current
native MLP, and its sampled renderer memory is about 1.8 times as large. At
layer 1, the candidate fails the downstream error bound. No production backend
changed and no full 32-token run was launched. All browser experiments in this
task, including failed attempts and correctness runs, took about 5.9 minutes.

## What was connected

Each page calculates the following in the browser, with author JavaScript disabled:

```
real post-attention residual, 768 values
 → the layer's LN2
 → FC, 768 to 3,072
 → GELU
 → projection, 3,072 to 768
 → projection bias and residual addition
 → the next layer's LN1
 → a final width depending on all 768 normalized values
```

The harness selects raw residual inputs from a four-token quantized GPT-2
trajectory and advances a generation number. It never supplies normalized
vectors, hidden activations, or MLP answers. Every returned state coordinate and
every next-LN coordinate is checked. The terminal must have the new generation
and remain unchanged during the full-vector verification.

This is **two separate layer-segment replays**, for layers 0 and 1. They are not
two layers connected to each other or to autoregressive feedback. Attention,
cache history, the vocabulary head, all-layer selection, and token feedback are
outside the timed graph. Layer 1 inputs come from the reference trajectory,
not from the candidate layer-0 page. The exact implementation and differences
from the native core are in [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md).

An earlier [connected prototype](../avar2-gelu-linear-hvar-full-mlp/CONNECTED_RESULTS.md)
already demonstrated normalization/residual/next-layer connections. The earlier
recommendation missed that report. The new contribution is a matched comparison
against the current reusable token core's own FC/GELU/projection stages. The
old isolated 251 ms measurement is not a current connected latency estimate.

## Correctness findings and the acceptance change

Both implementations share row-quantized 9-bit FC weights. Their later arithmetic
differs: the baseline uses exact CSS GELU and 9-bit projection weights; the
candidate uses piecewise GELU and existing linear variable-font projection
assets. We therefore compare each to its own mathematical oracle and separately
to a shared exact-GELU/float-projection target. That common target still uses
quantized FC weights and is not full unquantized GPT-2.

The first screen required state maximum absolute error at most 0.1 and next-LN
maximum absolute error at most 0.01. Both implementations failed the state bound
at layer 1. These failures remain; we did not fix or explain away the absolute
discrepancy. The revised diagnostic policy explicitly adopts the existing native
core's state RMSE < 0.05 criterion, with finite coordinates and the unchanged
next-LN maximum bound of 0.01. The original and revised manifests preserve the
same HTML, inputs, oracles, and font hashes. [Protocol amendments](PLAN.md).

The [complete revised gate](correctness-v2.json) still fails for the candidate
at layer 1, on the second input. Its next-LN maximum error is 0.011310, above
the retained 0.01 bound. State RMSE is 0.01637, so a test looking only at the
MLP's aggregate state error would have missed this downstream failure. No
threshold was changed in response to that failure, and layer 1 is not timed.

Independent recalculation of LN1 using the candidate's actual browser state
agrees with the observed consumer to maximum error 0.000131. This supports a
functioning connection: error entering the consumer, rather than a missing or
stale consumer, accounts for most of its discrepancy with the ideal oracle.

The comparison with the common target also matters. Across the completed gate
observations, worst state RMSE is 0.01665 for baseline layer 0 and 0.02645 for
candidate layer 0. At layer 1 it is 0.02112 for the baseline and 0.05108 for
the candidate's two observed cases. The candidate's piecewise arithmetic is
therefore not interchangeable with the baseline merely because each can meet
an implementation-specific error check. These few states do not establish
full-model token quality.

## Short matched timings

All times below are milliseconds for one complete layer-0 segment update, from
selecting its raw residual input through the final dependent read. Every process
is fresh and has only one benchmark page. AB runs baseline before candidate;
BA reverses the order. A cell is that process's upper-middle sample median.

| Input schedule | Pair order | Current native MLP | Candidate | Candidate change |
| --- | --- | ---: | ---: | ---: |
| Four states repeatedly revisited | AB | 835.3 | 850.8 | +1.9% |
| Four states repeatedly revisited | BA | 772.7 | 1,048.2 | +35.7% |
| First visits to changed states | AB | 930.1 | 1,104.0 | +18.7% |
| First visits to changed states | BA | 931.3 | 1,091.2 | +17.2% |

The [repeated-state schedule](timing-layer0-replay.json) has two warmups and
eight measured updates per process. The [first-visit schedule](timing-layer0-first-visit.json)
warms only case 0 twice, then measures cases 1, 2, and 3 once each, reversing
their order in the second pair. It has twelve measured first-visit observations
in total, representing only three distinct input vectors repeated across fresh
processes. Its individual samples range from 904.9 to 941.8 ms for the baseline
and 1,080.5 to 1,191.1 ms for the candidate. These ranges are observations, not
confidence intervals or guarantees for arbitrary input states.

Cached revisits can look much better: individual candidate updates in the
repeated-state schedule fall as low as 411.7 ms. Its roughly 1.1-second fresh
updates reveal why using that cached minimum as a new-token estimate would be
misleading. Both paired schedules have identical inputs across their compared
backends. Neither shows a repeatable candidate advantage.

The [final layer-0 gate](correctness-layer0-final.json) checks 16 generations,
including A→B→A revisits, with 24,576 state/next-LN coordinate comparisons.
The two timing schedules check another 60 generations and 92,160 coordinates,
including warmups. All satisfy policy v2 and every timed terminal remains
unchanged during verification. An independent audit recomputed the gate errors
from raw vectors and the timing medians from raw samples; the saved manifest,
font, HTML and harness hashes match.

### Memory, startup, and observation cost

The first-visit runs sample 1,011–1,012 MiB of total renderer RSS for baseline
processes and 1,849–1,862 MiB for candidate processes. The pages contain 8,483
and 17,322 elements respectively. RSS is summed over renderer processes reported
by that fresh browser, sampled after updates; this is not a continuous peak or
a direct comparison to the historical model's single-renderer measurement.

Navigation plus explicit font preload takes 2.302–2.332 seconds for baseline and
2.746–2.753 seconds for candidate in the first-visit runs. These are setup costs,
excluded from update timing; this segment uses an external preload rather than
the production runtime's native loading barrier.

The timed interval includes external polling and DevTools round-trip gaps.
Baseline first-visit updates complete on the second observation, candidate on
the first; the polling delay is 16 ms. The external wrapper adds about 1.1–1.4 ms
median beyond the recorded browser interval. We do not subtract an assumed
polling cost to claim pure computation time.

Reading and checking all 1,536 diagnostic widths occurs after the timer. It is
substantial: about 300–306 ms median for baseline and 1,145–1,154 ms for candidate
in the first-visit runs. Those extra observations can affect browser scheduling
and cache state and are not called exclusive model-stage work. The timed final
scalar depends on all state coordinates through the next LayerNorm reductions,
and its unchanged value after full verification guards against recording a
stale completion before that later readout.

The completed timing invocations took about 123.6 seconds in total, including
loading and verification. Adding correctness gates and preserved failed attempts
brings total browser experiment wall time to about 353.9 seconds. Preparation,
analysis and documentation time are not included in that number.

## What the runtime-estimation scaffold can establish

The [estimator](../../tools/estimate_native_mlp_runtime.py) runs without launching
a browser. It uses the existing complete capacity-32 trajectory, fits only early
continuing-token intervals, and evaluates predictions on the withheld later
continuing tokens. It does not fit the full run and then call that a forecast.
The actual saved total is 3,177.132 seconds, about 52.95 minutes.

| Information used for fit | Forecast model | Withheld continuing-time error |
| --- | --- | ---: |
| Continuing tokens 2–4 | Constant time per token | −42.0% |
| Continuing tokens 2–4 | Linear growth with context | −7.9% |
| Continuing tokens 2–8 | Linear growth with context | +9.3% |
| Continuing tokens 2–12 | Linear growth with context | +9.0% |
| Continuing tokens 2–16 | Linear growth with context | +1.0% |

Using the observed startup and an explicitly uncalibrated terminal-token proxy,
the four-token constant model estimates 32.41 minutes; the linear model estimates
49.26 minutes. The eight-token linear fit estimates 57.34 minutes. The early
linear forecasts are informative on this historical run, but their spread is
not a confidence interval or evidence of accuracy for a new backend.

Allocation also matters. For the same early token epochs, the old capacity-32
run's mean latency is about 1.26 times the capacity-8 run's. Those were separate
historical runs with other differences, so this is not a causal estimate of
capacity cost. It shows why a four-slot timing cannot simply stand in for the
beginning of a 32-slot run.

The [machine-readable backtest](runtime-estimation.json) retains source hashes,
every held-out prediction, initialization/terminal exclusions, and a calibration
specification. It leaves the candidate's full-run prediction empty. The missing
native-loop effects are not measured by multiplying a segment time by twelve
layers and 32 tokens.

A credible short calibration would keep all twelve layers and 32 allocated
slots resident, measure continuing-token windows at low/middle/high occupancy,
and validate a forecast on held-out contexts. Checkpoint restoration could avoid
generating every preceding token, but must restore and verify the real cache and
generation state outside timing. The current estimator documents that interface;
it does **not** implement a native checkpoint-resume runner. A candidate that
fails the connected quality check should not trigger that more expensive work.

We did implement a smaller [bounded prefix observer](../../tools/benchmark_native_token_prefix.py)
that leaves the existing 32-slot page unchanged and stops after a requested
number of observed tokens. Its default browser heap flag and navigation-time
origin match the saved long-run protocol. A parent watchdog bounds the complete
worker, and outputs go to a new directory. This gives a concrete way to collect
four-token timing on the full allocation rather than a misleading four-slot
replacement.

This new observer has **offline validation only**: syntax, argument checks,
unchanged-graph dry run, fresh-output enforcement, and process-group timeout
behavior. It has not been run against the full native model. It also does not
independently validate numerical state. The estimator accepts its report directly
through `--calibration`, rejects incompatible/incomplete/nonfinite reports, and
labels the resulting forecast diagnostic until numerical and later-context
validation exist. Feeding saved first-four-token observations through this same
interface reproduces the backtest figures above. The offline
[observer checks](prefix-scaffold-offline-checks.json) and
[estimator checks](calibration-scaffold-check.json) retain these distinctions.

Because this candidate is slower at the accepted first layer and fails the next
layer's accuracy check, we stop at the short comparison. An additional full-model
run or a precise projected candidate token time would not be justified by these
results. The last measured model time remains the historical 52.95-minute run.

## Reproduction and preserved attempts

[README.md](README.md) contains the build, gate, timing, and offline-estimator
commands. The first smoke run's completion observer stalled with page scripts
disabled; the revised bounded external polling observer is disclosed in the
timing protocol. Original strict-error failures, the passing layer-0 gates, and
the failed full revised gate remain alongside their source/manifest snapshots.
All timing reports must use a passing gate with matching manifest, harness,
HTML, and font hashes. Font preload and full-vector serialization are outside
the update timer; external polling and browser-protocol gaps are inside it.
