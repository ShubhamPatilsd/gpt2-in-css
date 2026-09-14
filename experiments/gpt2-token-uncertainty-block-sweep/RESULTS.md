# Token uncertainty block-size sweep

## Result

Contiguous block gating preserves the exact winner for every tested state, as expected from the inclusive `max(block upper) >= max(token lower)` rule. It exposes a tunable tradeoff between fewer container-query gates and more exact rows. This is an offline structural screen; browser timing decides whether any point beats the retained full 256-row grid.

The token-granular baseline shapes a mean **30.57** rows over the 1,024-state corpus and **7.60** rows over the ten browser fixtures.

| Block size | Static gates | Mean active blocks (corpus) | Mean shaped rows (corpus) | Row inflation | Mean shaped rows (fixtures) | Fixture inflation |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 256 | 30.57 | 30.57 | 1.00× | 7.60 | 1.00× |
| 2 | 128 | 21.24 | 42.48 | 1.39× | 13.00 | 1.71× |
| 4 | 64 | 13.79 | 55.14 | 1.80× | 20.40 | 2.68× |
| 8 | 32 | 8.54 | 68.32 | 2.23× | 28.80 | 3.79× |
| 16 | 16 | 5.72 | 91.52 | 2.99× | 48.00 | 6.32× |
| 32 | 8 | 3.55 | 113.59 | 3.72× | 70.40 | 9.26× |
| 64 | 4 | 2.66 | 170.31 | 5.57× | 134.40 | 17.68× |
| 128 | 2 | 1.92 | 245.62 | 8.03× | 256.00 | 33.68× |
| 256 | 1 | 1.00 | 256.00 | 8.37× | 256.00 | 33.68× |

## Interpretation

The browser probe should focus on the knee rather than every size: the smallest candidates that materially reduce the 256 gate carriers while keeping exact-row inflation bounded. The raw JSON records minimum, median, p95, maximum, and mean active blocks and shaped rows for every size on both screens.

## Contract

- Group: fixed GPT-2 vocabulary group 0, 256 tokens.
- Target: retained global-int16 head.
- Coarse bound: row-wise signed int10 center plus/minus the Cauchy radius to the global-int16 target.
- Outward allowance: 27 score buckets, matching the token-level browser probe.
- Corpus hidden vectors are snapped to the production axis grid and use the conservative query-norm upper bound.
- A block is active iff any token upper bound in that block is at least the global maximum token lower bound.

Generated in **0.05s** by `tools/analyze_token_uncertainty_block_sweep.py`.
