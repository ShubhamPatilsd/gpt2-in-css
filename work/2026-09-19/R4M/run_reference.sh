#!/bin/zsh
# R4M: NumPy reference ids with the MERGED tools (8-token: R3M/reference_ids.py; 32-token: R4C/reference_ids_32.py -> R4M/reference_ids_32.json)
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4M
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=tools
echo "== $(date '+%F %T') 8-token"; nice -n 19 uv run --with numpy --with fonttools --with pillow --with brotli python reference_ids.py
echo "== $(date '+%F %T') 32-token"; nice -n 19 uv run --with numpy --with fonttools --with pillow --with brotli python reference_ids_32.py
echo "== $(date '+%F %T') done"
