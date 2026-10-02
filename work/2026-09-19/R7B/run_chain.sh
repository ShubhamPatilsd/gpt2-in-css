#!/bin/zsh
# R7B Chrome chain (dropdown-prompt runs only; typed-prompt runs are HELD until R6X's typed-path fix lands): under with_lock.sh (gate AC/disk/swap/load1, lock owner R7B):
# (1) 2-layer smoke R7B/smoke-r7b-2L, dropdown Hello, T=0 -> stop rule at 32 (cap 36) vs reference_hello_s0_t0_2L.json
# (2) same bundle, seed 17 T=1.0 (selectOption) vs reference_hello_s17_t1.0_2L.json
# (3) bundles/demo-8.r7b, dropdown Hello 8/8 (T=0) vs reference_hello_s0_t0_cap8.json
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R7B; cd $W
logline() { echo "- $(date '+%F %T') [R7B chain] $*" >> $W/R7B.log.md; echo "$(date '+%T') $*"; }
run() { local label=$1 cap=$2; shift 2; while true; do $R/with_lock.sh $label $cap "$@"; local rc=$?; (( rc == 8 || rc == 9 )) || return $rc; logline "$label refused (rc=$rc: gate/battery) — retrying in 60 s"; sleep 60; done; }
until [[ -f $R/DONE-builds ]]; do sleep 15; done
if [[ ! -f $R/DONE-smoke-hello ]]; then
  B0_STOP_TOKEN=32 REF_JSON=$R/reference_hello_s0_t0_2L.json run smoke-hello-t0 900 $R/c32_inner.sh smoke-r7b-2L hello-t0 700000 36 > $R/logs/chain-smoke-hello-t0.out 2>&1
  logline "2L smoke Hello T=0: $(grep -o '^ids [0-9]*/[0-9]*' $R/run-smoke-r7b-2L/hello-t0.summary.md | head -1); $(grep -o '^NEW tokens.*' $R/run-smoke-r7b-2L/hello-t0.summary.md); $(grep -h '"r7b-state"' $R/run-smoke-r7b-2L/hello-t0.stdout.log | cut -c1-400)"
  touch $R/DONE-smoke-hello
fi
if [[ ! -f $R/DONE-smoke-hello-s17 ]]; then
  B0_STOP_TOKEN=32 B0_SEED=17 B0_TEMP=1 REF_JSON=$R/reference_hello_s17_t1.0_2L.json run smoke-hello-s17 900 $R/c32_inner.sh smoke-r7b-2L hello-s17-t1 700000 36 > $R/logs/chain-smoke-hello-s17.out 2>&1
  logline "2L smoke Hello seed 17 T=1.0: $(grep -o '^ids [0-9]*/[0-9]*' $R/run-smoke-r7b-2L/hello-s17-t1.summary.md | head -1); $(grep -h '"sampling-selected"' $R/run-smoke-r7b-2L/hello-s17-t1.stdout.log | cut -c1-300); $(grep -h '"r7b-state"' $R/run-smoke-r7b-2L/hello-s17-t1.stdout.log | cut -c1-400)"
  touch $R/DONE-smoke-hello-s17
fi
until [[ -f $R/DONE-builds3 ]]; do sleep 15; done
if [[ ! -f $R/DONE-demo8 ]]; then
  B0_STOP_TOKEN=8 REF_JSON=$R/reference_hello_s0_t0_cap8.json run demo-8-hello 1200 $R/c32_inner.sh demo-8.r7b hello 900000 8 > $R/logs/chain-demo8-hello.out 2>&1
  logline "demo-8.r7b Hello T=0: $(grep -o '^ids [0-9]*/[0-9]*' $R/run-demo-8.r7b/hello.summary.md | head -1); $(grep -o 'total .* s for .*' $R/run-demo-8.r7b/hello.summary.md); $(grep -o 'RSS peak.*' $R/run-demo-8.r7b/hello.summary.md)"
  touch $R/DONE-demo8
fi
touch $R/CHAIN-1-DONE; logline "chain 1 (dropdown runs) done"
