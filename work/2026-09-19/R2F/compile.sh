#!/bin/zsh
# R2F build: B0/F4 recipe with the R2F tools copy (= F4 tools + r2f_lean_handshake.py). usage: compile.sh <bundle-name> <blocks> <capacity>
set -e
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R2F
name=${1:?bundle}; blocks=${2:-12}; capacity=${3:-8}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2F_LEAN_HANDSHAKE=${R2F_LEAN_HANDSHAKE:-1}
out=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/$name
mkdir -p $out
/usr/bin/time -l uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks $blocks --capacity $capacity --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output $out
