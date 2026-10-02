#!/bin/zsh
# R7B: cap-8 builds with demo-8's recipe (VALUE_LAYOUT=runs); the first queue built them with widths by mistake.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R7B
until [[ -f $R/DONE-builds2 ]]; do sleep 10; done
rm -rf $R/twins/p8-off $W/bundles/demo-8.r7b
env R7B_PREFILL_HEAD_SKIP=0 R7B_CAPACITY_36=0 R7B_SAMPLING=0 $R/build_when_free_8.sh $R/logs/build-twin-p8-off-runs.log $R/twins/p8-off 8 12
$R/build_when_free_8.sh $R/logs/build-demo-8-r7b-runs.log $W/bundles/demo-8.r7b 8 12
touch $R/DONE-builds3
