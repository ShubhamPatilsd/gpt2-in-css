#!/bin/zsh
# R7B: after the first queue, rebuild the cap-32 flags-off twin with the v6 base (R6X_SCROLLBAR_FIX hunk taken 14:15).
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R7B
until [[ -f $R/DONE-builds ]]; do sleep 10; done
env R7B_PREFILL_HEAD_SKIP=0 R7B_CAPACITY_36=0 R7B_SAMPLING=0 $R/build_when_free.sh $R/logs/build-twin-c32-off-v6.log $R/twins/c32-off-v6 32 12
touch $R/DONE-builds2
