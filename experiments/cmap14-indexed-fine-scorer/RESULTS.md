# CMAP format-14 indexed fine-scorer probe

Decision: **reject the 50px bounded salvage; do not build all 197 groups**.

## Salvage configuration

Chrome 153.0.8010.36 tested exactly eight spread groups (`0, 1, 2, 17, 64, 96, 128, 195`) and the same ten certified fixtures as the GSUB indexed probe. The parameterized display scale was 0.05: stage font size 50px, equivalent-base subtraction halved from the 100px path, and score decode factor doubled.

The scalable topology remains 256 candidates, 12 fixed face carriers per candidate, no group-specific candidate copies, and 96 ancestor group/face base declarations: `O(faces*candidates)` DOM and `O(groups*faces)` group CSS.

## Ceiling and sequence checks

All 256 variation selectors and all 24,576 face/base/selector mappings were audited. Chrome reported zero unsupported, split, or malformed sequences. Dynamic switching across all eight groups was valid.

The saturation fix succeeded. The complete certified-fixture calculation bounded face widths at 21,925.412px, and Chrome's audited maximum was 21,916.969px. No measured face reached the 32,768px ceiling. The theoretical maximum over every independent axis corner is 43,443.2px; this probe's safety statement is therefore fixture-bounded, not a portable all-axis proof.

## Buckets, winners, and ties

The recovered scorer was not exact. Of 20,480 candidate buckets, only 1 matched the CSS-dispatched baseline. Delta counts were: 71 at +1, 2,369 at +2, 9,606 at +3, 6,664 at +4, 822 at +5, 4 at +6, and 943 above +6. Maximum absolute delta was 8,714 buckets versus the existing bound of 2. Halving the geometry doubled sensitivity to Chromium's 1/64px layout quantization, accounting for the dominant +2..+5 bias; the tail remains far outside the bound.

Winner-token agreement was 78/80 (97.5%), but winner-bucket agreement was 0/80. Both winner failures were group 195, fixtures 0 and 9: CMAP14 selected local 26 while the baseline selected local 188.

The baseline had a unique top bucket in all 80 cases. CMAP14 had 79 unique cases and one two-way top-bucket tie (fixture 9, group 96, locals 179 and 218); its width tie-break still selected local 179, matching the baseline winner for that case.

## Uncontended switching and sizes

Median isolated switching was 37.800ms for CMAP14 and 12.800ms for the same CSS-dispatched baseline. CMAP14 was 195.3% slower rather than at least 25% faster, so the speed gate failed independently of correctness.

The eight-group artifacts occupy 3,363,152 WOFF2 bytes and 13,016,832 expanded TTF bytes. CSS is 34,629 bytes and HTML is 196,323 bytes.
