#!/bin/zsh
# R7B NumPy references (single-threaded BLAS, nice 19): T=0 35-epoch "Once upon a time"; sampled seed 17 T=1.0 and seed 42 T=0.7; "Hello" (consistency vs R4C) and "I" (vs R4P).
set -u
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R7B
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R7B/tools
run() { nice -n 19 uv run --with numpy --with fonttools --with pillow python reference_r7b.py "$@" ; }
run "Once upon a time" reference_once-upon-a-time_s0_t0.json 32 0 0 > logs/ref-once-t0.log 2>&1
run "Once upon a time" reference_once-upon-a-time_s17_t1.0.json 32 17 1.0 > logs/ref-once-s17-t1.0.log 2>&1
run "Once upon a time" reference_once-upon-a-time_s42_t0.7.json 32 42 0.7 > logs/ref-once-s42-t0.7.log 2>&1
run "Hello" reference_hello_s0_t0.json 32 0 0 --no-float > logs/ref-hello-t0.log 2>&1
run "I" reference_I_s0_t0.json 32 0 0 --no-float > logs/ref-I-t0.log 2>&1
run "Shubham was" reference_shubham-was_s0_t0.json 32 0 0 --no-float > logs/ref-shubham-t0.log 2>&1
touch DONE-references
# 2-layer smoke references (dropdown Hello allowed now; typed Once held until R6X's fix)
run "Hello" reference_hello_s0_t0_2L.json 32 0 0 2 --no-float > logs/ref-hello-t0-2L.log 2>&1
run "Hello" reference_hello_s17_t1.0_2L.json 32 17 1.0 2 > logs/ref-hello-s17-t1.0-2L.log 2>&1
run "Once upon a time" reference_once-upon-a-time_s0_t0_2L.json 32 0 0 2 --no-float > logs/ref-once-t0-2L.log 2>&1
touch DONE-references-2L
