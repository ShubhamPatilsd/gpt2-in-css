# Geometry attention with a live GPT-2 MLP tail

This experiment asks whether the shallow-sibling attention win survives when
its 768-value residual directly drives the rest of a transformer block.

The connected page contains real block-0 multi-token attention and output
projection followed by a real GPT-2 block-1 `LN2 -> 768x3072 FC -> GELU ->
3072x768 projection -> residual` tail. Using block-1 tail weights makes this a
structural hybrid rather than an exact checkpoint block, but preserves the
real dimensions, weights, nonlinearities, and dependency shape needed for the
scaling test. Runtime pages contain no JavaScript.

## Direct connection

The numerical reference mirrors the font-weight quantization and four-hidden-
values-per-timeline encoding. Five-round warm medians were used through 16
tokens; the 32-token point used three rounds.

| Context | Attention | Isolated MLP tail | Direct connected | Dependency premium | Connected RMSE |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 0.965 s | 1.034 s | 2.963 s | 0.964 s | 0.0274 |
| 8 | 2.092 s | 1.040 s | 4.299 s | 1.167 s | 0.0338 |
| 16 | 3.961 s | 1.029 s | 6.822 s | 1.831 s | 0.0288 |
| 32 | 10.393 s | 1.102 s | 14.194 s | 2.699 s | 0.0292 |

The isolated tail is nearly constant because it always handles one 768-value
state. The direct connection costs substantially more than attention plus the
isolated tail, and that excess grows with the upstream context graph. This is
direct evidence that dependency traversal across stages is a scaling cost, not
only the number of matrix operations.

Layer normalization remained accurate (connected RMSE below 0.00023), and the
3,072 packed hidden values remained accurate (RMSE below 0.00137). The larger
final error comes from the existing packed output-projection transport.

## Explicit timeline boundary

A second page materializes all 768 attention outputs through fresh view
timelines before starting the MLP. It is accurate but slower:

| Context | Direct | Materialized boundary | Boundary penalty |
| ---: | ---: | ---: | ---: |
| 2 | 2.948 s | 3.090 s | +0.142 s |
| 8 | 4.277 s | 5.135 s | +0.857 s |
| 16 | 6.713 s | 8.991 s | +2.277 s |

The extra 768 timelines do not isolate the graph cheaply. Their own animation,
layout, and decoding work compounds with the upstream dependency graph. Keep
the direct inherited custom-property connection; reject timeline
materialization as a stage boundary.

## Packed boundary variants

Three attempts reduced the number of boundary timelines:

- Four 9-bit values in each two-dimensional carrier use 192 timelines. This
  occasionally saved about 0.4 seconds at eight tokens, but lost the gain at
  sixteen tokens and raised final RMSE to 0.055-0.094.
- Two nominally 12-bit values packed into one width use 384 timelines, but the
  resulting 16.7-million-pixel coordinate loses low-order digits in timeline
  progress. Its two-token final RMSE was 0.132, so nominal bit depth did not
  survive the geometry transport.
- Two independent 12-bit values stored in `left` and `width` use 384 elements
  and timelines. This preserves useful accuracy (0.031-0.033 RMSE), but is
  0.430 seconds slower than direct inheritance at eight tokens and 1.119
  seconds slower at sixteen.

This separates the costs: lowering timeline count alone is insufficient, and
large scalar coordinates cannot safely serve as packed integers. A useful
future boundary must reduce timelines, layout boxes, and decode expressions at
the same time. Until then, no boundary is faster than direct inheritance.

## Phase-gating the MLP

Two CSS-only gates tried to keep the MLP subtree out of layout until the final
attention-projection timeline had resolved. The first used
`content-visibility` plus a one-millisecond state animation. The stricter
variant used `display:none` and revealed the tail directly from a style
container query. Both produced exactly the same 768 outputs as the ungated
connection.

The strict gate lost in five-round warm medians:

| Context | Direct connected | `display:none` gate | Gate penalty |
| ---: | ---: | ---: | ---: |
| 8 | 4.223 s | 4.342 s | +0.119 s |
| 16 | 6.473 s | 6.789 s | +0.316 s |

The `content-visibility` gate was unstable: it saved 0.267 seconds at eight
tokens in one three-round run but added 1.241 seconds at sixteen. A Chrome
trace explains the tradeoff. Hiding the tail reduces the largest individual
layout burst and the number of shaped text runs, but revealing it adds style
recalculation and full lifecycle passes. Chromium ultimately performs the same
dependent work and also pays to change the tree state. Phase gating is
therefore rejected as a scaling optimization.

## Warm state mutation and K/V reuse

Navigation timings overstate sequential-token cost because Chrome can retain
already shaped K/V geometry. A separate harness loads the page once, then
changes one input coordinate. One coordinate invalidates every dense QKV output
because every row depends on it; the harness waits for all 768 final values.

| Context | Mutation | Attention only | Through MLP tail |
| ---: | --- | ---: | ---: |
| 2 | query | 0.299 s | 0.784 s |
| 2 | query + newest source | 0.300 s | 0.970 s |
| 8 | query | 0.767 s | 1.313 s |
| 8 | query + newest source | 0.750 s | 1.524 s |
| 16 | query | 2.331 s | 3.143 s |
| 16 | query + newest source | 2.378 s | 3.676 s |

At sixteen tokens this is about 1.8x faster than the 6.47-second connected
navigation median. It is not yet a complete autoregressive step—the fixture
mutates an existing newest-token slot instead of appending a token or feeding
an argmax result back—but it has the same dense invalidation footprint for new
Q and K/V values. A CSS-only generator should keep one page alive and reuse
past K/V state rather than instantiate a fresh graph per token.

An inheritance-firewall variant reset all 768 Q properties around cached K/V
metric subtrees. It preserved every output and reduced the sixteen-token
attention-only query update from 2.328 to 2.195 seconds (5.7%). The full
query-plus-source update improved only 2.2%, and through the connected MLP the
same firewall was slower: 3.654 versus 3.535 seconds. This rejects the wrapper
firewall itself while bounding accidental Q-property traversal to a small
fraction of total latency.

## Score-track grouping

A follow-up tried to physically separate Q-dependent score nodes from cached
K/V metrics. Chrome does not allow named anchors to cross the relevant shadow
or size-containment boundaries, so a true sibling cache makes score widths
invalid. The valid alternative keeps anchors in their score track, resets Q on
the K/V wrapper, and groups several token sources into one track.

All group sizes reproduce the baseline residual exactly. They are slower for a
sixteen-token query update:

| Sources per score track | Query mutation |
| ---: | ---: |
| Existing per-source topology | 2.250 s |
| 1, with combined K/V wrapper | 2.401 s |
| 2 | 2.550 s |
| 4 | 2.732 s |
| 8 | 3.277 s |
| 16 | 4.141 s |

Cold navigation follows the same pattern: the existing page is about 3.96
seconds at sixteen tokens, while groups of 1/2/4/8 take approximately
5.12/4.37/5.19/6.20 seconds in the focused run. Chromium benefits from small
independent formatting contexts more than it benefits from removing scroller
and track elements. Keep one K/V+score track per source.

An earlier fixture accidentally used a packed projection page generated with
projection-easing flags. That combination omitted the final projection rules
and produced an apparently faster but invalid tail. Those timings are
discarded; the benchmark now uses the validated non-easing packed projection
and checks every output against an independent numerical reference.

## Reproduce

```sh
make geometry-streaming-full-tail
GEOMETRY_FULL_TAIL_CONTEXTS=2,8,16 \
GEOMETRY_FULL_TAIL_ROUNDS=5 \
GEOMETRY_FULL_TAIL_VARIANTS=tail-isolated,connected,display-gated \
node tools/benchmark_geometry_streaming_full_tail.mjs

GEOMETRY_FULL_TAIL_PROFILE_CONTEXT=16 \
node tools/profile_geometry_streaming_full_tail.mjs

GEOMETRY_FULL_TAIL_MUTATION_CONTEXTS=8,16 \
GEOMETRY_FULL_TAIL_MUTATION_ROUNDS=7 \
node tools/benchmark_geometry_streaming_full_tail_mutation.mjs
```
