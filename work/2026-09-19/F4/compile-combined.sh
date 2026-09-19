#!/bin/zsh
# combined: F2 + F5 + F4 (packed KV banks + packed head input + numeric list entries), all flags default ON (F4_PACKED_BANKS=0 / F4_PACKED_HEAD=0 / F4_NUMERIC_LISTS=0 revert).
# Same command as work/2026-09-19/B0/compile-baseline.sh except the tools copy and the output dir.
set -e
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/F4
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/combined
