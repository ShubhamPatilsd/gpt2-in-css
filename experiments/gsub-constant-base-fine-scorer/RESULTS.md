# Constant-base GSUB fine-scorer probe

Decision: **reject: 40-face constant-base sharding is numerically unstable and slower than CSS dispatch**.

20,480 candidate buckets across 10 fixtures and 8 groups had a maximum absolute delta of 8711 versus the exact CSS-dispatch baseline; 943 comparisons exceeded 10 buckets. Winner-token and winner-bucket agreement were 97.50% and 63.75%. The two winner swaps were both in group 195: fixtures 0 and 9 changed from local 188 to local 26.

Median isolated group switching was 16.600 ms for constant-base GSUB and 13.300 ms for CSS dispatch (-24.8% improvement; 25% required). Load was 650.7 ms versus 49538.2 ms.

The bounded fonts occupy 3,643,512 WOFF2 bytes. The scorer DOM has 263 elements versus 51,778 for the baseline; each candidate has 0 total descendants and 40 codepoints/glyphs total (one glyph for each of 40 faces). No full build was launched.
