# Scaling implementation, September 16–17

Constraints: stock Chromium, no runtime or harness JavaScript, no external
intermediate-vector feedback. Existing demo remains untouched. Static Python
compilation and independent reference evaluation are permitted.

Prioritized work:

1. SVG/CSS hybrid feasibility: existing native raster exports are one-way.
   There is no demonstrated SVG-pixel-to-CSS-number return route. Do not claim
   an MLP accelerator until both directions work without external readback.
2. Packed KV: test expression12, expression10, and expression8 against scalar
   and expression16 in the real browser. Require native retention and numerical
   checks; smaller property counts alone do not establish lower memory.
3. Reuse a single transformer block's rendering graph across layers, with
   separate browser-owned KV banks. First prove native ping-pong vector
   feedback, then two real layers, then twelve. This preserves the checkpoint
   and computation; it changes execution scheduling, not the architecture.
4. Integrate a successful candidate with the full vocabulary head and native
   token feedback. Measure complete generation, RSS, and context scaling before
   promoting it. Record failures and unfinished gates explicitly.

Initial results:

- Whole-vector comma-list latch retains data but cannot unpack it through
  CSS custom-function arguments. Deferred custom functions evaluate at the
  producer, not at the consumer. Rejected; `css-vector-latch/results.json`.
- Two-block expression12, eight positions: all numerical and cache-retention
  checks passed, 2.95 s median warm update. RSS still grows to roughly 3 GiB;
  this is not a low-memory result or a new full-pipeline timing.
- Two-bank native feedback completed 32 synthetic iterations without external
  writes. Ordinary progress transport accumulated 0.0224 error and failed the
  strict numerical gate. Centered progress passed with 0.00001 final error;
  the factored two-state controller passed the same regression.
- A single shared rendering graph completed two real GPT-2 layers on one token
  in 6.70 s from navigation, with final residual RMSE 0.0179 against the q9
  reference and sampled peak renderer RSS 1.41 GiB. This is the first integration
  proof, not a full-model performance result. Initial attempts were blocked by
  a missing positioned style on the standalone font-readiness reduction tree;
  the font readiness guard remains enabled in the successful run.
- Twelve shared-graph layers across eight native teacher-forced positions
  completed all 96 passes in 370.9 s. Final residual RMSE was 0.05099 (just above
  the 0.05 component gate); sampled peak renderer RSS was 6,171 MiB. This is
  NOT a promoted full pipeline or a low-memory result. A separate centered
  context bridge is now available to reduce the extra geometry handoff error.
- A source-informed blanket MatchedPropertiesCache bypass was tested with
  `opacity:attr(data-mpc-guard type(<number>),1)`. Numeric outputs were unchanged,
  but the two-block update slowed to roughly 6.6 s and RSS exceeded 5 GiB.
  Reject the blanket bypass. Stage-liveness and a narrower cache policy remain
  separate experiments, not established wins.
- Detailed memory-infra dump of the two-block expression12 fixture attributes
  2,212 MiB to Blink's managed heap (574 MiB allocated objects at dump time),
  including two 106 MiB custom-property trie categories. This is not raw KV
  storage. A diagnostic critical-pressure signal did not release those objects.
  Narrow cache exclusion, liveness resets, and non-inherited private state have
  not established a meaningful latency improvement in the eight-token screen.
- A Chromium precision probe found that computed `<integer>` packets initially
  serialize with the same six-significant-digit loss as `<number>`, but their
  retained transitions materialize exact signed 32-bit integer text. A native
  integer10 codec now bypasses the active packet with live K/V and decodes only
  retained packets. This is experimental pending core and full-pipeline tests.
- The first packed/liveness full-pipeline attempt exceeded the old 30 s DOM
  navigation deadline. The retry permits 180 s startup and reached the first
  token at 108.3 s. Its timing is diagnostic: a one-second native process sample,
  extra read-only CDP inspection, and concurrent component work were performed.
  A clean rerun is required before reporting a comparative pipeline speed.
  This retry was interrupted after five of eight generated tokens at 405.0 s;
  it is not a completed pipeline result. No measurement Chrome processes
  survived the interruption. The concurrent scoped reused-core test did not
  finish or leave a final result; it must be rerun.
- Integer10 eight-position core passed in Chromium, including exact retained
  integer packet checks. The scoped reused two-layer core completed 16 native
  passes in 44.80 s, final RMSE 0.003053, peak renderer RSS 4,485 MiB. This is
  accurate but not yet low-memory.
- Autonomous shared-core adapter completed three two-layer tokens with the full
  vocabulary head: `[11,3387,3387]`, all matching the q9/q16 reference. Final
  residual RMSE 0.002559; total 79.11 s, peak renderer RSS 6,034 MiB. This is a
  TWO-layer integration test, not a twelve-layer GPT-2 performance result.
  Its initial controller-name collision was fixed; root query-only layer state
  is now being made non-inherited to avoid invalidating the vocabulary sibling.
- Matched integer10 two-layer/eight-position fresh-process memory comparison:
  default Chrome 3,075 MiB renderer peak / 2.985 s median warm; native heap
  growth 10% 1,550 MiB / 3.150 s. All browser vectors were identical and retention
  passed. This cuts sampled peak RSS 49.6% at 5.5% latency cost in this short
  screen. Requires `--js-flags=--heap-growing-percent=10`: a native collector
  setting, not JavaScript execution, external GC calls, or model computation.
  Source checked at exact V8 revision `6b96683d44174e78ff4e65cb274bad56dc108231`,
  `src/heap/heap-controller.cc`: the flag also controls GlobalMemoryTrait, which
  includes the embedder heap. Default page/runtime behavior remains unchanged.
- The integrated private-control two-layer/three-token check also passed with
  identical vectors under the heap setting: 71.94 → 63.07 s total; renderer peak
  5,464 → 3,846 MiB. The flagged cold load overlapped a small compiler run, so
  treat the cold difference as diagnostic. Warm intervals were 19.70/6.97 s
  default versus 11.12/6.52 s flagged; only two intervals, not a robust latency
  distribution.
- Moving the per-layer style container off `body` exposed a specificity bug:
  the external token-boundary selector permanently overrode later layer
  advances. The failed run stopped at pass 3 after one token. All controller
  pass selectors now use equal-specificity `:where()` forms; regression checks
  cover the boundary and following intra-token advance. No failed timings are
  promoted. A detached-output experiment keeps token storage alive while the
  vocabulary scorer is skipped during core computation; it is not yet proven.

Further completed measurements and current work:

- Reused/local-controller/detached-output two-layer integration completed three
  tokens in 65.89 s with peak renderer RSS 3,338 MiB. All q9/q16 decisions
  matched; final residual RMSE 0.002559. The transient head observer missed an
  intermediate milestone, so a separate retained capture observer was added.
- Full twelve-layer reused integer10 pipeline then completed all eight tokens
  in 458.206 s (navigation-to-first 81.967 s; Run-to-first 50.969 s; warm median
  54.461 s, range 41.165–63.855 s). Peak renderer RSS 5,445 MiB. All eight
  q9/q16 and original floating-point decisions matched; final RMSE 0.019826.
  This is 31% lower total time than the SAVED 662.495 s baseline, not a clean
  randomized paired benchmark. Warm cost still rises as native cache fills.
  Warm renderer task time: 59.46% style, 8.30% layout, 32.12% other, 0.12% CDP;
  script/V8 compilation zero. Only three complete coarse milestone intervals
  were observable; their core+KV share was 88.65%, not an exclusive profiler.
- Integer10 ordinary two-layer core passed all 32 held-out teacher-forced
  positions, including exact retained-packet checks. Warm updates grew from
  3.319 s at position 2 to 6.302 s at 32; last renderer sample 2,450 MiB.
  Position-32 task time: style 2.072 s, layout 0.328 s, other 3.891 s. This is
  component evidence, not full-model long-context inference timing.
- Re-running the unchanged original full runtime with heap growth 10% was
  intentionally stopped after four correct tokens. Warm intervals were
  79.653, 104.700, 91.405 s. It is NOT complete and has no final RSS/numerical
  readback. The original unprefixed baseline files remain untouched; partial
  files use `demo/scaling-heap10-`. Aggressive collection alone is not a speed
  fix for the original graph.
- Split the full head's score and epoch into separate geometry transports;
  the old packing only had four epoch bits. Actual full-vocabulary component
  checks passed all 38 existing hard fixtures at epochs 14–50 and 1024,
  including the 15/16 boundary. The initial 30 s navigation timeout was raised
  to 180 s. This proves long epoch transport, NOT 1024-token inference.
- New native storage mechanism: `contain-intrinsic-size:auto 0px` remembers
  prior layout dimensions while contents are hidden. Direct anchors on hidden
  latches return fallback zero, but a visible outer wrapper exposes their
  correct remembered sizes. Wrapped and `content-visibility:auto` variants
  passed holding, source mutation, ancestor display:none/restoration, rewrite,
  and re-hold. No transitions or scripts store these values.
- A remembered-layout attention prototype now passes a four-position synthetic
  test: final RMSE 0.000052, max 0.000080. It stores per-head dynamic scales and
  K/V dimensions, uses anchor arithmetic for signed dot products / stable
  softmax / weighted V, and returns only the context through the existing
  centered view-timeline bridge. The first version could not resolve anchors
  across separate positioning contexts; sharing the scroll-track plane fixed
  that. Real 32-position QKV component and native full-model integration are
  pending. This backend is experimental, not promoted.

Further September 17 measurements:

- Remembered-layout attention passed all 32 real layer-0 QKV positions, maximum
  RMSE 0.000060, but attention alone took about 17 s/update. Peak renderer RSS
  924 MiB. This diagnostic run overlapped a short quality probe and native
  process sample; it is not a clean speed comparison. Balanced sum trees did
  not improve the result. Two-layer autonomous integration passed three tokens
  in 66.70 s, peak renderer 3,222 MiB. Do not promote the geometry backend.
- Whole-head font-vector cache stores each K/V head as a registered universal
  font-settings list and numeric scale: 48 fields per token/layer, versus
  integer10's 552 and scalar's 1,536. Private per-layer banks are nested, and
  only the active bank projects readable aliases to one bilinear attention
  graph. No external unpacking or author JavaScript is used.
- The first font-vector probe failed because a 4096 px dot font saturated
  Chromium's individual shaped glyph advance near 32768 px. A 512 px dot font
  fixes this. The value path now uses a fixed 1024 px font, folds V scales into
  probability axes, and restores the common scale after summing inline widths.
  This avoids glyph-size overflow for larger neural activations.
- `font-vector-attention32-scaled-axes` passed all 32 held-out real QKV steps.
  Final RMSE 0.0000794, maximum 0.000745. Component update time grew from
  0.508 s at position 2 to 1.393 s at position 32. This is attention only,
  not an autonomous pipeline measurement. The earlier variable-font-size
  version also passed, but accumulated more rounding error (RMSE 0.00118 at 32).
- Initial font-vector autonomous two-layer/three-token integration completed
  in 36.804 s, warm intervals 9.168/12.014 s, peak renderer 3,215 MiB. All
  decisions matched; final residual RMSE 0.002409. This fixture predates the
  improved value scaling. Retained whole-head lists were decoded only after
  timing and compared with independent model QKV traces.
- A full twelve-layer/eight-token font-vector run is in progress. Optional
  bounded KV with initial sinks plus a rolling recent-token ring and metric-only
  inherited-state isolation are implemented but not yet browser-validated.
  Bounded KV explicitly changes the attention mask; full causal remains default.

Remembered-size sources were inspected in the exact Chromium revision below:
`core/dom/element.cc` (`ProcessContainIntrinsicSizeChanges`),
`core/dom/document.cc` (native `IntrinsicSizeResizeObserverDelegate`),
`core/layout/layout_box.cc` (using last remembered sizes while locked).
The delegate is Chromium C++, not author JavaScript. The CSS specification:
https://drafts.csswg.org/css-sizing-4/#last-remembered

The cache-policy source was read at the actual browser revision:
`199a3a541d76237379e353b348e64045584db057`,
`third_party/blink/renderer/core/css/resolver/matched_properties_cache.cc`.
`HasAttrFunction()` excludes cache insertion; the 500-entry cache limit is
enforced during weak/GC cleanup. This motivated a test, not a claim that this
cache explains all measured resident memory.

Disk recovery: the twelve generated `nested/batch24-cut-bN-attention.html`
pages in the failed causal SVG batch experiment were compressed in place to
`.html.gz` and checked with `gzip -t`. They are recoverable with `gunzip`;
no model assets, source, valid diagnostic results, or demo files were deleted.

Deadline requested by user: six hours from 2026-09-17 04:29 UTC. This is an
engineering target, not a promise that an unproven backend will succeed.
Only about 1 GiB of disk was free at the start; reuse existing font assets and
avoid generating more massive SVG graphs. Do not delete unrelated experiments.

Completed and pending at 2026-09-17 07:00 UTC:

- The full twelve-layer/eight-token whole-head font-vector pipeline completed
  in **402.672 s**, navigation-to-first 45.058 s, Run-to-first 39.772 s, warm
  median 51.310 s. Peak sampled renderer RSS **3,863 MiB**. Eight of eight
  q9/q16 and original floating-point decisions match; residual RMSE 0.018902.
  These are saved in `demo-font-vector-twelve/`, using the preserved v1 fonts.
  Total time is 39.2% below the saved 662.495 s original, not a randomized
  paired benchmark. Warm task time: style 56.85%, layout 15.50%, other 27.58%,
  CDP 0.07%, script and V8 compile zero. Five complete coarse milestone
  intervals put core+KV at 90.28%, handoff 5.32%, head 3.57%, embedding 0.82%.
- The v1 full-causal 32-token pipeline is still running, now beyond the old
  16-epoch head boundary. Do not promote its partial timing as completion.
- `font-vector-ring32-window8` passed all 32 real QKV attention updates with
  eight physical slots and two retained initial positions. After filling, cost
  stayed about 0.46–0.49 s/update; final RMSE 0.000061 against the SAME bounded
  mask, peak renderer 987 MiB. This proves ring retention and component cost,
  not full-model quality relative to full attention.
- Metric-state isolation did NOT improve matched two-layer/four-token runs:
  control 43.243 s / 3,522 MiB; isolated 44.791 s / 3,673 MiB. Both had identical
  vectors and four matching q9/q16 decisions. It stays disabled.
- `tools/launch_browser_gpt2.py` provides an allowlisted localhost static server
  and dedicated Chrome profile with scripts disabled. Default points to the
  validated eight-token font-vector fixture. Dependency/CSP and server tests
  pass. No inference endpoint or external token scheduler exists.
- Source-only candidates, NOT yet browser-validated: v2 weighted-V font with
  one probability axis plus 64 value axes; factored cache write strings;
  private score scratch and same-element softmax; fallback-font V runs with
  only 768 output metric elements rather than 768 times the cache capacity.
  Unit tests check all 64 bilinear products and slot-specific cmap/axis mapping.
- Another pending candidate selects Chromium's native Fontations backend using
  an identity `avar` version-2 table. Original font assets remain unchanged;
  protected model/shaping tables are checked byte-for-byte on the clones.
  Exact Chromium revision `199a3a541d76237379e353b348e64045584db057`,
  `platform/fonts/web_font_typeface_factory.cc`, routes avar2 to Fontations,
  while ordinary variable fonts use the macOS system font manager. This may
  bypass the previously observed 256-axis limit; acceptance and speed remain
  unproven. Do not claim a backend improvement until native tests pass.
- Teacher-forced full-pipeline quality capture is implemented but not yet
  browser-tested. It supplies only known input token IDs and reads retained
  native final hidden states after predictions. Distribution metrics use an
  explicitly OFFLINE head after the run; this is not browser-native PPL.
  `scaling-quality33-tokens.json` contains 33 IDs from the existing held-out
  WikiText2 test article 36 / token offset 2300, enabling 32 next-token scores.
  No diagnostic hidden state or reference activation is fed to Chromium.
