# Mixed-precision hot-2 upper-head feasibility

Browser status: **pending uncontaminated run**.

The offline probe is feasible on the available screens. It replaces the existing 512 int10 upper rows for groups 0/1 with global-int16 rows. The exact `--group-*` grid anchor preserves the standard bucket-plus-lower-token tie for reuse; a shared 24-bucket safety offset is added only to the outer `--score-group-*` routing wrapper. It adds **0 upper rows** and **0 speculative parallel fine rows**.

## Offline exactness

- Ten-fixture final exact winners: 10/10.
- Corpus target retention: 1024/1024.
- Corpus standard lexicographic geometry: 2048/2048.
- Agreement with unrounded raw-score winners (a different contract): 2045/2048.
- Fine-grid evaluations removed along mixed corpus paths: 820.

The probe uses the proven exact fine-stage lexicographic contract: rounded 1/256 score bucket first, lower token ID second. Relative to unrounded raw scores, that standard rule reaches 2,045/2,048 corpus hot-group checks because distinct raw scores can occupy one bucket. An acyclic fitted permutation can repair those three analysis cases, but it is recorded only as diagnostics and is **not used by the browser probe**.

With the common 48-bucket stopping guard, mixed paths visit 4.616 groups on average (median 2, p95 17) versus 5.509 (median 3, p95 18) for the int10-upper control.

## Topology

- Generated HTML: 7,302,659 bytes.
- Generated topology CSS: 704,865 bytes.
- Reused int10 WOFF2: 50,862,612 bytes.
- Reused exact WOFF2: 79,431,996 bytes.
- No fonts were copied or rebuilt. The current exact bank is full-vocabulary; possible 512-glyph subsetting is not counted.

The browser test will overwrite this report with measured results once no other Chrome/layout benchmark is running.
