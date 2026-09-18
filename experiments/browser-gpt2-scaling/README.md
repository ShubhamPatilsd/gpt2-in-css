# Browser GPT-2 scaling investigation — 2026-09-17

Start with [findings and decisions](RESULTS.md), then inspect the
[measurement tables](MEASUREMENTS.md) and [native pipeline report](native-report.md).
This file records the questions, experiment definitions and reproduction protocol.

## Question and scope

Can native Chromium inference do substantially less style/layout work when most
stored state is unchanged? The constraint remains **no runtime JavaScript**.
Python may compile weights/fixtures offline and observe Chromium through CDP.
Externally driven component tests are explicitly separated from autonomous runs.

This is an investigation, not a declaration that scaling has been solved. The
existing font/CSS runtime and all previous results are preserved. New generators
are opt-in; measured variants are never silently promoted into the working demo.

## Baseline evidence

The previous 12-layer, 32-position autonomous run generated 32 reference-matching
tokens in **3177.13 s (52m 57s)**. Median warm interval: **97.69 s**; sampled peak
renderer RSS: **5215.72 MiB**. Approximately 67.97% of warm renderer task time was
style recalculation and 15.10% layout. These are not exclusive wall-clock shares.
One matching trajectory does not establish general model quality.

Source: [original scaling summary](../browser-gpt2/demo-font-vector-context32/scaling-summary.json).

The existing runtime already has a KV cache, one reused transformer graph,
private layer control, a local layer container, some non-inheriting scratch
properties, and an isolated vocabulary head. These must not be presented as
new discoveries. The earlier metric-state isolation ablation had warm medians
of 9.73 s versus 9.43 s for its two-layer control, with higher sampled memory;
that small experiment did not demonstrate a win.

Sources: [control](../browser-gpt2/demo-font-control4/scaling-summary.json),
[metric isolation](../browser-gpt2/demo-font-isolated4/scaling-summary.json).

The earlier rendered-V-width experiment reduced an isolated 32-position attention
measurement from approximately 1.35 s to 0.98 s. This is a component result,
not a 27% end-to-end speedup. Its survival across layer changes is a separate
question. See [implementation](../../tools/browser_gpt2_font_vector_cache.py).

## What can and cannot stay unchanged

| State/work | Lifetime | Desired behavior |
|---|---|---|
| Model weights | Whole run, with different assets selected by layer | Reuse assets; avoid needless style changes |
| Old token K/V | Until its cache slot is overwritten | Retain values without rewriting them |
| A rendered old V at a fixed font location | Until that layer/slot V changes | Reuse shaping; update its scalar weight |
| Query and all attention scores for that query | One layer pass | Recompute; old scores are not reusable |
| Softmax and weighted V sum | One layer pass | Recompute using the retained cache |
| Inactive layers and unpopulated slots | Until selected/populated | Avoid irrelevant work while preserving retained state |
| Residual and MLP activations | One layer pass | Update actual consumers only |
| Completion/version signals | Stage boundary | Preserve freshness without unnecessary propagation |

CSS inheritance is not proof that every value is physically copied. Performance
claims require measurements of style work, layout work, memory and correctness.

## Experiments and hypotheses

| ID | Variant | Change | Expected benefit | Main falsification risk |
|---|---|---|---|---|
| B0 | `baseline` | Existing attention generator, unchanged | Matched control | Harness or environment drift |
| R1 | `widths` | Fixed V font location; weight its intrinsic width | Reuse shaping when query changes | Layer switching replaces V anyway |
| E1 | `empty` | Hide score/value glyphs until a slot is populated | Startup and short prefixes | Lost base-width compensation, inactive timelines |
| S1 | `fields` | Non-inheriting exported cache aliases; explicit forwarding | Score leaves receive K/scale for one slot; V leaves receive V/scale for one slot | Forwarding cost exceeds saving; missing a dependency |
| F1 | `materialize` | Reset raw QKV at the first cache bank, after the baseline has derived axis lists/scales | Stop propagating 2304 raw coordinates within that attention branch | Reset declarations cost more than they save; other branches still inherit QKV |
| C1 | `timelines` | Move attention-internal score timeline scope from root to `.fvs-query` | Narrow scheduling/dependency scope | Changes visibility of a required timeline |
| L1 | `contain-layout` | `contain: size layout` on attention scrollers | Separate layout from paint/style containment effects | Geometry/timeline behavior changes |
| L2 | `contain-none` | Remove containment on the same scrollers | Test whether containment itself costs more than it saves | Expensive global layout or incorrect geometry |
| A1 | `combined` | R1 + E1 + S1 + F1 + C1 | Interactions among independent changes | Individual wins do not add; correctness can regress |
| A2 | `lean` | R1 + E1 + F1 + C1, omitting S1 | Retain useful changes without expensive explicit forwarding | Early-prefix wins may vanish at full context |

S1 narrows the existing rendering graph rather than duplicating it into twelve
heads. Storage/consumer spine elements still relay the active layer's cache.
Thus a passing S1 does **not** establish complete head isolation. A truly separate
head-owned graph requires a correct all-head completion barrier and must pay for
its additional transport. This distinction is tracked explicitly.

The CLI label `materialize` is historical: F1 adds a raw-property lifetime
boundary, while the baseline already derives the axis lists and scales. It is
not a new materialization operator or algebraic fusion of GPT-2 operators.
The baseline already computes scores and softmax on one element and
combines bias, residual addition and GELU into existing output readers. Deeper
fusion must eliminate an actual conversion/barrier; merely renaming variables
cannot count as such a result.

## Correctness contracts

1. Every computed context is compared against an independent NumPy softmax and
   weighted-sum oracle, using the supplied QKV inputs and per-layer cache history.
2. All 768 coordinates must be finite; component RMSE must be below 0.005.
   Maximum absolute error is also saved. This tolerance is inherited from the
   existing attention probe and does not establish full-model quality.
3. Multi-layer component tests write distinct values to each layer, revisit the
   layers, and verify that their retained histories remain separate.
4. Query-only updates change 64 query coordinates and keep every K/V value fixed.
   The other eleven heads are independently checked against their references.
   With more than one layer these are labeled `query+layer-switch`: selecting a
   different layer changes the active font locations even though stored K/V in
   each layer are unchanged. They are not a pure query-locality experiment.
5. Empty slots are excluded from attention exactly as before. Removing their
   positive glyph bases requires adjusting the subtraction in every output row.
6. Completion requires three stable finite reads and a matching native generation
   receipt. A failure is retained in the results, never omitted from averages.
7. No reference output or intermediate Chromium output is written back to the
   page. Component inputs and layer/position controls ARE externally supplied.

## Measurement protocol

- A fresh headless Chromium process/profile per case; record exact browser
  version, arguments and source/fixture SHA-256 hashes.
- Fixed deterministic QKV fixture seed, same inputs across variants.
- `--js-flags=--heap-growing-percent=10` matches earlier controlled runs. No
  `Runtime`, `Debugger` or JS profiler domain is used; CSP disables page scripts.
- Use one browser workload at a time. Reverse variant order on alternating
  repeats. Preserve existing run directories rather than overwriting results.
- Record wall time including CDP writes/reads, settling polls and their ~75 ms
  floor; renderer style/layout duration/count deltas; sampled OS RSS; DOM counts.
- Exclude the first sample from warm summaries. Report append and query-only
  updates separately. A query-only update still changes a generation marker so
  these timings include freshness-control overhead.
- Component timings exclude QKV/output projection, MLP, embedding, final head,
  and autonomous scheduling. They must not be labeled seconds per generated token.
- The driver rewrites the complete body style containing QKV fixture inputs;
  unchanged numerical values may still incur attribute parsing. This is matched
  across variants and deliberately distinct from the separate locality probe,
  which compares an identical input change on root versus its owning subtree.
- Optional traces are separate diagnostic updates, excluded from timed samples.
  Nested trace durations are inclusive and must not be summed into wall time.
- Native multi-layer or full-runtime validation is required before promotion.

## Reproduction

Run from the repository root. `uv` reads the driver's inline dependency list.

```sh
uv run tools/investigate_browser_gpt2_scaling.py --capacity 4 --positions 4 --query-updates 2
uv run tools/investigate_browser_gpt2_scaling.py --variants baseline widths empty fields materialize timelines contain-layout contain-none combined lean --capacity 32 --positions 4 --repeats 2 --query-updates 3
uv run tools/investigate_browser_gpt2_scaling.py --variants baseline widths empty lean --capacity 32 --positions 32 --repeats 2 --query-updates 3
uv run tools/investigate_browser_gpt2_scaling.py --variants baseline widths lean --capacity 8 --positions 8 --layers 2 --repeats 2 --query-updates 3 --trace
uv run tools/investigate_browser_gpt2_scaling.py --variants baseline widths lean --capacity 4 --positions 4 --layers 12 --repeats 1 --query-updates 1 --trace
```

After the early screen rejected `fields`/`combined`, the continued matrix uses
`baseline widths empty lean` at 32 populated slots, `baseline widths lean` for
two-layer/eight-position repeated switching, and the same three variants for
twelve-layer/four-position switching. These are still component experiments.

Each run stores its HTML, CSS, hashes, exact counters, errors, summary and failure
diagnostics under `runs/`. Font assets are referenced in place, not duplicated.
Later driver revisions also snapshot imported measurement/compiler helpers and
record Python/package/platform/seed metadata. Earlier manifests are never
backfilled as though current sources had been used. Existing directories with
different query/trace settings are rejected, rather than silently substituted.
The baseline compiler is [browser_gpt2_font_vector_cache.py](../../tools/browser_gpt2_font_vector_cache.py).
The opt-in ablations are [browser_gpt2_scaling_variants.py](../../tools/browser_gpt2_scaling_variants.py).
The driver is [investigate_browser_gpt2_scaling.py](../../tools/investigate_browser_gpt2_scaling.py).

## Decision criteria

- **Correctness first:** a faster variant that loses slots, crosses layer histories,
  produces stale contexts, or stalls is rejected.
- **Early versus full context:** E1 is expected to help only unfilled capacity.
  Report fully populated runs separately; never extrapolate early savings.
- **Rendering locality:** narrower property exposure is useful only if browser
  work or memory falls. DOM/property counts alone are insufficient evidence.
- **System effect:** advance promising changes through native layer feedback and
  the existing full pipeline. Stop promoting a component gain when the complete
  system regresses or remains inconclusive.
- **Scaling is a curve:** compare 4, 8 and 32 allocated/populated slots and layer
  revisits. Do not call one small test a scaling solution.

## Browser references and limits

- [Chrome: registered-property performance](https://web.dev/blog/at-property-performance)
  supports testing non-inheriting state; its microbenchmark speedups cannot be
  applied directly to this workload.
- [CSS containment](https://www.w3.org/TR/css-contain-2/): `contain: style` does not
  block general custom-property inheritance. Size/layout/paint containment have
  distinct effects and may affect the geometry used to compute numbers here.
- [Chrome: selector statistics](https://developer.chrome.com/docs/devtools/performance/selector-stats)
  can help diagnose style work, but instrumented timings need separate treatment.

## Work log

- Started after reviewing the previous task, current compilers and saved reports.
- Repository already contains substantial uncommitted experimental work; existing
  sources and runs are preserved. No production default is changed.
- Initial free disk space was ~2.4 GiB. With user authorization, `uv cache prune`
  removed 2.8 GiB of unused package cache. No model, source, measurement, or git
  data was deleted. All new fixtures reuse existing fonts.
- Implemented B0/R1/E1/S1/F1/C1/L1/L2/A1 and began the four-slot correctness screen.
- All nine initial variants passed all six four-slot numerical samples. S1 and
  A1 were slower; added A2 to measure the combination without explicit forwarding.
- Completed two reversed-order screens with 32 allocated slots and four populated
  positions. All 20 runs passed. S1/A1 substantially regress; A2 improves early
  component latency. Those runs covered early prefixes only.
- User requested maximum available subagents. Three handled locality diagnostics,
  native pipeline validation, and independent analysis/documentation. Browser
  workloads were serialized; the source-scan contention exception is recorded below.
- Independent review found and fixed evidence-handling issues: compilation
  failures now produce reports, optional trace validity is checked separately,
  mismatched reruns are rejected, and invalid zero/negative arguments fail fast.
  Regression tests exercise these failure paths without launching Chromium.
- Locality agent completed 24 timing cases plus 12 independent traces. Input
  ownership reduced collateral style updates; unchanged heads were already
  avoiding redundant shaping in this diagnostic. See its report for exact counts.
- The first four native two-layer/four-position cases all matched their reference
  tokens/cache state with zero post-navigation writes. These are truncated-model
  integration checks, not full GPT-2 quality or steady-state throughput evidence.
- Completed eight full-capacity component runs, each checking all 32 appends and
  three fixed-cache query updates. Rendered-width reuse reduced the final append
  by about 28%; empty-slot gating provided no full-occupancy benefit.
- Completed six two-layer/eight-position and three twelve-layer/four-position
  component runs. All 312 contexts and nine separate trace updates passed.
  Append gains survived, but query/layer-switch gains were weak or absent.
- Initial twelve-layer native baseline/lean runs both passed token/cache checks.
  Lean took 91.97 s versus 82.73 s, a regression that triggered separate native
  single-factor ablations. All four additional cases passed; raw-QKV reset was
  a plausible contributor to the extra style cost, while width reuse looked faster.
- Native local-commit follow-up passed nine A→B→A commits across three processes.
  Held inputs/results survived upstream source poisoning with zero writes; the
  strongest delayed-observation run completed before its first computed-style
  read. This is mechanism validation, not a production performance comparison.
- Tested width reuse against fresh twelve-layer/four-token controls twice in
  opposite orders. The first pair was 6.3% faster; the reversed pair was 13.7%
  slower. Neither native time nor sampled memory showed a repeatable advantage.
- One earlier four-token baseline overlapped a CPU-heavy documentation scan.
  Its correctness passed, but its timing was explicitly excluded and replaced.
  Original results and the incident record remain in the native evidence directory.
- Added the missing twelve-layer component test for raw-QKV reset. All 60 contexts
  and its diagnostic trace passed, with nearly neutral timing/style cost. It did
  not reproduce the native result under the component protocol.
- Final browser inventory: 47 attention cases, 24 completed locality timing cases,
  15 native integration cases (one timing excluded), and three native local-commit
  processes. A failed locality browser startup is separately preserved.
- Added a standalone scaling figure and hash-preserved plotting data. Final lint
  cleanup is documented separately from measured source versions; exact pre-cleanup
  bytes are saved in [source-before-final-lint](source-before-final-lint/manifest.json).

Results and subsequent decisions are recorded in [RESULTS.md](RESULTS.md).
