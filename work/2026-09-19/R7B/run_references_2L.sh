#!/bin/zsh
set -u
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R7B
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R7B/tools
run() { nice -n 19 uv run --with numpy --with fonttools --with pillow python reference_r7b.py "$@" ; }
run "Hello" reference_hello_s0_t0_2L.json 32 0 0 2 --no-float > logs/ref-hello-t0-2L.log 2>&1
run "Hello" reference_hello_s17_t1.0_2L.json 32 17 1.0 2 > logs/ref-hello-s17-t1.0-2L.log 2>&1
run "Once upon a time" reference_once-upon-a-time_s0_t0_2L.json 32 0 0 2 --no-float > logs/ref-once-t0-2L.log 2>&1
touch DONE-references-2L
