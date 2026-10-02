#!/bin/zsh
# R7B chain 2: control run — R6X's flags-off 2-layer smoke bundle (smoke-demo-2L, cap 32) with dropdown Hello vs the same 2-layer reference (attribution of the epoch-19 1-q flip).
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R7B; cd $W
logline() { echo "- $(date '+%F %T') [R7B chain2] $*" >> $W/R7B.log.md; echo "$(date '+%T') $*"; }
run() { local label=$1 cap=$2; shift 2; while true; do $R/with_lock.sh $label $cap "$@"; local rc=$?; (( rc == 8 || rc == 9 )) || return $rc; logline "$label refused (rc=$rc) — retrying in 60 s"; sleep 60; done; }
until [[ -f $R/CHAIN-1-DONE ]]; do sleep 15; done
mkdir -p $R/smoke-control-2L; [[ -e $R/smoke-control-2L/index.html ]] || { ln -s $W/R6X/smoke-demo-2L/index.html $R/smoke-control-2L/index.html; ln -s $W/R6X/smoke-demo-2L/runtime.css $R/smoke-control-2L/runtime.css; cp $W/R6X/smoke-demo-2L/manifest.json $R/smoke-control-2L/; }
B0_STOP_TOKEN=32 REF_JSON=$R/reference_hello_s0_t0_2L.json run control-2L-hello 900 $R/c32_inner.sh smoke-control-2L hello-t0 700000 32 > $R/logs/chain2-control.out 2>&1
logline "control (R6X smoke-demo-2L flags off) Hello T=0: $(grep -o '^ids [0-9]*/[0-9]*' $R/run-smoke-control-2L/hello-t0.summary.md | head -1); $(grep -o '^first mismatching.*' $R/run-smoke-control-2L/hello-t0.summary.md)"
touch $R/CHAIN-2-DONE
