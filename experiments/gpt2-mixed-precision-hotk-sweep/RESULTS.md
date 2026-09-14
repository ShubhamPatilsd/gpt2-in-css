# Mixed-precision hot-K sweep

Browser screening status: **complete**. Exactly one paired round over all ten fixtures was run for K=1,2,4,8. No robust repeat was performed.

## Browser screen

All 40/40 fixture checks passed. This includes every live exact-shadow bucket/winner comparison, stage route/state/certificate check, and dense final-winner gate. There were no failed candidate or control requests.

| K | Warm candidate mean | Paired control mean | Ratio | Speedup | Cold candidate / control | Active visits | Hot reuse | Dynamic grids | Live stages | Dense winners |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4,316.1 ms | 5,355.8 ms | 0.806x | 19.4% | 53,184.5 / 55,577.5 ms | 17 | 9 | 8 | 17/17 | 10/10 |
| 2 | 3,495.5 ms | 5,455.4 ms | **0.641x** | **35.9%** | 58,594.9 / 58,923.4 ms | 13 | 12 | 1 | 13/13 | 10/10 |
| 4 | 4,131.0 ms | 5,667.0 ms | 0.729x | 27.1% | 39,611.0 / 57,611.0 ms | 13 | 12 | 1 | 13/13 | 10/10 |
| 8 | 3,744.7 ms | 5,268.8 ms | 0.711x | 28.9% | 45,296.8 / 57,492.7 ms | 12 | 12 | 0 | 12/12 | 10/10 |

K=2 wins the paired warm ratio and reproduces the retained hot-2 direction. The retained three-round result was 0.720x; this isolated screen is 0.641x, so direction agrees but the one-round magnitude is not treated as robust.

Benchmark caveat: the long-lived Cursor MCP load was present, as in prior paired benchmarks, and was intentionally not terminated. Chrome 153.0.8010.36 was used. The temporary workspace server was stopped after the run.

## Offline result

## Result

Every policy retained **1,024/1,024** final target groups and passed every standard rounded-bucket-then-lower-token tie check. No policy adds rows: each hot row replaces its existing int10 upper row in place.

The deployable primary sweep uses contiguous low groups `0..K-1`. The nondominated K values under static exact rows, candidate-row work, and route p95 are **0, 1, 2, 4, 8, 16, 32**. The smallest browser screen that preserves the useful knees is **1, 2, 4, 8**; K=2 is retained as the measured anchor/control.

| K | Hot groups | Exact upper rows replaced | Fine grids removed | Total group visits | Route mean / median / p95 / max | Stop <=6 | Target retained | Tie checks | Candidate-row proxy/state |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | `none` | 0 | 0 | 5,641 | 5.509 / 3 / 18 / 61 | 791/1,024 | 1024/1,024 | 0/0 | 51,667.2 |
| 1 | `0` | 256 | 492 | 5,198 | 5.076 / 3 / 18 / 61 | 810/1,024 | 1024/1,024 | 1024/1024 | 51,433.5 |
| 2 | `0,1` | 512 | 820 | 4,727 | 4.616 / 2 / 17 / 60 | 828/1,024 | 1024/1,024 | 2048/2048 | 51,233.8 |
| 4 | `0,1,2,3` | 1,024 | 940 | 4,186 | 4.088 / 2 / 16 / 60 | 851/1,024 | 1024/1,024 | 4096/4096 | 51,068.5 |
| 8 | `0,1,2,3,4,5,6,7` | 2,048 | 1,021 | 3,686 | 3.600 / 2 / 14 / 57 | 881/1,024 | 1024/1,024 | 8192/8192 | 50,923.2 |
| 16 | `0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15` | 4,096 | 1,098 | 3,075 | 3.003 / 1 / 11 / 50 | 918/1,024 | 1024/1,024 | 16384/16384 | 50,751.2 |
| 32 | `0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31` | 8,192 | 1,152 | 2,474 | 2.416 / 1 / 9 / 39 | 957/1,024 | 1024/1,024 | 32768/32768 | 50,587.5 |

The candidate-row proxy is `50,257 upper rows + 256 × mean non-hot visits`; it does not pretend that int10 and global-int16 rows have identical browser cost. `offline-results.json` also records a transparent 1.6x precision-weighted companion proxy.

## Group selection check

Frequency ranking is computed once from the K=0 route, then frozen. It is diagnostic because it was selected on this same corpus. Contiguous low IDs remain the browser policy so selection does not depend on the evaluated states.

| K | Contiguous low | K=0 frequency-ranked | Ranked minus low visits | Ranked minus low dynamic fine visits |
|---:|---|---|---:|---:|
| 0 | `none` | `none` | +0 | +0 |
| 1 | `0` | `0` | +0 | +0 |
| 2 | `0,1` | `0,1` | +0 | +0 |
| 4 | `0,1,2,3` | `0,1,2,3` | +0 | +0 |
| 8 | `0,1,2,3,4,5,6,7` | `0,1,2,3,4,5,6,9` | -8 | -5 |
| 16 | `0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15` | `0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15` | +0 | +0 |
| 32 | `0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31` | `0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,27,28,29,30,34,37` | -16 | -17 |

## Pareto interpretation

- Formal objectives: minimize exact upper rows, candidate-row work proxy, and route p95. Values with identical p95 can dominate a larger K when they do no more dynamic work.
- Browser candidates are a deliberately small representative subset of the nondominated frontier, selected at material marginal-work knees plus retained K=2. This is a screening set, not a browser timing conclusion.
- Exact upper rows replaced are `256 × K`; `upperRowsAdded` is zero for every K.

Offline-analysis runtime: **2.84s**. The separate browser screen is reported above.
