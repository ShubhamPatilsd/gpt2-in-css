#!/bin/zsh
# R5E build = R4M/compile.sh (combined7 recipe: all round-2..4 flags ON, R4T_CONSUMER_CHUNK=64) with the R5E tools copy and blocks/capacity args.
# usage: compile.sh <output-dir> [blocks=12] [capacity=8]   (override flags via the environment, e.g. R5E_ALL=0)
set -e
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R5E
out=${1:?out}; blocks=${2:-12}; cap=${3:-8}; export VALUE_LAYOUT=${VALUE_LAYOUT:-runs}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=${R2C_HOIST_FVS:-1} R2C_HOIST_STAGES=${R2C_HOIST_STAGES:-1} R2C_HOIST_QUERY=${R2C_HOIST_QUERY:-1} R2C_HOIST_EMBEDDING=${R2C_HOIST_EMBEDDING:-1}
export R2F_LEAN_HANDSHAKE=${R2F_LEAN_HANDSHAKE:-1}
export R2D_HEAD_LOCK=${R2D_HEAD_LOCK:-1} R2D_OVERFLOW_CLIP=${R2D_OVERFLOW_CLIP:-1} R2D_POINTER_EVENTS=${R2D_POINTER_EVENTS:-0} R2D_CONTAIN_PAINT=${R2D_CONTAIN_PAINT:-1}
export R2G_SCOPED_HAS=${R2G_SCOPED_HAS:-1} R3R_FOLD_HOP=${R3R_FOLD_HOP:-1} R3H_BLOCKFLOW_MAX=${R3H_BLOCKFLOW_MAX:-1}
export R4S_SMALL_HOPS=${R4S_SMALL_HOPS:-1}
export R4D_EMPTY_UNFILLED=${R4D_EMPTY_UNFILLED:-1} R4D_LEAN_LATCH=${R4D_LEAN_LATCH:-1} R4D_UNPACK_V=${R4D_UNPACK_V:-1} R4D_HIDE_UNFILLED=${R4D_HIDE_UNFILLED:-1} R4D_GATE_SCORES=${R4D_GATE_SCORES:-0}
export R4T_CONSUMER_CHUNK=${R4T_CONSUMER_CHUNK:-64}
mkdir -p $out
env | grep -E '^(F4|R2C|R2F|R2D|R2G|R3R|R3H|R4S|R4T|R4D|R5E)_' | sort | tr '\n' ' '; echo "-> $out ($blocks blocks, capacity $cap, value-layout $VALUE_LAYOUT, tools R5E/tools)"
nice -n ${NICE:-19} uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks $blocks --capacity $cap --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout ${VALUE_LAYOUT:-runs} --font-backend original \
  --output $out
