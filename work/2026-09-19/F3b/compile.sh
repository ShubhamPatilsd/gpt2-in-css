#!/bin/zsh
# F3b build: B0's recipe (work/2026-09-19/B0/compile-baseline.sh) with the F3b tools copy (= F5 tools + f3_chain_mlp.py).
# usage: compile.sh <bundle-name> <blocks> <capacity>   (env: F3_CHAIN_MLP=0 for the timeline A/B, F3_CHAIN_LEVEL=2)
set -e
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/F3b
name=${1:?bundle}; blocks=${2:-12}; capacity=${3:-8}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
out=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/$name
mkdir -p $out
/usr/bin/time -l uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks $blocks --capacity $capacity --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output $out
