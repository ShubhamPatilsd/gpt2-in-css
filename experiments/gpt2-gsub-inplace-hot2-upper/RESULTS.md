# In-place GSUB hot-2 upper/fine feasibility

Decision: **reject offline topology; browser not launched**.

The requested 512-row removal is impossible with the production split-complement scorer. GSUB selects group-specific glyph rows, but it does not compute argmax: each group maximum still needs 256 overlaid CSS Grid candidates. Because the router needs groups 0 and 1 at the same time, two independently feature-selected top grids are required. Their lower bound is **512 candidate elements**, exactly the retained K=2 count, so **0/512 rows are removed**.

## Top-two cost

The top anchor can carry its score bucket and tie-coded winner through the existing router, but it cannot also reveal the runner-up margin. Certification needs a winner-masked second Grid pass.

- Lazy runner: +256 candidate elements and +3,328 shaped glyph instances per selected hot visit, before any exact fallback.
- Eager runners for both simultaneous groups: 1,024 top-plus-runner candidates, **+512** versus retained K=2.
- A near-margin case still needs the 256-row exact fallback.

The split scorer uses 13 glyphs per candidate versus 12 for the retained exact rows. The unavoidable top layer therefore rises from 6,144 to 6,656 glyph instances (**+512, 8.3%**) before the runner. Eager top-two reaches 13,312, **+7,168 (116.7%)**.

The 963,044-byte split bank is additive, not a substitute for the retained exact bank: non-hot groups and near-margin fallbacks still require the full exact fonts.

## Semantics and allowance

Existing Chrome fixture evidence remains favorable in isolation: 19/20 group cases accept at GSUB margin >4, 1 falls back, all 20 winners match, and there are 0 unsafe accepts. A routing wrapper would need **26 buckets (104px)**: the existing 24-bucket browser allowance plus the observed ±2 GSUB candidate error.

No corpus claim is made. The ±2 error radius is an empirical Chrome/fixture observation, and no browser-realized split-GSUB deltas exist for the 1,024-state corpus.

## Gate outcome

The offline gate fails both requested scaling conditions: candidate rows are not removed and per-candidate glyph work increases. Consequently this probe emits only the feasibility report and reference; it does not emit `index.html`, does not launch Chrome, and does not run the two-fixture or full-ten screens.
