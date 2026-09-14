# Groupwise 96-block Cauchy integrated cascade gate

## Decision

**Reject this integration topology; retain the groupwise coarse carrier.**

The three-stage strict HTML/CSS page does not route correctly. Across two
rounds over representative one-, two-, and three-stage fixtures, it passed
0/6 route/fine-winner/stop/final-winner checks. Every mutation incorrectly
selected groups `102, 179, 13`, kept all three exact stages active, and
requested fallback. The generated offline routes were input-dependent and
ended after one, two, or three stages.

This failure is not evidence against the retained one-glyph-per-group
96-block Cauchy carrier. All 96 bound axes changed, all 197 bound glyphs were
present, and their geometry changed. Of 48 sampled widths, 46 matched the
predicted outward 4 px bucket exactly and two observations of the same
boundary case landed one additional bucket outward. No width rounded inward.
The carrier is live and conservative; its width does not compose correctly
with this page's older scroll-timeline outer reducer.

Do not build the exact fallback on this base. The next valid integration test
should port the carrier into the retained block-flow/fan-in-16 topology, then
repeat this smallest-prefix correctness gate before adding a tail.

## What was actually built

The page starts from
`gpt2-hvar-grid-output-head-certified-upper-int10-one-step`, not from the
retained shard256 page. It adds:

- all 197 groupwise certified upper bounds, each as one live 96-axis HVAR
  glyph;
- three best-first exact 256-row global-int16 stages;
- strict `gap > 48 buckets` stopping with later stages gated by `display:none`;
- `--fallback-required: 1` when the finite prefix remains unresolved.

The page contains 50,257 coarse candidates, 768 exact-stage candidates, 197
bound glyphs, 8.12 MB HTML, and 5.35 MB CSS. It contains no `<script>` and was
loaded with page JavaScript disabled; Playwright only mutated inputs and read
layout from outside the page.

No fallback was generated. A complete finite implementation would require one
of three known exact closures: one conditional 50,257-row global-int16 dense
scorer, 197 conditional exact-group branches, or continuation through all 197
groups. Each adds work and cannot repair a wrong upstream route.

## Target and sound contract

The intended target is precisely:

```text
argmax of GPT-2's tied output matrix quantized once with the existing global
int16 scale, evaluated at Chromium's F2DOT14-realized hidden coordinates,
rounded to 1/256-logit score buckets, with lower token ID winning ties
```

It is not a claim of original-float exactness. The intended global-int16 target
happens to match the fresh float checkpoint winner on all ten generated browser
fixtures. GPT-2 small's architecture and checkpoint weights are unchanged.

Offline, the finite schedule is sound under the existing current-range
Chromium realization contract: visit groups by descending groupwise upper,
evaluate one exact group, and stop only when the incumbent fine lower exceeds
the next unvisited upper by more than 48 buckets. Otherwise fallback is
mandatory. The generated ten-fixture schedule certified six states in one
group, three in two groups, and one in three groups.

Browser correctness failed before that contract could be exercised: the outer
group selector did not preserve the groupwise upper ordering after the bound
glyph was inserted into the scroll-timeline geometry.

## Timing, with limitations

| Metric | Broken three-stage prefix | Saved retained shard256 profile | Saved global-Cauchy cascade |
|---|---:|---:|---:|
| Loaded mutation median | 2,918.5 ms | 2,709.1 ms | 4,806 ms |
| Loaded mutation mean | 3,087.0 ms | 2,741.0 ms | 4,517 ms |
| Cold load | 59,321.7 ms | 56,693.5 ms | not reported separately |
| Cold load + first evaluation | 62,465.0 ms | not reported | 49,100 ms |

The retained shard256 topology and global-Cauchy page were **not run in this
browser process**. Their values are prior profile results included only for
orientation; this is not a paired A/B.

The 2.919 s prefix median is diagnostic, not an optimistic lower bound. The
route failure kept all three exact stages active even on fixtures that should
stop after one or two. Correct routing and gating could reduce this number.
Conversely, the missing exact fallback can only add source and conditional
work. Because both effects are unresolved, this run cannot decide whether a
correct groupwise cascade on the retained topology beats shard256. It decides
only that extending this older one-step/scroll-timeline integration would be
overbuilding on an invalid base.

## Artifacts

- `reference.json`: exact target, generated routes, stop contract, fixture
  corpus, and architecture/checkpoint invariants.
- `browser-results.json`: authoritative live timing, 0/6 correctness result,
  bound-axis/geometry evidence, and timing limitations.
- `index.html` / `index.css`: generated strict script-free three-stage page.

Nothing was committed or pushed.
