#!/bin/zsh
# R4D: combined4 recipe (R3M) + R4D flags (r4d_flags.py, default ON) -> bundles/$name at --capacity $cap.
# Tools copy work/2026-09-19/R4D/tools = R3M/tools + r4d_flags.py + browser_gpt2_font_vector_cache.py edits (see bundles/<name>/BUILD.md).
set -e
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4D
name=${1:-combined4-c32b}; cap=${2:-32}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=${R2C_HOIST_FVS:-1} R2C_HOIST_STAGES=${R2C_HOIST_STAGES:-1} R2C_HOIST_QUERY=${R2C_HOIST_QUERY:-1} R2C_HOIST_EMBEDDING=${R2C_HOIST_EMBEDDING:-1}
export R2F_LEAN_HANDSHAKE=${R2F_LEAN_HANDSHAKE:-1}
export R2D_HEAD_LOCK=${R2D_HEAD_LOCK:-1} R2D_OVERFLOW_CLIP=${R2D_OVERFLOW_CLIP:-1} R2D_POINTER_EVENTS=${R2D_POINTER_EVENTS:-0} R2D_CONTAIN_PAINT=${R2D_CONTAIN_PAINT:-1}
export R2G_SCOPED_HAS=${R2G_SCOPED_HAS:-1}
export R3R_FOLD_HOP=${R3R_FOLD_HOP:-1}
export R3H_BLOCKFLOW_MAX=${R3H_BLOCKFLOW_MAX:-1}
env | grep -E '^(F4|R2C|R2F|R2D|R2G|R3R|R3H|R4D)_' | sort | tr '\n' ' '; echo "-> bundles/$name capacity=$cap"
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity $cap --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout ${R4D_VALUE_LAYOUT:-runs} --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/$name
