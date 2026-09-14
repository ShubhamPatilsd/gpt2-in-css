# Production selective-rowwise-q12 groupwise cascade

## Decision

**Retain as a backend-equivalent latency candidate; do not call it a new
mathematical-target proof.** The OpenAI GPT-2-small architecture, checkpoint,
and vocabulary are unchanged. This experiment only changes the coarse numeric
representation for 32 of 195 non-hot groups.

The selected groups are those most often visited by baseline-q10 tail states.
Their 8,192 q10 rows are replaced by rowwise q12 rows encoded as radix-64
high/residual values in three 256-axis font pairs. This changes each selected
row from three to six glyphs, adding 24,576 shaped glyphs and 10.77 MB of WOFF2
data. Every stored and shaped plane advance fits the OpenType uint16 range.

## Scaling result

The live q12 group transport differs from its mathematical width by -14 to +6
score buckets over the six hard fixtures. A 27-bucket outward allowance,
matching the retained token-gate contract, covers every measured q12 group.

With that allowance, the 1,024-state offline route changes from the retained
q10 mean 2.402 / p95 7 / max 23 groups to **mean 1.912 / p95 5 / max 16**.
The six browser fixtures use 17, 14, 13, 11, 8, and 1 live stages, versus 19,
18, 17, 13, 10, and 1 on the retained q10 page.

Paired Chrome mutations favor selective q12:

| Metric | Selective q12 | Retained q10 | Ratio |
| --- | ---: | ---: | ---: |
| Mean, four fixtures | 9.674 s | 12.489 s | **0.775x** |
| Median | 12.164 s | 15.753 s | **0.772x** |
| Minimum | 3.339 s | 2.749 s | 1.214x |
| Maximum | 13.393 s | 20.796 s | 0.644x |

This is a hard-tail win, not a universal mutation win: the easiest measured
case regresses because it pays the always-on q12 rows but needs only one exact
group either way.

## Correctness boundary

All six selective-q12 final browser tokens and buckets are identical to the
retained production page. All visited groups, fine winners and buckets,
incumbents, stop decisions, bounds, and script-free checks pass relative to
that browser backend.

One newly selected max-tail state exposes an inherited accuracy hole: both
pages choose token 2032, while the mathematical global-q16 target and original
float GPT-2 choose token 37848. Their global-q16 mathematical separation is
seven score buckets, within the existing q16 font transport allowance. The
selective-q12 page therefore preserves current backend semantics but is not an
all-fixture proof of the intended q16 target.

Raw evidence:

- `browser-results.json`: mathematical-target verifier and paired timing;
- `output-comparison.json`: selective-q12 versus retained final outputs;
- `coarse-diagnostics.json`: measured q10/q12 coarse transport deltas;
- `reference.json`: corpus route, selected groups, fonts, and fixtures.

Nothing was committed or pushed.

