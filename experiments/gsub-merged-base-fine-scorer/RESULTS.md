# GSUB merged-base fine-scorer probe

Decision: **reject pure GSUB merged-base path at bounded scale**.

This bounded probe patches each selectable score glyph's hmtx advance to the sum of its original score and zero-HVAR complement advances. GSUB and HVAR table digests are unchanged, and the page renders one glyph per face instead of score-plus-complement.

## Semantic result

The primary comparison against the existing exact CSS-dispatch baseline covered 20,480 candidate buckets and 80 winners. 6,130 buckets differed; maximum absolute delta was 8710. Winner-token agreement was 97.50% and winner-bucket agreement was 77.50%.

At the same safe scale, merged GSUB versus a matched exact CSS-dispatch audit had 4,669 differing buckets, maximum delta 1, and 100.00% winner-token agreement (64/80 winner buckets). This separates merge error from any scale-induced difference relative to the existing 0.1-scale baseline.

## Advance ceiling and remedy

At display scale 0.1, 6/6 high-plane faces exceed Chrome's 32,768 px adjusted-advance ceiling on these fixtures. That source-scale diagnostic had 19,581 differing buckets and maximum delta 12620. The primary probe uses display scale 0.0625; each low-plane font unit is 4 layout-grid units and each high-plane unit is 1024, while the inverse geometry factor preserves the same mathematical score target. All bounded fixture advances clear the ceiling. This is not a proof for every corner of the normalized 768-axis cube. The existing 0.1-scale exact comparator also has 1,627 high-face candidate/fixture advances over the ceiling across 166 face-local token rows. Therefore lowering the scale removes clamp behavior that is part of that browser baseline; the large primary deltas are a semantic change, not an arithmetic rescaling bug.

## Runtime and size

Median isolated group switching was 4.600 ms for merged GSUB and 12.900 ms for existing exact CSS dispatch (64.3% speedup; 25% required). The bounded fonts occupy 3,607,272 WOFF2 bytes and 25,929,024 expanded TTF bytes. The primary DOM has 256 candidate nodes and 12 glyphs per candidate (versus 24 in the score-plus-complement source).

## Full-scale disposition

Bounded exactness failed; full construction is not justified. No full bank was built. A score-only merged full bank would project to roughly 79,431,996 WOFF2 bytes from the existing full score fonts, before any further size optimization.
