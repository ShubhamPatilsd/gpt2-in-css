# GSUB split-complement fine-scorer probe

Decision: **retain: split complement removes groups 0/1 overflow with bounded empirical error**.

The focused groups 0/1 run compared 5,120 candidate buckets across 20 winner cases. The maximum absolute split-GSUB versus exact CSS-dispatch delta was 2; the histogram was `-1: 341`, `0: 3,339`, `1: 1,424`, `2: 16`. Winner-token agreement was 20/20 and winner-bucket agreement was 14/20.

Winner margins ranged from 3 to 713 buckets (median 52, p95 522). Using the observed ±2 error radius, a margin strictly greater than 4 accepts 19/20 cases (95.0%) with 0 unsafe accepts. This is an empirical Chrome/fixture gate, not a portable proof.

Median isolated switching was 5.500 ms for split GSUB and 12.400 ms for exact CSS dispatch (55.6% faster). P95 switching was 6.600 ms versus 13.100 ms. The focused bank is 963,044 WOFF2 bytes. The split adds no DOM elements, one shaped glyph per candidate (12 to 13, 8.3%), and 768 h3 font rows.

The score rows retain the production source scale and every per-face common base matches the existing full GSUB bank. The audit reproduces exactly five original over-cap rows: group 0 local 11, group 0 local 13, group 1 local 1, group 1 local 6, group 1 local 31. The largest original h3 complement was 1317 font units. Its largest split parts are 658 and 659; the largest adjusted static part is 16,870.4 px, below Chrome's observed 32,768 px cap. All 512 h3 group/local splits sum exactly to their original integer correction.
