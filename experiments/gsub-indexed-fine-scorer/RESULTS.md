# GSUB-indexed fine-scorer probe

Decision: **retain the probe and hybrid design; reject pure GSUB certification, and do not yet call the hybrid portable-certified.** Dynamic numbered `cv01` selection is valid and fast. Scores are not bit-exact, but groups 2–196 have an observed bound that makes selective exact fallback promising.

## Strict gate and full scale

The 8-group run compared 20,480 candidates. Its delta histogram was `-2: 1, -1: 2,342, 0: 15,927, +1: 2,209, +2: 1`; one additional bucket does not cover it. Winner-token agreement was 80/80 and winner-bucket agreement 66/80. Switching was 6.1 ms GSUB versus 12.8 ms CSS (52.3% faster). Its WOFF2/expanded sizes are 3,638,420/25,929,024 bytes.

The measured full-197 build compared 502,570 candidates: 311,050 (61.89%) were exact, 496,634 (98.8189%) were within +/-1, and 502,519 (99.9899%) within +/-2. Maximum absolute delta was 12,008. Winner-token agreement was 1,945/1,970 (98.73%), so pure GSUB fails certification.

## Hybrid margin certificate

The harness now records each GSUB winner, runner-up, integer bucket margin, and per-group maximum delta. Across 1,970 cases, margins range from 0 to 2,018 buckets: median 45, p90 173, and p95 293.

Every observed candidate delta in groups 2–196 is at most 3. If that bound holds, a GSUB margin strictly greater than `2 * 3 = 6` guarantees the exact winner. Routing groups 0/1 and margins <=6 to the existing exact scorer gives:

- GSUB-certifiable: 1,744/1,970 (88.53%).
- Exact fallback: 226/1,970 (11.47%): 20 group-0/1 cases and 206 near ties.
- Route-weighted cost at the requested 22.6 ms GSUB / 231.9 ms exact medians: 46.61 ms, 79.90% faster than always exact.
- Sequential declarative estimate: 48.97 ms, 78.88% faster. This charges GSUB before exact scoring for the 206 margin-discovered near ties; groups 0/1 route directly to exact.

The <=3 bound is empirical, not a portable proof. It covers these fonts, Chrome 153, and ten fixtures; unseen activations or another shaper/browser could violate it. Certification still needs an analytic layout-error bound or broader engine/input proof.

## Error causes

Ordinary +/-1 (occasionally +/-2/3) differences come from base normalization. The exact scorer lays out one HVAR glyph and subtracts its serialized base in CSS. This probe adds a static complement glyph. Chrome snaps score and complement independently to its 1/64 px grid before summing; the roughly 75.486 fine-score scale amplifies that residual across bucket boundaries.

The huge full-only errors are a correctable construction problem. Only high-plane h3 corrections for groups 0/1 exceed 1,279 units: group 0 locals 11/13 and group 1 locals 1/6/31. At 100 px and 25,600% `size-adjust`, Chrome clamps their adjusted advances at 32,768 px. A 1,298-unit row should be 33,228.8 px but measures 32,768 px; at 25,000% it correctly measures 32,450 px. The cap is a browser limit, but smaller/split complements or different normalization can avoid it.

The self-alternate hypothesis was tested with a real `probeDummy` at alternate index 1. FontTools verified score indices 1–4 as `probeDummy, y000, y256, y512` and correction indices as `probeDummy, y256, y512, y768`; Chrome used real groups 0/1/2 at feature values 2/3/4. Over three fixtures, maxima remained 8,694, 12,008, and 3. Self-alternation is not causal.

## Declarative CSS feasibility

The margin gate is realizable in principle with existing primitives: decode top-1 from the overlaid grid, inherit its local index through a style container, mask that index in a duplicate 256-candidate grid, take its max as top-2, decode both buckets, and gate on `winnerBucket - runnerBucket > 6` with a size/style container query. Groups 0/1 can bypass GSUB by known group ID. The decision need not use JavaScript.

This adds 256 nodes and another argmax/layout pass, and near ties then activate the exact scorer. Conditional layout/invalidation must be benchmarked in the eventual hybrid; 46.61 ms is a route-weighted lower estimate, while 48.97 ms models the two-stage near-tie path.

## Size and disposition

The full bank occupies 82,510,284 WOFF2 bytes and 283,495,200 expanded bytes. Fonts plus CSS total 82,543,137 bytes versus 84,433,236 bytes for the current fine bank plus dispatch CSS: a 1,890,099-byte (2.24%) saving. Full switching was 22.6 ms GSUB versus 231.9 ms CSS (90.3% faster). Page-load figures remain in JSON but are not directly comparable because page topology differs.

Retain these artifacts for hybrid composition and CMAP14 comparison. Before certification, fix the five overflowing h3 complements, establish a portable <=3 bound, and measure the declarative top-2/fallback composition under uncontended browser conditions.
