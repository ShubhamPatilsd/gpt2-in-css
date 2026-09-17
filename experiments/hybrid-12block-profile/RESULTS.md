# Twelve-block hybrid: measured latency and bottlenecks

September 16, 2026. Chrome 153.0.8010.48. Real GPT-2-small weights,
row-wise signed 9-bit weight quantization. No JavaScript in the runtime **or
measurement harness**; script execution is also explicitly disabled through CDP.

## Answer to “13 seconds per token?”

**No: 13.2 seconds was an extrapolation, not a measured complete token.**
The working experiment now measures approximately **39 seconds for the twelve
transformer blocks**. It does not yet measure complete autoregressive generation.

The input is one current-token embedding at position 15, attending to a fixed
15-token prefix KV cache. Its residual passes through all twelve blocks inside
one document. Python prepares the fixed prefix and numerical references; it does
not transfer intermediate current-token vectors or schedule individual blocks.
One input transaction supplies the embedding and a generation number. Native
CSS/view-timeline generation gates schedule the internal stages.

Excluded: prefix prefill, final LayerNorm, vocabulary scoring/selection, KV append,
and token feedback. Adding a separately timed head to these figures would still
not constitute an end-to-end measurement.

## What actually ran

| Connected implementation | Cold setup | Fresh-input warm update |
| --- | ---: | ---: |
| Initial hybrid, nested graph | 126.7 s | 203.8 s, one completed sample |
| Compact font runs, reset scratch variables, layout containment, generation gates | 45.9 s | 47.9 s median; 45.1 / 57.5 / 47.9 s |
| Sibling blocks, native residual bridges, retained `content-visibility` gates | 46.5 s | 39.7 s median; 38.1 / 39.7 / 40.1 s |
| Above plus 1,025-stop FC/GELU easing | 47.7 s | 39.3 s median; 38.8 / 39.3 / 40.8 s |

All warm states use different real current-token embeddings with the same prefix;
they are not repeated toggles of two cached states. The initial slow control was
stopped during its second update; its one completed observation is recorded in
`baseline12-first-update.json`, not presented as a median.

The control used full computed-style reads for settling. Later fixtures use an
external anchor observer with an explicit generation check, then verify all
768 output coordinates outside the timed interval. The control's browser task
time was itself 203.3 s, so readback/round-trip overhead does not explain the large
improvement. The changes are a bundle, not individually controlled ablations.

The 39.7-to-39.3 s difference is **not a demonstrated end-to-end improvement**:
three samples, different inputs, and browser scheduling noise are insufficient
to resolve such a small effect reliably. Keep the exact-GELU variant as the
conservative reference; retain the eased variant as an experimentally faster
local FC implementation.

## Where the complete twelve-block run spends time

A low-volume trace of a fresh update of the eased variant covers 36.17 s of
main-thread events versus 36.22 s wall time. Trace completion reports
`dataLossOccurred: false`. Traced latency is diagnostic, not substituted for the
untraced warm medians above.

Nested events are assigned to non-overlapping categories, not simply summed.

| Rendering phase | Share of traced main-thread time |
| --- | ---: |
| Animation frame servicing | 30.2% |
| Paint/compositing lifecycle and pre-paint preparation | 27.0% |
| Style recalculation and style/layout lifecycle overhead | 13.2% |
| Layout, including font shaping | 5.3% |
| Other main-thread work | 24.4% |

Rounding makes the displayed percentages sum slightly above 100%. The 24.4%
remainder is deliberately not assigned to a more specific cause without evidence.
CSS arithmetic is counted within style work; “5.3% layout” does not mean all
arithmetic consumes only 5.3%.

The high-volume earlier trace in `content-gated/connected-12-trace.json` captured
only about 23 s of main-thread intervals for a 44.7 s update. It records 2.8 million
per-timeline servicing events, but must **not** be used as a complete-run percentage
breakdown. The low-volume trace at `fc-eased/connected-12-trace.json` is the retained
source for the table above.

## Which neural-network stages are expensive

All seven stages were isolated and tested at every layer: 84 fixtures, three
fresh-input updates each. These percentages describe **isolated browser task
work**, not exclusive shares of the connected 39.7-second run.

| Stage | Sum of per-layer median browser task times | Isolated-work share |
| --- | ---: | ---: |
| MLP expansion 768 → 3,072 + GELU | 4.151 s | 45.3% |
| QKV 768 → 2,304 | 2.127 s | 23.2% |
| MLP projection 3,072 → 768 + residual | 1.508 s | 16.5% |
| Attention output projection + residual | 0.760 s | 8.3% |
| QK scores + typed softmax + weighted V | 0.328 s | 3.6% |
| Both LayerNorms | 0.285 s | 3.1% |
| Total | **9.158 s** | **100%** |

Browser task accounting includes incidental scheduling/GC work. As a robustness
check, isolating just style + layout gives the same ranking: FC/GELU 47.8%, QKV
20.0%, MLP projection 17.4%, attention projection 8.4%, mix 4.3%, LayerNorms 2.1%.
Some individual tiny-stage task samples contain large outliers; do not interpret
their times as precise instruction-level costs.

The isolated 9.16 s versus connected 39.63 s of browser task work exposes an
approximately 30.5 s **diagnostic gap**. It is not a measured exclusive “transport
stage,” nor proof that the full gap can be eliminated. The connected graph has
different scheduling, animation lifetime, propagation, and observation costs.

## Optimizations tried and what they establish

1. **Smaller graph and less inherited state.** Single-pack matrices now share font
   settings on an ancestor instead of repeating an extra wrapper per output.
   Larger consumer chunks, reusable registered scratch names, and boundary resets
   keep the twelve-block graph manageable. The prior repository's incorrect
   connected twelve-block result is not reused as a speed baseline.
2. **Generation-aware native scheduling.** A marker travels through the same
   layout pass as each font matvec. Downstream work is gated until that pass has
   consumed the current input generation. This is event/state driven, not a
   guessed millisecond delay or an external Python block scheduler.
3. **Sibling block subtrees and native bridges.** Only residual values and the
   generation marker cross the block boundary through geometry/view timelines.
   This adds a little numerical error but limits inherited state propagation.
4. **Retain skipped stage layouts.** `content-visibility` gates retain more state
   than repeatedly removing complete subtrees with `display:none`. An observer
   outside the gated subtrees avoids directly forcing their layout just to poll
   completion.
5. **Apply the earlier FC/GELU easing technique across all layers.** Affine
   `calc-size()` geometry plus a shared 1,025-stop easing writes hidden activations
   directly, removing 3,072 progress/decode properties. Isolated FC task work fell
   from 4.151 to 2.621 s (about 37%); its style/layout component fell 56%. The full
   model did not show a meaningful timing improvement. A small latch diagnostic
   ran concurrently with the first few eased-FC samples, so treat the local
   percentage as approximate, not a tightly controlled microbenchmark.
6. **Test, and reject, a naive timeline latch.** Pausing QKV output animations
   preserved all 2,304 values. Removing their producing timeline names/scroller
   while paused corrupted them (RMSE 105.19; generation gate closed). Reattaching
   and resuming on a fresh input restored accuracy. Therefore simply pausing and
   deleting completed producers is not a valid optimization.

## Accuracy and limitations

The exact-GELU sibling variant has final residual RMSE 0.0209–0.0337 across the
four tested states. The eased variant has RMSE 0.0191–0.0276. Applying the real
final LayerNorm and tied embedding head **offline, outside the timing**, preserves
the quantized-reference winner for all four states in both variants: token IDs
314, 995, 314, and 382. This is a small numerical screen, not a general accuracy
guarantee or a completed browser vocabulary head.

The inputs/ranges are calibrated for these four states. The prefix cache is fixed;
rolling KV updates, long-context behavior, and broad prompt accuracy remain
untested. Geometry bridges introduce additional rounding. Fonts still use the
existing 9-bit row weight representation.

## Next tests, in priority order

1. **Retire completed work without losing state.** First prove a real native
   numeric latch on a two-stage, 256-output fixture: values must survive producer
   deactivation, remain readable by a second font, and resume correctly on a new
   generation. The naive paused-timeline version above already failed. Only after
   a latch passes should automatic acknowledgement-driven retirement be attempted.
   Measure active timeline count/servicing, not just DOM node count.
2. **Reduce live timeline count in a localized stage.** QKV is a better first
   candidate than the entire MLP. Compare the existing packet transports against
   the accurate font path on fresh inputs, including final winner margins; do not
   trade away accuracy based only on local RMSE or a cached-state speedup.
3. **Dissect paint/compositing lifecycle cost and the unassigned remainder.** Test
   hidden versus scroll overflow and containment in a single stage, keeping the
   timeline geometry mapping and outputs unchanged. A win here can matter more
   than further speeding up softmax arithmetic.

Do not prioritize replacing the typed softmax reducer: it is only 3.6% of
isolated stage work. Do not assume another isolated FC speedup translates into
an equally large complete-token improvement.

## Reproduction and primary artifacts

Build the conservative retained experiment:

```sh
uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_hybrid_twelve_block.py --blocks 12 --compact-metrics --reset-scratch --contain --gated --sibling-blocks --content-gates --chunk 512 --output experiments/hybrid-12block-profile/content-gated
uv run --with pillow python tools/profile_hybrid_twelve_block.py --blocks 12 --isolated --directory experiments/hybrid-12block-profile/content-gated --report twelve-and-stages-results.json
```

Add `--fc-easing`, with a separate output directory, for the easing experiment.
Use `--trace --states 2` for the low-volume diagnostic trace. Timings are local
machine measurements, not browser-independent guarantees.

- `content-gated/twelve-and-stages-results.json`: connected run plus all 84 stages.
- `fc-eased/twelve-results.json`: untraced eased twelve-block run.
- `fc-eased/fc-stages-results.json`: all twelve isolated eased FC stages.
- `fc-eased/connected-12-trace.json`: retained complete low-volume trace.
- `*-offline-head-check.json` beside the reports: offline winner checks.
- `timeline-latch-results.json`: failed pause/detach latch experiment.
- `tools/test_hybrid_profile.py`: non-overlapping trace accounting and fixture
  script/depth regression checks.

All work in this experiment is in new tools and generated fixtures; the prior
project implementations and their saved measurements are left intact.
