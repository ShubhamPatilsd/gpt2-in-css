#!/bin/zsh
# R3L build: combined3 recipe (bundles/combined3/BUILD.md) with the R3L tools copy (= R2H tools + r3l_packed_loop.py, flag R3L_PACKED_LOOP default ON).
# usage: compile.sh <bundle-name> [blocks=12] [capacity=8]
set -e
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R3L
name=${1:?bundle}; blocks=${2:-12}; capacity=${3:-8}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=${R2C_HOIST_FVS:-1} R2C_HOIST_STAGES=${R2C_HOIST_STAGES:-1} R2C_HOIST_QUERY=${R2C_HOIST_QUERY:-1} R2C_HOIST_EMBEDDING=${R2C_HOIST_EMBEDDING:-1}
export R2F_LEAN_HANDSHAKE=${R2F_LEAN_HANDSHAKE:-1}
export R2D_HEAD_LOCK=${R2D_HEAD_LOCK:-1} R2D_OVERFLOW_CLIP=${R2D_OVERFLOW_CLIP:-1} R2D_POINTER_EVENTS=${R2D_POINTER_EVENTS:-0} R2D_CONTAIN_PAINT=${R2D_CONTAIN_PAINT:-1}
export R3L_FONT_LOOP=${R3L_FONT_LOOP:-1} R3L_PACKED_LOOP=${R3L_PACKED_LOOP:-0}
out=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/$name
mkdir -p $out
env | grep -E '^(F4|R2C|R2F|R2D|R3L)_' | sort | tr '\n' ' '; echo "-> bundles/$name ($blocks blocks, capacity $capacity)"
/usr/bin/time -l uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks $blocks --capacity $capacity --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output $out
