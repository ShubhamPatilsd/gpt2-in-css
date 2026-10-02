# bundles/R4T2 — combined4 + R4T_CONSUMER_CHUNK=64 on the matvec + bridge sites only (R4T_CHUNK_SITES=matvec,bridge)

Built by R4T on 2026-09-21 (`work/2026-09-19/R4T/R4T_CHUNK_SITES=matvec,bridge compile-R4T.sh R4T2 12 8`; tools copy `work/2026-09-19/R4T/tools` = `R3M/tools` + `r4t_consumer_chunk.py`
+ 5 patched files, diff below / `R4T/tools-vs-R3M.diff`; fonts and F2's projection shards reused via the `experiments` / `data` / `assets -> ../F4/assets` /
`global-projection-assets -> ../F2/…` symlinks beside the tools copy — no new font files). Recipe = `bundles/combined4/BUILD.md` + one flag.

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4T
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=1 R2C_HOIST_STAGES=1 R2C_HOIST_QUERY=1 R2C_HOIST_EMBEDDING=1
export R2F_LEAN_HANDSHAKE=1
export R2D_HEAD_LOCK=1 R2D_OVERFLOW_CLIP=1 R2D_POINTER_EVENTS=0 R2D_CONTAIN_PAINT=1
export R2G_SCOPED_HAS=1 R3R_FOLD_HOP=1 R3H_BLOCKFLOW_MAX=1
export R4T_CONSUMER_CHUNK=64 R4T_CHUNK_SITES=matvec,bridge
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R4T2
```

## Flag

| flag | default | effect |
|---|---|---|
| `R4T_CHUNK_SITES` | matvec,bridge (tools default: matvec,bridge,loop,embedding) | which consumer sites are chunked; R4T2 leaves `.loop-reader` (768) and `.embedding-consumer-N` (256) whole -> no `.loop-reader-cK` chain and no `--lp-*:inherit` fan-out (R4T.md §R4T2). Manifest `r4tChunkSites`. |
| `R4T_CONSUMER_CHUNK` | 64 | animations per consumer element for the matvec consumers (`.shared-qkv/attn/fc-cN`: 512 → 64), the cache bridge and the b11 bridge (`.cache-bridge-cN`, `.b11-bridge-cN`: 512 → 64), the R3R loop reader (`.loop-reader` 768 → 12 nested `.loop-reader-cK`), the embedding consumers (`.embedding-consumer-N` 256 → 64). `0` = off (= combined4). Manifest `r4tConsumerChunk`. |

Why (`work/2026-09-19/R4T.md`): Blink's per-frame cost for a carrier whose width changed is 14 µs + 46 ns × (animations on its consumer element)
(fixture fit, R² 0.996): 38 µs at 512 (= R3A's measured 40 µs), 17 µs at 64, flat below (knee). Same animations, same decode declarations, same
passes and frames — only the elements holding the `animation-name`/`animation-timeline` lists are split (each chunk element is an ancestor of the
readers; every published number is an inherited registered property).

## Why a second variant
B5's first 12-layer pair of R4T came out +2.3 s/token (contended, load 30) with layout as well as style inflated; the 2-layer smoke shows no steady-state style
penalty. R4T2 removes the only structural additions that a 12-layer build could plausibly pay for beyond the matvec/bridge chunks — the 12-element
loop-reader chain with its 4,224 `--lp-*:inherit` forwarding declarations and the 12 embedding consumers — while keeping the knee on the 7,680 per-layer
hop carriers. Consumer elements 1,200 -> 1,088 (+924 vs combined4).

## Offline verification (`R4T_CHUNK_SITES=matvec,bridge R4T/offline_check_r4t.py bundles/R4T2 bundles/combined4`, log `R4T/offline_check-R4T2.log`)
```
max animations per element (bundle): {'.shared-qkv-cN': 64, '.shared-attn-cN': 64, '.shared-fc-cN': 64, '.cache-bridge-cN': 64, '.fvs-score-reader': 96, '.loop-reader': 768, '.bN-bridge-cN': 64, '.embedding-consumer-N': 256, '.feedback-reader': 8}
max animations per element (ref):    {'.shared-qkv-cN': 512, '.shared-attn-cN': 512, '.shared-fc-cN': 512, '.cache-bridge-cN': 512, '.fvs-score-reader': 96, '.loop-reader': 768, '.bN-bridge-cN': 512, '.embedding-consumer-N': 256, '.feedback-reader': 8}
inherit-forwarding declarations on chunk elements (bundle): {'shared-qkv': 0, 'shared-attn': 0, 'shared-fc': 0, 'cache-bridge': 0, 'loop-reader': 0, 'b11-bridge': 0, 'embedding-consumer': 0}
consumer elements bundle/ref: 1180 164
non-consumer CSS identical (38973628 B ref, 39127036 B bundle incl. consumer rules)
elements bundle/ref: 67504 67401 delta 103
HTML identical modulo consumer wrapper elements
manifest keys differing: {'r4tConsumerChunk': (None, 64), 'r4tChunkSites': (None, ['bridge', 'matvec'])}
font-witnesses identical (modulo tools dir): True 283
RESULT: PASS
```
Non-consumer CSS byte-identical to combined4; HTML identical modulo the wrapper elements; manifest differs only by `r4tConsumerChunk` / `r4tChunkSites`; `.loop-reader` (768) and `.embedding-consumer-N` (256) intentionally unchunked; 283/283 font witnesses identical.

## Chrome runs
- 2-layer smoke `smoke-R4T2-2L` (03:24): ids [11, 3387]; counts vs ref / R4T:

| bundle | frames | UpdateLayoutTree | Layout | ULT ms | Layout ms | paint lifecycle ms | animate ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| ref (chunk 0) | 26 | 53 | 32 | 6232 | 3103 | 1018 | 715 |
| R4T (all sites) | 26 | 53 | 32 | 6676 | 3111 | 396 | 743 |
| R4T2 (matvec,bridge) | 27 | 53 | 32 | 6801 | 3248 | 539 | 855 |

- ONE passive 8-token correctness run (`R4T/run_correctness.sh R4T2`): see `R4T.md` / `R4T/run-R4T2/` (READY written on 8/8 + verify rc 0).

## Diff of the tools copy vs `work/2026-09-19/R3M/tools` (`diff -ru`, = `R4T/tools-vs-R3M.diff`)
(same tools copy as bundles/R4T; the R4T2 build differs only by the environment flag)
