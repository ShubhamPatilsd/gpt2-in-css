#!/bin/zsh
# R6X: NumPy reference ids with the MERGED tools (R5X/run_reference.sh with R6X/tools): 8-token Hello (prompt 15496, teacher inputs) and 32-token free-running prompt 40 vs R4P/reference_ids_32_40.json
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
cp ../R5X/reference_ids.py scratch/reference_ids.py; sed 's#work/2026-09-19/R5X/tools#work/2026-09-19/R6X/tools#' ../R5X/numpy_ids_40.py > scratch/numpy_ids_40.py
PYTHONPATH=tools nice -n 19 uv run --with numpy --with fonttools --with pillow --with brotli python scratch/reference_ids.py > logs/reference_ids.log 2>&1; echo "8-token rc=$?"
PYTHONPATH=tools nice -n 19 uv run --with numpy --with fonttools --with pillow --with brotli python scratch/numpy_ids_40.py > logs/numpy_ids_40.log 2>&1; echo "32-token rc=$?"
touch DONE-numpy
