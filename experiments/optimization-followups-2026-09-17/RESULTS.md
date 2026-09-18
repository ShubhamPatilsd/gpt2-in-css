**Optimization follow-ups — September 17–18, 2026**

Working report; the final native comparisons and bounded follow-ups are still running. The completed evidence below is retained independently of the pending conclusions.

This follows the [repository audit](../repo-optimization-audit-2026-09-17/AUDIT.md). That audit inventoried 407 experiment directories and traced the historical acceptance/rejection evidence. This follow-up executes its unresolved proposals, refines promising candidates, and tests their interaction in the current native runtime. It does not rerun all historical experiments or establish a global optimum.

**Method and interpretation**

All browser tests use stock Chrome 153.0.8010.48 on the same M2 Pro Mac, fresh browser profiles, heap growth 10%, and disabled page JavaScript. The Python/CDP harness also executes no JavaScript. Component experiments supply inputs externally; native prefix experiments supply no activations or token ticks after Run. Heavy experiments share one advisory lock and single-threaded BLAS settings. The user chose to continue on battery. Ordinary machine activity, thermal state and battery state remain uncontrolled; opposite-order repeats reduce, but do not eliminate, these confounds.

Timing differences below compare matched current-source controls. A component gain is not a token-speed gain. In particular, do not add the dense-stage and lifecycle percentages together. The [protocol](PROTOCOL.md) records initial gates and later refinements before the corresponding runs. Raw results, source snapshots, input/reference hashes and failed attempts are preserved under this directory.

**Correction: the interrupted runs coincided with display-off/sleep**

The user correctly challenged the earlier description of a browser failure. The [power record](power-interruption.json) and [underlying log](power-events.txt) show:

| Interrupted case | Lost connection, PDT | Display turned off, PDT | Interpretation |
|---|---|---|---|
| Loop, first order, static readers plus local scope | 22:45:47 | 22:45:47 | System sleep followed at 22:45:52. |
| Head, reverse order, settings | 23:02:53 | 23:02:52 | Display transition coincides; no full system-sleep event recorded here. |
| Head, reverse order, baseline | 23:05:24 | 23:05:23 | System sleep followed at 23:05:28. |

These are environment interruptions, not evidence of candidate defects. A loop case that completed across sleep retains its numerical result but loses its timing eligibility. Conservatively exclude the entire original loop timing pairs 0/1 and head pair 1 from paired timing conclusions. Original loop pairs 2/3 and the initial dense window are unaffected. Temporary `caffeinate -di` protects the replacement runs. The head retry uses eight fixed original indices, `0,1,5,10,15,20,30,37`, in all three modes; the first full sweep already checked all 38 inputs. This distinction is necessary when comparing coverage or medians.

**Dense consumers: chunk size was worth revisiting**

The initial sweep covers layers 0 and 11, QKV and the complete LN2→FC→GELU→projection stage, six states per case, two opposite process orders, and both fresh states and layer revisits. All 84 complete-stage samples pass, including 119,808 coordinate comparisons with exactly zero difference from baseline. These tests retain the pre-existing 0.05 RMSE reference gate and require candidate/baseline differences no greater than 1e-6.

| Change versus chunk 512 | Fresh QKV, order 1 / 2 | Fresh full MLP, order 1 / 2 | Revisit result |
|---|---:|---:|---|
| Chunk 128 | −18.81% / −15.60% | −14.26% / −14.71% | QKV −21.76% / −20.75%; MLP −7.89% / −9.73%. |
| Chunk 256 | −9.96% / −9.29% | −9.81% / −10.05% | Smaller repeatable savings than 128. |
| Projection settings only | Not applicable | −0.35% / −1.34% | MLP +1.12% / +0.53%; neutral overall. |

Fresh QKV medians move from about 335–338 ms to 272–285 ms; MLP moves from about 771–772 ms to 657–662 ms. These include the harness's 75 ms minimum settling wait. Cold gains are much smaller. In the MLP runs, sampled renderer peak drops from about 1,141 MiB to 1,023–1,024 MiB. See [dense summary](dense/summary.json) and [paired changes](dense/paired-summary.json).

The renderer performs the same number of style/layout updates. For example, across the three fresh updates in the first order, QKV task duration drops from 0.781 s to 0.616 s, while style is 0.240→0.234 s and layout 0.146→0.152 s. MLP task duration is 2.151→1.860 s, style 0.841→0.812 s and layout 0.419→0.411 s. Much of the reduction is in the residual `TaskOtherDuration` counter. This does not identify a specific exclusive animation or font cost without a trace.

The subsequent 32/64/128 sweep also preserves all output coordinates. Its predeclared selection rule requires a smaller chunk to improve fresh medians by at least 2% in both stages and both orders, with no revisit penalty over 2%. Only 128 qualifies. Size 64 offers small fresh gains but misses the QKV threshold and worsens one MLP revisit by about 3.9%; size 32 is mixed. Thus 128 is the locally supported integration candidate, not a universal optimum. [Refinement measurements](dense-refinement/summary.json), [selection](dense-refinement/selection.json).

**Lifecycle: static bank readers help the recurrence fixture**

The alternative gives each saved bank a fixed reader list instead of replacing the selected animation list each pass. A separate experiment narrows the residual timeline scope; their combination is also tested. All four designs pass the 1/2/3/4/8/24-pass correctness gates, including all 768 live values, retained banks and generation stamps: 24 gate cases and 73,728 coordinate checks.

In the two original timing pairs unaffected by sleep, static readers improve the 23-continuation window by 8.99% and 9.82%. Local scope alone changes it by +1.13% and −0.22%, which is neutral. The combination improves it by 8.52% and 9.56%, with no evidence that local scope adds a benefit. Baseline continuation time is roughly 9.2 s; static readers take roughly 8.35 s. Style/layout cycle counts remain essentially unchanged: this reduces work per cycle, rather than removing an acknowledgement cycle. [Gate results](loop/gates.json), [original timing](loop/summary.json). Replacement awake controls are reported separately below.

**Normalization: the low-variance fallback repairs the offline gate**

The algebra centers before the font, using `z = gamma * (x - mean)` and `Qz / sigma + Qbeta + bias`, while retaining the original q9 matrices. The initial audit passed 1,846 of 1,848 sensitivity checks; the remaining two were low-variance cases. This follow-up uses the legacy path whenever `sigma < 1/8` and keeps the original numerical gates unchanged.

All 1,848 checks now pass: 308 cases under six rounding models, spanning layers 0/5/11 and QKV/FC. The fallback covers 88 distinct stress cases and zero natural cases; all 44 natural cases use the centered formula. The worst candidate error against the ideal q9 output is about 0.001829 RMSE. This is the same regression set, not held-out validation. Passing it establishes numerical eligibility for browser checks, not speed or general accuracy. [Complete offline results](normalization/centered-normalization-results.json).

The browser comparison includes denominator hoisting alone, to distinguish a simpler repeated-expression change from the full algebraic rearrangement. It uses real layers 0/11 and complete QKV/MLP stages with six states and both orders. Hoisting has an exact-baseline gate; the centered candidate must preserve the existing absolute gate and avoid more than 10% plus 1e-5 degradation in RMSE and maximum error against the q9 reference. This browser reference differs from the offline relative-to-float policy and is recorded explicitly.

**Reproducibility: a validated bundle is now an identifiable set of bytes**

The [frozen registry](validated-bundles.json) hashes the actual preserved 8-output and 32-output bundles, all transitive static assets, manifests and saved numerical evidence. Each capacity checks 268 files. The [recipe](VALIDATED_RECIPE.md) gives verification and launch commands, as well as explicit current-source compiler flags.

The distinction matters: the preserved complete-run bundles use font-vector operator v1; current source with the same broad architecture uses v2. The default compiler flags also do not select the strongest reusable graph. New native comparisons therefore use a freshly compiled v2 baseline and matching candidates. They are not compared causally against the historical v1 timings.

Historical complete-run evidence remains 8/8 outputs at 402.672 s and 32/32 at 3,177.132 s, matching both quantized and original-float winners for the saved `Hello` continuation. Those single historical runs remain the full-completion evidence, not proof of general model quality or the speed of a new candidate.

**Attempts preserved for diagnosis**

The initial dense compiler adapter addressed the wrong positional argument; the normalization adapter initially failed to match scientific-notation bias constants; the first full-input fusion attempt hit a helper's 256-axis guard before reaching the browser. These are harness/build failures, not negative measurements of the proposed techniques. Their exception logs and source snapshots are retained. Each repair uses fresh artifacts.

The original static-reader native attempt times out at360seconds without a capture. Its read-only diagnostic records the font-ready marker but no Run latch, so startup was not verified. This cannot establish a candidate progress failure. The corrected observer explicitly verifies font readiness, the checkbox and Run latch before observing captures. Original raw evidence stays excluded from speed comparisons; corrected trials and their startup-policy difference are recorded below.

The first persistent-V design produces real nonzero glyph widths, but the context consumers receive the anchor fallback across the layout boundary and fail immediately (RMSE 13.156, maximum 31.367). This diagnoses delivery wiring, not the impossibility of persistent rendered V. The repair places the persistent glyphs inside the context track while retaining separate layer ownership; its independent result is reported below.

The first sticky-boundary diagnostic retains five of six stage witnesses for every one of 24 layer passes, but zero complete passes. Its context witness used the wrong container name. The corrected diagnostic uses the actual `cache-bridge` container and zero-duration witness pulses. These diagnostics modify the graph and are excluded from speed comparisons even if they pass numerical checks.

<!-- FINAL_FOLLOWUP_RESULTS -->
