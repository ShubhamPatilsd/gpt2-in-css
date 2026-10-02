#!/bin/zsh
# R7B build queue (sequential, each waits for a free CHROME.lock): flags-off twins (byte identity), demo-c36.next, demo-8.r7b, flag-on c32 twin, flags-off c36 twin, 2-layer smokes.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R7B; cd $R
OFF="R7B_PREFILL_HEAD_SKIP=0 R7B_CAPACITY_36=0 R7B_SAMPLING=0"
b() { local log=$1; shift; env "$@" $R/build_when_free.sh $log; }
env R7B_PREFILL_HEAD_SKIP=0 R7B_CAPACITY_36=0 R7B_SAMPLING=0 $R/build_when_free.sh $R/logs/build-twin-c32-off.log $R/twins/c32-off 32 12
env R7B_PREFILL_HEAD_SKIP=0 R7B_CAPACITY_36=0 R7B_SAMPLING=0 $R/build_when_free.sh $R/logs/build-twin-p8-off.log $R/twins/p8-off 8 12
$R/build_when_free.sh $R/logs/build-demo-c36.log $W/bundles/demo-c36.next 36 12
$R/build_when_free.sh $R/logs/build-demo-8-r7b.log $W/bundles/demo-8.r7b 8 12
$R/build_when_free.sh $R/logs/build-twin-c32-on.log $R/twins/c32-on 32 12
env R7B_PREFILL_HEAD_SKIP=0 R7B_CAPACITY_36=0 R7B_SAMPLING=0 $R/build_when_free.sh $R/logs/build-twin-c36-off.log $R/twins/c36-off 36 12
$R/build_when_free.sh $R/logs/build-smoke-2L.log $R/smoke-r7b-2L 36 2
touch $R/DONE-builds
