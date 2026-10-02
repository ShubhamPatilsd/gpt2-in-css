#!/bin/zsh
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R7B
until [[ -f $R/DONE-builds3 ]]; do sleep 10; done
env R7B_PREFILL_HEAD_SKIP=0 R7B_SAMPLING=0 $R/build_when_free.sh $R/logs/build-twin-c36-cap-only.log $R/twins/c36-cap-only 36 12
touch $R/DONE-builds4
