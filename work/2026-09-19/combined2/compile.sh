#!/bin/zsh
# combined2 = F2 + F5 + F4 (work/2026-09-19/F4/tools) + F3b chain MLP (f3_chain_mlp.py). Same command as F4/compile-combined.sh except the tools copy and output.
set -e
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/combined2
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F3_CHAIN_MLP=1
name=${1:-combined2}; blocks=${2:-12}; capacity=${3:-8}
/usr/bin/time -l uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks $blocks --capacity $capacity --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/$name
