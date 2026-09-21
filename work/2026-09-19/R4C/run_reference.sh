#!/bin/zsh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4C
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=tools
uv run --with numpy --with fonttools --with pillow --with brotli python reference_ids_32.py
