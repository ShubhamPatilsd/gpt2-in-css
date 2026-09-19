#!/bin/zsh
# B0 baseline build: VALIDATED_RECIPE.md current-source recipe at capacity 8, run from the tools COPY.
set -e
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/B0
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/baseline
