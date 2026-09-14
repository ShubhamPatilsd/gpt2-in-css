# Mixed-precision hot-2 exact-font subset browser probe

Decision: **retain-subset**.

The retained full-bank mixed page and subset page used identical row topology. The focused same-page sequence was fixture 0 (hot-only), fixture 1 (non-hot to hot), fixture 0, then fixture 1 again. The additional rounds repeated that sequence only after focused semantics and startup-byte gates passed.

## Exactness

- Live exact-shadow checks: 24/24 mutations; 48/48 stage gates.
- Dense final winners: 24/24.
- Subset/full semantic signatures: 12/12.
- Exact-shadow coverage: 4/4 selected fixture/group pairs (4 on route, 0 forced).

## Requested fonts

- Focused subset hot startup exact bytes: 14,137,192; full-bank page: 79,431,996.
- Subset-page startup exact breakdown: 881,772 subset bytes plus 13,255,420 eagerly requested full-bank bytes. The eager full-bank requests are score-h0/l0, so the browser does not realize the static ideal of a subset-only hot load.
- Focused subset total WOFF2 startup bytes: 65,318,216; full-bank page: 130,613,020.
- Full exact bytes lazily requested by the subset page on first non-hot activation: 66,176,576 across 10 responses.
- Full exact bytes requested on the subsequent non-hot activation: 0.

Actual subset-page WOFF2 URLs requested before first non-hot activation (19):

- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head-global16-twoplane/score-h0.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head-global16-twoplane/score-l0.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head/score-d0.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head/score-d1.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head/score-d2.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head/score-d3.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head/score-d4.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-mixed-precision-hot2-upper-subset/score-h0-hot2.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-mixed-precision-hot2-upper-subset/score-h1-hot2.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-mixed-precision-hot2-upper-subset/score-h2-hot2.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-mixed-precision-hot2-upper-subset/score-h3-hot2.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-mixed-precision-hot2-upper-subset/score-h4-hot2.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-mixed-precision-hot2-upper-subset/score-h5-hot2.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-mixed-precision-hot2-upper-subset/score-l0-hot2.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-mixed-precision-hot2-upper-subset/score-l1-hot2.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-mixed-precision-hot2-upper-subset/score-l2-hot2.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-mixed-precision-hot2-upper-subset/score-l3-hot2.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-mixed-precision-hot2-upper-subset/score-l4-hot2.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-mixed-precision-hot2-upper-subset/score-l5-hot2.woff2`

New subset-page WOFF2 URLs requested by first non-hot activation (10):

- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head-global16-twoplane/score-h1.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head-global16-twoplane/score-h2.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head-global16-twoplane/score-h3.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head-global16-twoplane/score-h4.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head-global16-twoplane/score-h5.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head-global16-twoplane/score-l1.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head-global16-twoplane/score-l2.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head-global16-twoplane/score-l3.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head-global16-twoplane/score-l4.woff2`
- `http://127.0.0.1:4191/experiments/gpt2-hvar-grid-output-head-global16-twoplane/score-l5.woff2`

## Timing

Absolute cold times are conditional: PID 16288 (long-running Cursor editor MCP server) remained near 100% CPU by user instruction; paired relative request-byte and semantic results are primary, while absolute cold times are conditional on that load.

| Metric | Subset page mean | Retained full-bank mean |
|---|---:|---:|
| cold load | 49107.9 ms | 61451.8 ms |
| hot fixture-0 mutation | 2482.5 ms | 2349.6 ms |
| first non-hot fixture-1 mutation | 4870.8 ms | 3959.8 ms |
| subsequent non-hot fixture-1 mutation | 2492.9 ms | 2143.2 ms |

Hot semantics are unchanged: **true**. Hot timing ratio is **1.057x**; within the predeclared ±15% small-repeat band: **true**.

### Cold repeat

| Round | Load order | Subset cold | Full cold | Subset startup WOFF2 bytes | Full startup WOFF2 bytes |
|---:|---|---:|---:|---:|---:|
| 0 | subset then full | 52595.5 ms | 60081.5 ms | 65,318,216 | 130,613,020 |
| 1 | full then subset | 42367.7 ms | 64728.0 ms | 65,318,216 | 130,613,020 |
| 2 | subset then full | 52360.3 ms | 59546.0 ms | 65,318,216 | 130,613,020 |

The static bank sizes are 881,772 bytes subset and 79,431,996 bytes full. Measured request figures above count the response Content-Length for actual WOFF2 requests; they do not count declared-but-unrequested faces. Request failures: 0.

Chrome: 153.0.8010.36. Full observations are in browser-results.json; the pre-browser static report is preserved as RESULTS-static.md.
