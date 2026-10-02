#!/bin/zsh
# R7B: rebuilds with the .pg hide fix (display:none!important): demo-c36.next, smoke-r7b-2L, twins/c32-on
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R7B
until [[ -f $R/DONE-builds4 && -f $R/CHAIN-2-DONE ]]; do sleep 15; done
$R/build_when_free.sh $R/logs/build-demo-c36-v2.log $W/bundles/demo-c36.next 36 12
$R/build_when_free.sh $R/logs/build-twin-c32-on-v2.log $R/twins/c32-on 32 12
$R/build_when_free.sh $R/logs/build-smoke-2L-v2.log $R/smoke-r7b-2L 36 2
touch $R/DONE-builds5
