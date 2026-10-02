# bundles/baseline — current-source rebuild of the pinned capacity-8 bundle (v2 operator fonts)

Built by B0 on 2026-09-18 from an unmodified copy of `tools/` (`work/2026-09-19/B0/tools`).
Recipe = `experiments/optimization-followups-2026-09-17/VALIDATED_RECIPE.md` "current-source build" with `--capacity 8`
(the pinned `experiments/browser-gpt2/demo-font-vector-twelve` flags per its manifest.json / C2 §0).

## Exact command (`work/2026-09-19/B0/compile-baseline.sh`)

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/B0
# every emitter module computes ROOT = Path(__file__).resolve().parents[1]; a tools copy needs these two links
ln -sfn ../../../experiments experiments
ln -sfn ../../../data data
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/baseline
```

Wall time 11 s (all layer fonts already existed under `experiments/gpt2-flat-12block-chain/layer*/`; the
emitter rebuilds fonts only when missing, so nothing under `experiments/` was written). Peak RSS 2.98 GB.

## Diff of the tools copy vs `tools/`

`diff -rq tools work/2026-09-19/B0/tools` (ignoring `__pycache__`): **no differences**.

## Verification against the pinned bundle

| file | pinned | rebuild | |
|---|---|---|---|
| index.html | 6,750,560 B sha256 be238150… | 6,750,560 B sha256 be238150… | **byte-identical** |
| runtime.css | 45,783,674 B | 34,876,568 B | differs: v2 operator fonts (`font-vector-operators-v2/{dot,value}.woff2`, single `P000` value axis) vs v1 (64 duplicated `Q0xx` axes); see structural table in `work/2026-09-19/B0.md` |
| font-witnesses.json | 261 faces | 261 faces | 259 shared faces identical (codepoint/advance/upem); only the 2 operator fonts differ (v1→v2) |
| manifest.json | 737 B | 1,016 B | rebuild adds `fontVectorOperatorVersion: 2`, `kvWindow: 8`, `valueLayout`, `fontBackend`, … ; all shared keys equal |
| static allowlist (`tools/launch_browser_gpt2.py --check`) | 263 files | 263 files, 280,706,452 B | passes, no JS |
| offline q9/q16 reference (`reference_sequence` + head scorer, same code as `tools/verify_browser_gpt2_runtime.py`) | `[11,314,1101,7926,11,475,314,1101]` | same | matches pinned `numerical-results.json` (tokens == referenceQ9Q16) |

Conclusion: the current source does NOT reproduce the pinned bundle byte-for-byte (as `validated-bundles.json`
says: `currentSourceRebuildEquivalent: false`, `fontVectorOperatorVersion: v1`; no v1 emitter source exists in
the repo). Both are benched: the pinned v1 bundle as `pinned`, this rebuild as `baseline`. Fix bundles are
compared against `baseline` (same source, same v2 fonts). Browser-side numerical verification (8/8 ids) is
part of the bench run.

Asset URLs in this bundle's runtime.css point at `../../B0/experiments/...` (through the symlink); the repo's
static servers resolve them to the real `experiments/` files.
