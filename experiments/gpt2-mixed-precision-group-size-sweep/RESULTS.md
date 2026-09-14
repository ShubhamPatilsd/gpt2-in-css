# Mixed exact-upper group-size/score-stride sweep

Browser status: **not launched**. The analysis and candidate selection are offline-first on the 1,024-state Chromium-realized coordinate corpus.

## Result

All variants retain **1,024/1,024** rounded-bucket targets and pass every emitted lower-token tie check. The formal frontier is **g128-s4, g256-s4, g512-s8, g1024-s16**. Browser artifacts are prepared only for **g128-s4, g512-s8, g1024-s16**; `g256-s4` is the already-retained control.

The offline weighted proxy favors **g128-s4** by only **1.1%** versus retained G256: it cuts dynamic candidate-row work by 43.8%, but raises route p95 from 17 to 20 and more than doubles mean router source/match work. G512 and G1024 shorten routes, but their larger dynamic grids raise the weighted proxy by 2.1% and 4.9%. Retain G256 as the default until browser timing can determine whether G128's row savings outweigh its router topology.

| Variant | Groups | Exact rows / delta from 512 | Target retained | Route total / mean / med / p95 / max | <=6 | Dynamic grids / candidate rows | Six-stage router elements / mean source+match ops | Fine / upper width range px | Weighted units / vs G256 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| g128-s4 | 393 | 512 / +0 | 1024/1,024 | 5,256 / 5.133 / 3 / 20 / 68 | 815 | 4,391 / 562,048 | 4,758 / 4,034.4 | 1,024–85,498 / 10,628–85,592 | 51,644.1 / 0.989 |
| g256-s4 | 197 | 512 / +0 | 1024/1,024 | 4,727 / 4.616 / 2 / 17 / 60 | 828 | 3,907 / 1,000,192 | 2,406 / 1,818.8 | 1,024–85,500 / 11,920–85,592 | 52,217.9 / 1.000 |
| g512-s8 | 99 | 512 / +0 | 1024/1,024 | 4,145 / 4.048 / 2 / 15 / 45 | 852 | 3,382 / 1,731,584 | 1,230 / 801.5 | 2,048–171,000 / 24,424–171,184 | 53,309.9 / 1.021 |
| g1024-s16 | 50 | 1024 / +512 | 1024/1,024 | 3,279 / 3.202 / 2 / 11 / 34 | 891 | 2,431 / 2,489,344 | 642 / 320.2 | 4,096–342,000 / 51,440–342,368 | 54,777.0 / 1.049 |

The weighted diagnostic uses int10 row = 1, global-int16 row = 1.6, and each router source/match geometry operation = 0.05. It is a transparent screening proxy, not a browser latency claim.

## Encoding and readback

The score quantizer stays at **1/256 logit per bucket** for every row. Only the layout stride changes. A candidate width is `bucket * scoreStride + (groupSize - 1 - local)/64px`; group max strips the tie with `round(down, width, scoreStride)`. Readback divides by the variant stride and decodes `local = groupSize - 1 - round(mod(width, stride) * 64)`. Therefore `scoreStride/groupSize >= 1/64px` is mandatory.

The browser-error allowance remains 24 buckets per side: it is emitted as `24 * scoreStride` pixels. The strict certificate remains `best - nextUpper > 48` after widths are converted back to bucket units.

`g128-s4` leaves 2px of unused fractional space per bucket. `g256-s4`, `g512-s8`, and `g1024-s16` exactly fill the available 64-layout-unit tie payload. For G1024, one hot group is the smallest nonzero prefix, so it necessarily replaces **1,024 exact rows (+512)** rather than 512.

All reported final score widths fit Chromium's 33,554,432px layout ceiling. Width ranges and router accounting are explicit in `offline-results.json`.

Runtime: **2.54s**. No browser or Chrome process was started.

## G128 tie-spacing transport sweep

This is an append-only transport sweep. It inherits G128-s4's 1,024/1,024 target retention, routes, router work, dynamic fine work, exact rows, and weighted proxy unchanged. Only the pixel stride and fractional tie spacing change; no fixture-specific correction is permitted.

| Variant | Score stride px | Tie step px | Layout units / token | 24-bucket allowance / 48-bucket stop px | Maximum encoded fine width px | Fits |
|---|---:|---:|---:|---:|---:|---:|
| g128-s8 | 8 | 0.0625 | 4 | 192 / 384 | 170,999.938 | yes |
| g128-s16 | 16 | 0.1250 | 8 | 384 / 768 | 341,999.875 | yes |
| g128-s32 | 32 | 0.2500 | 16 | 768 / 1536 | 683,999.750 | yes |

Bucket semantics remain 1/256 logit. Each variant emits `localTie * (scoreStridePx / 128)` and decodes `round(mod(width, scoreStridePx) / tieStepPx)`. Browser order is g128-s8, g128-s16, then g128-s32, stopping at the first semantically exact variant.
