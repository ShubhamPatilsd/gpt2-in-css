#!/bin/zsh
# R3M scratch build: like compile-combined4.sh but with a chosen tools dir and output dir (for offline A/B of one flag).
# usage: compile-scratch.sh <tools-dir> <output-dir>
set -e
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R3M
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=${R2C_HOIST_FVS:-1} R2C_HOIST_STAGES=${R2C_HOIST_STAGES:-1} R2C_HOIST_QUERY=${R2C_HOIST_QUERY:-1} R2C_HOIST_EMBEDDING=${R2C_HOIST_EMBEDDING:-1}
export R2F_LEAN_HANDSHAKE=${R2F_LEAN_HANDSHAKE:-1}
export R2D_HEAD_LOCK=${R2D_HEAD_LOCK:-1} R2D_OVERFLOW_CLIP=${R2D_OVERFLOW_CLIP:-1} R2D_POINTER_EVENTS=${R2D_POINTER_EVENTS:-0} R2D_CONTAIN_PAINT=${R2D_CONTAIN_PAINT:-1}
export R2G_SCOPED_HAS=${R2G_SCOPED_HAS:-1} R3R_FOLD_HOP=${R3R_FOLD_HOP:-1} R3H_BLOCKFLOW_MAX=${R3H_BLOCKFLOW_MAX:-1}
env | grep -E '^(F4|R2C|R2F|R2D|R2G|R3R|R3H)_' | sort | tr '\n' ' '; echo "-> $2"
nice -n 19 uv run --with numpy --with fonttools --with pillow --with brotli \
  python $1/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original --output $2
