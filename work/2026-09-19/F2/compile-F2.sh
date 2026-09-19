#!/bin/zsh
# F2 build: identical to work/2026-09-19/B0/compile-baseline.sh except the tools copy (patched) and the output dir.
# The F2 copy defaults --global-projection and --value-weight-once to ON.
set -e
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/F2
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/F2
