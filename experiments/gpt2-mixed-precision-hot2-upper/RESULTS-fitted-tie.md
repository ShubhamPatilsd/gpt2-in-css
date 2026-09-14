# Mixed-precision hot-2 upper-head feasibility

Decision: **invalid transport; no scaling decision**.

The probe replaces 512 existing int10 upper rows (groups 0 and 1) with global-int16 rows. It adds **0 upper rows** and **0 speculative parallel fine rows**. A selected hot group reuses its upper anchor after removing the shared 24-bucket safety offset; only selected non-hot groups instantiate the ordinary 256-row fine grid.

## Exactness and feasibility

- Browser fixture checks: 0/10. No browser exactness claim passed.
- Offline corpus target retention: 1024/1024.
- Offline hot-group winner checks: 2048/2048.
- Fine-grid evaluations removed in the browser screen: 12/13 active stage visits.
- Corpus-path fine-grid evaluations removable: 820.

The ordinary lower-token tie code missed 3/2,048 corpus hot-group winners after 1/256 score bucketing. The probe therefore uses an acyclic static tie permutation fit jointly on the ten fixtures and 1,024 corpus states (group 0: 3 precedence edges, group 1: 3 precedence edges) and inverts the code to token ID with CSS `if()`. This is empirically exact on these screens, **not a portable exactness proof for unseen hidden states**.

## Timing

| Metric | Mixed upper | Six-stage exact/int10 control |
|---|---:|---:|
| cold load | 84046.2 ms | 77500.2 ms |
| cold load + first evaluation | 87171.8 ms | 80684.7 ms |
| warm mean (10 fixtures) | 3763.9 ms | 5716.3 ms |
| warm median | 3666.9 ms | 6029.3 ms |
| warm p90 | 4802.7 ms | 7552.8 ms |

Mean ratio: **0.658x** (34.2% faster).

## Topology and bytes

- Generated HTML: 8,247,838 bytes.
- Generated topology CSS: 791,815 bytes; the fitted inverse tie maps account for most of the increase.
- Reused int10 WOFF2: 51,181,024 bytes; reused exact WOFF2: 79,431,996 bytes. No font was copied or rebuilt.
- The current exact assets cover the full vocabulary. A production version could subset them to the 512 hot glyphs, but this probe does not count hypothetical subset savings.

## Interpretation

Every reused hot stage decoded `fineCode=255`/`fineLocal=255`, producing tokens 255 or 511. The bucket-only `--score-group-*` wrapper had discarded the candidate tie fraction, so the encouraging 0.658x warm ratio is invalid for scaling decisions. This run is retained only as a failed-transport diagnostic.

Chrome: 153.0.8010.36. Full observations are in `browser-results-fitted-tie.json`.
