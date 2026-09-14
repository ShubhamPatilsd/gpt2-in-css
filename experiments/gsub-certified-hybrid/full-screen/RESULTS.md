# Full-screen GSUB-certified hybrid

Decision: **pass-conservative**. Chrome 153.0.8010.36 completed one exhaustive 10 × 197 pass in 729.9 seconds. The CSS-selected final token matched the separate exact page in 1970/1970 comparisons, and the separate exact page matched the authoritative source exact result in all 1970 cases.

The semantic safety gate passed with **0 unsafe accepts**. The 11 source-route differences were all source-accept → CSS-fallback, so they increase work without risking a wrong accepted winner. Ten are partial final group 196: only 81 candidates are valid, while padded duplicate slots make the CSS runner margin zero. The remaining fixture 3 / group 18 case also exposed conservative stale/duplicate runner state with margin zero.

The actual CSS route accepted 1733 cases (87.97%) and fell back on 237 (12.03%): 20 forced group-0/1 cases and 217 rendered margins at or below six buckets.

Overall mean in-page time was 135.74 ms hybrid versus 220.16 ms exact: 1.62× throughput-equivalent speedup, or 38.3% less time. Medians were 47.20 ms versus 220.10 ms. Hybrid p95 was worse (456.70 ms versus 238.80 ms) because fallback evaluates the GSUB topology and exact stage.

| Route | Cases | Hybrid median | Hybrid p95 | Exact median | Exact p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| accepted | 1733 | 45.40 ms | 259.70 ms | 220.20 ms | 238.70 ms |
| fallback | 237 | 448.30 ms | 493.60 ms | 218.00 ms | 239.00 ms |

| Hybrid route transition | Cases | Median | p95 |
| --- | ---: | ---: | ---: |
| start->fallback | 1 | 455.70 ms | 455.70 ms |
| fallback->fallback | 47 | 464.20 ms | 490.70 ms |
| fallback->accepted | 189 | 46.70 ms | 259.70 ms |
| accepted->fallback | 189 | 442.60 ms | 493.80 ms |
| accepted->accepted | 1544 | 45.30 ms | 259.60 ms |

Timings are direct per-case in-page measurements from the single exhaustive pass, rotating hybrid-first and exact-first order. They include input mutation and synchronous geometry observation.

The artifact reuses 82,510,284 bytes of GSUB WOFF2 fonts and 79,431,996 bytes of exact-scorer WOFF2 fonts; no fonts were copied or rebuilt. Exact dispatch CSS is 5,001,240 bytes, and generated full-screen files total 1,218,006 bytes.

Raw diagnostics remain in browser-results.json. The 67 exact-versus-offline-oracle group-local differences are diagnostic because the separate/source exact browser result is authoritative. Chrome's ten group-0 feature strings normalize cv01 value 1 to `"cv01"` and are accepted.

## Caveat

The six-bucket gate is an empirical bound for this generated font bank and tested Chrome build. It is not a portable proof for arbitrary hidden vectors, fonts, rendering engines, or browser versions.
