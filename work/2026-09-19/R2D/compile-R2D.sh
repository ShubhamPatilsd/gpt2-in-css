#!/bin/zsh
# R2D: combined (F2+F5+F4) + head lock + per-frame knobs. usage: compile-R2D.sh <bundle-name> [R2D_* env overrides]
# Same command as work/2026-09-19/F4/compile-combined.sh except the tools copy and the output dir.
set -e
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R2D
name=${1:-R2D}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2D_HEAD_LOCK=${R2D_HEAD_LOCK:-1} R2D_OVERFLOW_CLIP=${R2D_OVERFLOW_CLIP:-1} R2D_POINTER_EVENTS=${R2D_POINTER_EVENTS:-0} R2D_CONTAIN_PAINT=${R2D_CONTAIN_PAINT:-1}
echo "R2D_HEAD_LOCK=$R2D_HEAD_LOCK R2D_OVERFLOW_CLIP=$R2D_OVERFLOW_CLIP R2D_POINTER_EVENTS=$R2D_POINTER_EVENTS R2D_CONTAIN_PAINT=$R2D_CONTAIN_PAINT -> bundles/$name"
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/$name
