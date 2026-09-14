# Full-197 GSUB-indexed fine-scorer result

Decision: **reject pure GSUB certification; retain as the measured basis for a selective exact-fallback hybrid.**

The full run covered 502,570 candidates and 1,970 group/fixture cases. Maximum absolute delta was 12,008 and winner-token agreement was 1,945/1,970. Groups 2–196 had an empirical maximum candidate delta of 3; groups 0/1 contain the only huge outliers.

GSUB top-1 margins were min 0, median 45, p90 173, p95 293, and max 2,018 buckets. Requiring group >1 and margin >6 certifies 1,744 cases; 226 (11.47%) fall back, including 20 group-0/1 cases and 206 near ties. The final uncontended rerun measured 21.9 ms GSUB / 226.0 ms exact: route weighting is 45.31 ms, while charging the GSUB pass before exact scoring on fallback cases gives 47.83 ms. The <=3 bound is observed, not a portable proof.

Only five h3 correction rows cross Chrome's 32,768 px adjusted-advance cap. A verified real-dummy shifted AlternateSet test left group maxima unchanged at 8,694, 12,008, and 3 for groups 0/1/2, ruling out the self-alternate hypothesis.

The full bank is 82,510,284 WOFF2 bytes / 283,495,200 expanded bytes. Fonts plus CSS save only 2.24% versus the current fine bank plus dispatch CSS. The later CSS-only top-two/fallback composition passes all 1,970 direct full-screen comparisons with zero unsafe accepts. Its actual 12.03% fallback route measures 135.74 ms mean versus 220.16 ms exact (1.62x faster); median improves to 47.20 ms, but fallback worsens p95 to 456.70 ms. See `../../gsub-certified-hybrid/RESULTS.md` and the parent `RESULTS.md` for the construction diagnosis.

A later merged-base probe folds each static complement into its corresponding
score glyph. It removes the independent complement snap at a safe 0.0625 scale
(80/80 bounded winners against a matched-scale exact page, maximum delta one)
and switches in 4.6 ms. It is not production-equivalent: the existing 0.1-scale
exact comparator itself contains clamped high-face advances, and removing that
clamp changes two of 80 winners. See
`../../gsub-merged-base-fine-scorer/RESULTS.md`.

A production-scale repair is successful for the two exceptional groups. The
h3 complement is split into two integer parts whose adjusted advances remain
below Chrome's cap. Across groups 0/1, all 5,120 candidate errors are at most
two buckets and all 20 winners match exact; margin >4 accepts 19/20 with zero
unsafe accepts. It adds one glyph per candidate and switches in 5.5 ms versus
12.4 ms dispatch. See `../../gsub-split-complement-fine-scorer/RESULTS.md`.
