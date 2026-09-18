# Native stage cost evidence

The saved records place most observed continuing-token time between embedding readiness and the final core-to-head input handoff. They do not establish how much of that interval belongs to QKV, attention, MLP, transport, or vocabulary work triggered by a shared renderer update. The separate receipt diagnostic is intended to locate those costs.

Reproduce the saved-data extraction with `uv run tools/profile_browser_gpt2_stage_costs.py extract`. No browser is launched. [Machine-readable rows](profiling/saved-stage-costs.json) retain each source hash, rejected epoch, token-boundary renderer counter, and timing exclusion.

## Matched saved geometry spans

These are observations after CDP reads return, not exclusive stage execution times. The old core marker appears only for some epochs; this table uses the distinct, retained head-input marker and matches the full boundary sequence within each token. Token 4 is terminal and is kept separate. The contaminated baseline r0 is excluded from timing.

| Case | Token epochs | Feedback + embedding (s) | Embedding → head input (s) | Head input → head (s) | Head → capture (s) | Total observed span (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| baseline-b12-c4-r1 | 4 | 2.824 | 31.382 | 1.194 | 0.284 | 35.685 |
| widths-b12-c4-r1 | 4 | 4.767 | 38.600 | 0.052 | 0.007 | 43.426 |
| baseline-b12-c4-r2 | 2, 3 | 2.509 | 34.157 | 1.494 | 0.346 | 38.506 |
| baseline-b12-c4-r2 | 4 | 3.171 | 38.790 | 2.522 | 0.320 | 44.801 |
| widths-b12-c4-r2 | 2, 3 | 2.551 | 31.167 | 1.160 | 0.337 | 35.215 |
| widths-b12-c4-r2 | 4 | 3.147 | 36.930 | 2.262 | 0.300 | 42.639 |

Rows average only the displayed token epochs within one process. They are not independent repeated samples. Pair r1 and pair r2 have opposite overall performance directions; these spans do not turn that into a repeatable speedup.

Matched whole-token renderer counters for continuing tokens 2 and 3 in pair r2 give the following shares. These counters have different boundaries from the geometry spans above; they cannot be mapped onto individual stages.

| Case | Style / task | Layout / task | Other / task | DevTools / task |
| --- | ---: | ---: | ---: | ---: |
| baseline-b12-c4-r2 | 52.57% | 15.25% | 32.11% | 0.07% |
| widths-b12-c4-r2 | 51.24% | 15.66% | 33.02% | 0.07% |

## What the existing evidence can and cannot rank

1. **Highest observed span: the reusable core and its handoff.** On continuing tokens 2 and 3, this is the interval from embedding to head-input readiness. It includes twelve passes through LN1, QKV, native attention, attention projection, LN2, FC/GELU, MLP projection and residual feedback, plus final transport. The receipt diagnostic below attempts to split this combined interval at fresh pass receipts, but does not obtain complete coverage.
2. **Style work is material at token scale.** Saved token-boundary counters report renderer style and layout work across complete token intervals. Their shares cannot be assigned to a projection or vocabulary stage without intermediate counter observations.
3. **Vocabulary has an observable readiness tail, but its total cost is not isolated.** A small head-input-to-head span cannot establish that the 50,257-row head is cheap: the read exposing head-input geometry can already have flushed head work. The head-input observer itself reports a retained input epoch, not a command to start vocabulary execution.

## Fresh receipt diagnostic protocol

Prepare an HTML clone of the clean twelve-layer, four-slot baseline with `uv run tools/profile_browser_gpt2_stage_costs.py prepare`. Preparation retains the exact baseline CSS through an absolute stylesheet link and adds six tiny geometry witnesses inside existing native input/receipt gates. They expose the actual pass epoch only while the corresponding gate is open: core input, QKV, attention context transport, attention output projection, FC/GELU, and MLP output projection. No arithmetic, animation, container, or scheduling rule changes. The generation marker travels through the existing matrix receipt, so stale widths cannot be credited to a newer pass.

After the coordinator grants the serialized browser slot, run `uv run tools/profile_browser_gpt2_stage_costs.py run --target-tokens 2 --limit-seconds 180`. A fresh headless Chromium runs with page JavaScript disabled and the same heap flag as the native measurements. Only CDP geometry and performance reads observe progress after navigation. It stops after observing two captured tokens, or the explicit time limit, without supplying an input or intermediate result. Native generation can already have entered token 3 before the observer sees capture 2. Geometry at the retained capture witness supplies the token check against the preserved baseline; the baseline's separate residual validation remains baseline evidence, and no fresh residual check is claimed here.

Each new receipt observation saves the CDP call start/end timestamps and a renderer-counter snapshot. The observer polls the six small receipts plus three existing head/capture witnesses sequentially, then sleeps 50 ms. It retains at most 2,000 distinct stage events and writes compact JSON; no trace file is collected. A missed, reset, or nonmonotonic receipt is reported rather than filled in. Counter deltas include work flushed by the observer, and different stage receipts may be exposed during the same frame; resulting stage spans are diagnostic and cannot be presented as uncontaminated benchmarks. Geometry read latency and unassigned/missing boundaries accompany the result.

Source and method limits: observing a receipt establishes freshness, not that all work executed strictly before that read. The FC receipt includes bias and GELU in its fused CSS consumer; the attention-projection and MLP-projection intervals include their residual additions and readback. Math and transfer are therefore still combined until a separately validated ablation distinguishes them. No per-layer optimization recommendation will be claimed from a missing receipt.

## Fresh diagnostic result

The diagnostic captured the expected tokens **11 and 314** with zero post-navigation writes. It reached the second observed capture at 2 tokens; the last geometry event was at 105.601 seconds. This is a diagnostic run with additional observers, not a matched throughput benchmark. [Raw observations](profiling/receipt-diagnostic/results.json), [coverage and matched pairs](profiling/receipt-diagnostic/analysis.json), and [method review](profiling/methodological-review.md) are retained.

Coverage is insufficient for a native stage decomposition: **0 of 24 passes have all six witnesses observed**. There were 70 total fresh stage/head/capture events, including 4 core events beyond pass 24. Native token 3 had already started before capture 2 was read. Those later events are excluded below. The head-completion witness was never caught, so there is no fresh vocabulary interval estimate.

| Witness | Observed passes within 1–24 | Coverage |
| --- | --- | ---: |
| input | 1, 4, 6, 8, 11, 13, 15, 18, 20, 22, 24 | 11/24 |
| qkv | 2, 4, 6, 8, 11, 13, 15, 18, 20, 22, 24 | 11/24 |
| context | 2, 4, 7, 9, 11, 14, 16, 18, 20, 23 | 10/24 |
| attentionProjection | 2, 5, 7, 9, 11, 14, 16, 18, 21, 23 | 10/24 |
| fc | 3, 5, 7, 9, 12, 14, 16, 19, 21, 23 | 10/24 |
| projection | 3, 5, 7, 10, 12, 14, 17, 19, 21, 23 | 10/24 |

The 99 geometry calls took a median 436.8 ms, maximum 5.685 s, and a combined 59.961 s of call wall time. That wall time is not observer CPU overhead: it includes waiting for and flushing native browser work. A final-pass projection read lasted 5.685 s and returned near head readiness, demonstrating why that delay cannot be labeled exclusive MLP projection cost.

The following same-pass intervals have both endpoints observed in chronological order. Their pass sets differ and are selected by observability. They are diagnostic samples, **not comparable stage proportions**, and must not be added together.

| Observation interval | Matched passes | Median (ms) | Min–max (ms) |
| --- | --- | ---: | ---: |
| input → qkv | 4, 6, 8, 11, 13, 15, 18, 20, 22, 24 | 482.1 | 151.5–1478.9 |
| qkv → context | 2, 4, 11, 18, 20 | 869.3 | 314.1–1321.2 |
| context → attentionProjection | 2, 7, 9, 11, 14, 16, 18, 23 | 1443.0 | 337.1–1988.8 |
| attentionProjection → fc | 5, 7, 9, 14, 16, 21, 23 | 606.2 | 349.6–2495.4 |
| fc → projection | 3, 5, 7, 12, 14, 19, 21, 23 | 558.5 | 369.6–9940.3 |

**Actionable conclusion:** use isolated, numerically checked QKV and LN2→FC/GELU→projection ablations to compare dense changes. This experiment did not yield a defensible ranking of native QKV, MLP and vocabulary cost. A single aggregate pass/phase witness could reduce sequential polling, but it would require a separate diagnostic and would still not establish exclusive CPU attribution. No such follow-up is included here.
