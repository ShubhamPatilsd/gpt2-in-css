# Sibling-index/local-anchor upper router

## Result

Do not accept the sibling-index/local-anchor form as a material source-and-cold-load win.

Chrome 153.0.8010.36 parsed the required `sibling-index()` and `anchor-scope` grammar. All 197 unique-winner positions, 3 tie cases, and 4 visited-mask cases were exact in both routers.

The generic page is 53,669 raw HTML+CSS bytes versus 104,100 bytes for the structurally matched explicit-class baseline, a 48.4% reduction. Median cache-disabled navigation-to-first-result was 32.100 ms versus 31.400 ms, a -2.2% reduction. The materiality gates were at least 20.0% source reduction and 10.0% cold reduction.

Warm winner mutation was measured but is not an acceptance gate: 1.690 ms/mutation for sibling-index versus 1.613 ms/mutation for explicit classes (0.954x baseline/sibling-index). This isolated router probe makes no shaping or end-to-end runtime improvement claim.

## Raw bytes

| Router | HTML | CSS | Total |
| --- | ---: | ---: | ---: |
| sibling-index/local-anchor | 40,111 | 13,558 | 53,669 |
| explicit ID/class | 40,479 | 63,621 | 104,100 |

## Semantics checked

- `CSS.supports()` for tree-counting width expressions and `anchor-scope`.
- Computed candidate indices 1, 99, and 197, including inherited registered-integer values on match elements.
- Repeated computed `--local-score` anchor names and scopes, with unique globally reduced match anchors.
- A unique 220-bucket maximum at every zero-based group 0 through 196.
- Equal-score ties select the lowest zero-based group index.
- Single, pair, scattered, and all-but-one visited masks.

Full observations and timing samples are in `browser-results.json`.

## Reproduce

```sh
python3 tools/build_sibling_index_upper_router_probe.py
SIBLING_INDEX_ROUTER_RUN_CHROME=1 node tools/test_sibling_index_upper_router_probe.mjs
```
