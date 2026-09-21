#!/bin/zsh
# R4T build = combined4 recipe (R3M/compile-combined4.sh) with the R4T tools copy (+ r4t_consumer_chunk.py, flag R4T_CONSUMER_CHUNK default 64).
# usage: compile-R4T.sh <bundle-name> [blocks] [capacity]     e.g. compile-R4T.sh R4T 12 8 | compile-R4T.sh smoke-R4T-2L 2 2
set -e
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4T
name=${1:-R4T}; blocks=${2:-12}; capacity=${3:-8}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=${R2C_HOIST_FVS:-1} R2C_HOIST_STAGES=${R2C_HOIST_STAGES:-1} R2C_HOIST_QUERY=${R2C_HOIST_QUERY:-1} R2C_HOIST_EMBEDDING=${R2C_HOIST_EMBEDDING:-1}
export R2F_LEAN_HANDSHAKE=${R2F_LEAN_HANDSHAKE:-1}
export R2D_HEAD_LOCK=${R2D_HEAD_LOCK:-1} R2D_OVERFLOW_CLIP=${R2D_OVERFLOW_CLIP:-1} R2D_POINTER_EVENTS=${R2D_POINTER_EVENTS:-0} R2D_CONTAIN_PAINT=${R2D_CONTAIN_PAINT:-1}
export R2G_SCOPED_HAS=${R2G_SCOPED_HAS:-1} R3R_FOLD_HOP=${R3R_FOLD_HOP:-1} R3H_BLOCKFLOW_MAX=${R3H_BLOCKFLOW_MAX:-1}
export R4T_CONSUMER_CHUNK=${R4T_CONSUMER_CHUNK:-64} R4T_CHUNK_SITES=${R4T_CHUNK_SITES:-matvec,bridge,loop,embedding}
env | grep -E '^(F4|R2C|R2F|R2D|R2G|R3R|R3H|R4T)_' | sort | tr '\n' ' '; echo "-> bundles/$name ($blocks blocks, capacity $capacity)"
nice -n 10 uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks $blocks --capacity $capacity --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/$name
