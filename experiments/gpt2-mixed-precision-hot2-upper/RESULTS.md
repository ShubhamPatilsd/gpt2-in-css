# Mixed-precision hot-2 upper-head feasibility

Decision: **retain**.

The probe replaces 512 existing int10 upper rows (groups 0 and 1) with global-int16 rows. It adds **0 upper rows** and **0 speculative parallel fine rows**. A selected hot group reuses the tie-preserving `--group-*` grid anchor; the separate `--score-group-*` routing wrapper alone carries the 24-bucket safety offset. Only selected non-hot groups instantiate the ordinary 256-row fine grid.

## Exactness and feasibility

- Browser fixture checks against live exact per-group shadows: 30/30; exactness is claimed only for checks whose `pass` field is true.
- Exact-shadow coverage: 39/39 selected groups (39 on the control route, 0 forced through the control exact grid).
- Offline corpus target retention: 1024/1024.
- Standard lexicographic corpus geometry: 2048/2048; agreement with the distinct unrounded raw-score contract is 2045/2048.
- Fine-grid evaluations removed in the browser screen: 36/39 active stage visits.
- Corpus-path fine-grid evaluations removable: 820.

The browser probe uses the standard exact fine-stage lexicographic contract: rounded 1/256 score bucket first, then lower token ID. Its selected `--group-*` grid anchor carries bucket plus local tie; the separate `--score-group-*` wrapper receives the 24-bucket routing allowance. An analysis-only fitted permutation can recover raw-score winners in three bucket-collision cases, but it is not emitted by this probe (group 0: 3 fitted precedence edges, group 1: 3 fitted precedence edges).

Browser score buckets and winners are matched by selected group against the live exact six-stage control, not stale NumPy stage indices. Best-state is recomputed from those live per-group scores; certificate gap and stopping are checked from the mixed route's live next-upper bucket. Dense final winner remains an independent oracle.

## Aggregate warm timing

| Metric | Mixed upper | Six-stage exact/int10 control |
|---|---:|---:|
| warm mean (30 paired samples) | 3844.5 ms | 5340.3 ms |
| warm median | 3651.8 ms | 5310.8 ms |
| warm p90 | 5090.6 ms | 7306.6 ms |

Mean ratio: **0.720x** (28.0% faster).

### Per-round warm means

| Round | Page load order | Mixed upper | Control | Ratio |
|---:|---|---:|---:|---:|
| 0 | mixed then control | 3766.1 ms | 5563.1 ms | 0.677x |
| 1 | control then mixed | 4349.5 ms | 5507.8 ms | 0.790x |
| 2 | mixed then control | 3417.8 ms | 4950.1 ms | 0.690x |

### Cold loads

| Round | Mixed load | Control load | Mixed load + first evaluation | Control load + first evaluation |
|---:|---:|---:|---:|---:|
| 0 | 54831.8 ms | 60973.9 ms | 57583.9 ms | 63833.9 ms |
| 1 | 55582.3 ms | 57683.1 ms | 57896.9 ms | 61534.3 ms |
| 2 | 54102.6 ms | 58496.8 ms | 57375.8 ms | 63804.0 ms |

## Topology and bytes

- Generated HTML: 8,247,838 bytes.
- Generated topology CSS: 704,865 bytes.
- Reused int10 WOFF2: 51,181,024 bytes; reused exact WOFF2: 79,431,996 bytes. No font was copied or rebuilt.
- The measured exact asset covers the full vocabulary; all byte figures above are actual loaded or reused assets.

## Interpretation

The robust three-round screen passes all semantic gates and improves aggregate warm latency, so this route is retained.

## Cold-start subset follow-up

A separate 512-glyph exact-font subset preserves the same row topology and
passes 24/24 browser mutations. It cuts startup WOFF2 requests from 130.61 MB
to 65.32 MB and conditional cold mean from 61.45 to 49.11 seconds. It is an
optional cold/hot-route profile, not the warm default: hot mutation is 5.7%
slower and first non-hot activation lazily requests the remaining 66.18 MB.
See `../gpt2-mixed-precision-hot2-upper-subset/RESULTS.md`.

## Hot-K follow-up

An offline K=0/1/2/4/8/16/32 route sweep retains all 1,024 targets. The paired
browser screen for K=1/2/4/8 passes all 40 fixture gates and measures normalized
warm ratios of 0.806x/0.641x/0.729x/0.711x. K=2 remains fastest at 3.496 seconds
mean. K=8 eliminates every dynamic fine grid on the ten fixtures, but the extra
always-on exact upper rows outweigh that final removal. See
`../gpt2-mixed-precision-hotk-sweep/RESULTS.md`.

## Group-size follow-up

An offline G128/G256/G512/G1024 sweep retains all 1,024 targets, but the browser
rejects generalized local-ID transport. G128 keeps score buckets exact while
shifting selected token IDs at 4/8/16/32 px score strides; increasing tie
spacing does not repair the anchor/container handoff. Wider candidates were
not timed after that falsification. The retained G256 encoding remains the only
transport-proven group size. See
`../gpt2-mixed-precision-group-size-sweep/BROWSER-RESULTS.md`.

## Signed-result and one-plane follow-up

Chrome 153 preserves negative and greater-than-65,535 HVAR advances inside a
positive-width shaped run, even though isolated negative boxes report zero.
It also accumulates a 493,505-unit always-on HVAR bias before applying negative
regions. Those primitives make a direct six-glyph int16 row structurally
possible; see `../hvar-resulting-advance-range/RESULTS.md` and
`../hvar-virtual-base/RESULTS.md`.

The composed hot-2 replacement is nevertheless rejected. It halves each hot
row from twelve glyphs to six and needs only 909,368 bytes of hot fonts, but the
two-fixture browser falsification matches the retained live bucket route only
once. Fixture 1 group 1 decodes bucket 12,621 instead of 12,620, shifting the
next-upper and certificate gap by one. Its preliminary warm mean is also 1.152x
the retained two-plane page. Per-run metric snapping remains part of the exact
browser contract; fewer glyphs do not reproduce the old rounding. See
`../gpt2-virtual-base-oneplane-hot2/RESULTS.md`.

A cheaper screen-domain compensator does not work across the six font fallback
runs. Offline, 45,121 fixed units cover all 1,024 realized corpus states and ten
fixtures, and six signed score glyphs plus two fixed glyphs are 22.3% faster in
the two-fixture screen. Browser semantics are completely wrong (0/2 routes):
negative advances in one fallback run do not subtract from a compensator in a
later run. Per-shard compensation would restore twelve glyphs, so reject this
branch. See `../gpt2-compensated-oneplane-hot2/RESULTS.md`.

Reusing the already-paid int10 score and adding only an exact residual also
fails at the browser boundary. The coefficient decomposition
`globalCode = m*int10Code + residual` is exact, needs only three residual
glyphs, and keeps residual coefficients within +/-32. For group 0, separately
shaped coarse and residual widths disagree with the live twelve-glyph score on
2,397/2,560 candidate buckets and all ten winner buckets. The residual grid is
also 1.255x slower. See `../gpt2-aligned-residual-group/RESULTS.md`.

Rigorous token-level pruning preserves the unchanged exact rows and therefore
does pass semantics. For fixed group 0, 256 coarse-bound carriers activate only
3-15 exact rows (mean 7.6); all ten active sets, winners, buckets, equality
cases, and lower-token ties match their oracles. It still loses the balanced
50-mutation screen: 165.4 ms gated median versus 160.65 ms full-grid median,
with mean and p95 also worse. Reject the current gate topology; see
`../gpt2-token-uncertainty-gate/RESULTS.md`.

Block-level pruning removes that isolated topology bottleneck but not the
end-to-end cost. Contiguous B=4/B=8 wrappers are exact and cut the fixed-group
screen from roughly 157-160 ms full means to 9.84/10.31 ms. Integrating them
here requires restoring 512 int10 center rows beside the gated exact rows.
Against this retained page, B=4 is then 1.045x by mean and 1.089x by median;
B=8 is 1.317x by mean. The duplicated coarse score graph costs more than the
hidden exact rows save. Retain the in-place mixed-hot2 page; see
`../gpt2-token-uncertainty-block-gate/RESULTS.md` and
`../gpt2-mixed-hot2-block-gate-b4/RESULTS.md`.

## Reused-upper direct-max block gate

The duplication penalty is now removed. The original int10 upper rows for
groups 0/1 supply both global routing and token bounds, while their unchanged
exact rows sit behind B=4 conditional blocks. Reusing the exact maximum through
the old intrinsic-width wrapper is not legal in Chrome: it creates a descendant
sizing cycle or resolves to zero across the containing-block boundary. One
direct 197-way `max(anchor-size(...))` node can replace only the outer timeline
bucket extraction and feed the existing route decoder.

This topology passes 30/30 paired semantic checks over all ten fixtures and
three alternating rounds. Warm mean improves from 4,186.3 to 3,850.1 ms
(0.920x), and median improves from 3,903.1 to 3,227.2 ms (0.827x). Cold load
regresses from 40.06 to 51.33 seconds and one candidate sample reaches 12.10
seconds. B=8 passes its narrow screen but is slower than B=4 on both candidate
mean and median. A later matched comparison shows that direct maximum extraction
with the original full hot grids is another 5.8% faster by mean and 5.2% by
median, so the gate is superseded. See
`../gpt2-mixed-hot2-reused-upper-block-gate-b4/RESULTS.md`.

## Direct maximum ablation

Replacing only the 197 view-timeline inverse-width proxies with one direct
`max(anchor-size(...))` node passes 30/30 broad checks and improves warm mean
from 4,189.0 to 3,234.0 ms, median from 3,912.6 to 3,110.5 ms, and p90 from
7,145.9 to 4,956.0 ms. This simpler full-hot-grid form was the loaded warm-path
winner at this point. It proves the dominant improvement came from maximum transport, not
from suppressing exact hot-row shaping.

Removing the now-dead 197 proxy elements and disabling their timelines is
warm-neutral over 30 pairs (1.003x mean, 0.987x median) but cuts paired cold
load from 50.51 to 32.78 seconds. Keep the pruned form as the cold-start profile.
Physically stripping the remaining dead timeline CSS cuts only about 53 KB;
its 6/6 exact screen changes cold load by less than 1% and regresses warm mean
2.8%, so runtime graph pruning is the useful optimization.
A co-activation-clustered B=4 gate halves fixture row work but is still 1.086x
by mean and 1.402x by median against direct-max/full-grid. See
`../gpt2-mixed-hot2-direct-outer-max/RESULTS.md`.

A two-level maximum improves the router again without changing arithmetic.
Thirteen chunk nodes of at most 16 score anchors feed one root; over 30 exact
pairs it improves mean 2.5%, median 1.0%, p90 10.6%, and maximum 12.5% against
pruned flat direct-max. Fan-in 8 and 32 lose to 16; fan-in 64 trades 1.9% mean
and 5.3% median regressions for a 14.6% p90 improvement. Keep fan-in 16 as the
balanced loaded winner and 64 only as a tail profile. See
`../gpt2-mixed-hot2-hierarchical-outer-max16/RESULTS.md`.

Follow-up decoder compression does not help. A packed-four hierarchy and a
non-expanded chunk/slot decoder shrink the remaining flat carrier banks, but
both fail initial-route checks and regress narrow mean by 55.7% and 26.5%.
Nesting bounded `max()` calls inside one property stays exact over 30 pairs but
regresses mean 4.3% and median 6.0%. The browser benefits from materialized
bounded-max anchors, not merely a smaller DOM or syntactically nested math.

The score-row reducer itself does admit a simpler primitive. Ordinary
zero-height block children preserve the 256-row max-content maximum and every
tie without Grid track sizing. Composed with fan-in 16, this passes 30/30 and
improves mean/median/p90/maximum by 7.9%/6.2%/8.1%/8.7%. A browser trace shows
layout falling 13.3% and style recalculation 30.2%, while the approximately
50.5k shaping calls remain unchanged. This block-flow variant is now the
balanced loaded winner; see
`../gpt2-mixed-hot2-blockflow-group-max/RESULTS.md`.

The result does not generalize to every Grid or wrapper. Applying block flow
to the conditional exact fine stage regresses narrow mean 4.6%, and collapsing
the obsolete timeline scroll surface regresses 10.4%. Keep the original Grid
for active fine stages and retain the scroll ancestor as a layout boundary.

The remaining coarse glyph multiplicity can be reduced without changing that
topology. An opt-in relaxed-result writer packs each row into three 256-axis
faces instead of five 160-axis faces. The composed head passes 30/30, improves
loaded mean 2.0% and p90 11.9%, and cuts fixture-1 shaping time from 667.1 to
468.0 ms. Its paired cold load regresses 11.1%; use the 256-axis page for
loaded recurrent inference and retain the five-shard page for cold startup.
See `../gpt2-mixed-hot2-blockflow-group-max-shard256/RESULTS.md`.

Merging adjacent shards within the existing high/residual decomposition confirms
that run-level snapping, not virtual bias, causes the one-bucket error. Three
256-axis high/residual pairs fit the newly established asymmetric advance range
and cut each hot row from twelve glyphs to six with no extra axes. Fixture 1
group 1 still decodes 12,621 instead of 12,620; the two-fixture timing is only
2.8% faster. Reject transport and keep six 128-axis pairs. See
`../gpt2-twoplane-256axis-hot2/RESULTS.md`.

Chrome: 153.0.8010.36. Full observations are in `browser-results.json`.
