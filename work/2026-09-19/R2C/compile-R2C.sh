#!/bin/zsh
# R2C: combined (F2+F5+F4) + hoisted list arithmetic (R2C_HOIST_FVS=1; R2C_HOIST_STAGES/QUERY/EMBEDDING=0 disable one population).
# Same command as work/2026-09-19/F4/compile-combined.sh except the tools copy and the output dir.
set -e
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R2C
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=${R2C_HOIST_FVS:-1} R2C_HOIST_STAGES=${R2C_HOIST_STAGES:-1} R2C_HOIST_QUERY=${R2C_HOIST_QUERY:-1} R2C_HOIST_EMBEDDING=${R2C_HOIST_EMBEDDING:-1}
out=${1:-/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R2C}
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output $out
