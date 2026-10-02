#!/bin/zsh
# R7B chain 3 (typed prompts, headless, after the .pg-fix rebuilds): (1) 2-layer typed smoke "Once upon a time" T=0 -> 35 epochs (prefill skip + stop at 35) vs reference_once-upon-a-time_s0_t0_2L.json;
# (2) demo-c36.next typed "Once upon a time" T=0 vs reference_once-upon-a-time_s0_t0.json (35 epochs); (3) seed 17 T=1.0; (4) seed 42 T=0.7.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R7B; cd $W
logline() { echo "- $(date '+%F %T') [R7B chain3] $*" >> $W/R7B.log.md; echo "$(date '+%T') $*"; }
run() { local label=$1 cap=$2; shift 2; while true; do $R/with_lock.sh $label $cap "$@"; local rc=$?; (( rc == 8 || rc == 9 )) || return $rc; logline "$label refused (rc=$rc) — retrying in 60 s"; sleep 60; done; }
until [[ -f $R/DONE-builds5 ]]; do sleep 15; done
T='Once upon a time'; IDS='[7454,2402,257,640]'
if [[ ! -f $R/DONE-typed-smoke ]]; then
  B0_TYPED_PROMPT=$T B0_TYPED_IDS=$IDS B0_STOP_TOKEN=35 REF_JSON=$R/reference_once-upon-a-time_s0_t0_2L.json run smoke-once-t0 900 $R/c32_inner.sh smoke-r7b-2L once-t0 700000 36 > $R/logs/chain3-smoke-once.out 2>&1
  logline "2L typed smoke Once T=0: $(grep -o '^ids [0-9]*/[0-9]*' $R/run-smoke-r7b-2L/once-t0.summary.md | head -1); $(grep -o '^NEW tokens.*' $R/run-smoke-r7b-2L/once-t0.summary.md); $(grep -o '^prefill epochs.*' $R/run-smoke-r7b-2L/once-t0.summary.md); $(grep -h '"r7b-state"' $R/run-smoke-r7b-2L/once-t0.stdout.log | cut -c1-300)"
  touch $R/DONE-typed-smoke
fi
if [[ ! -f $R/DONE-c36-once-t0 ]]; then
  B0_TYPED_PROMPT=$T B0_TYPED_IDS=$IDS B0_STOP_TOKEN=35 REF_JSON=$R/reference_once-upon-a-time_s0_t0.json run c36-once-t0 2760 $R/c32_inner.sh demo-c36.next once-t0 2500000 36 > $R/logs/chain3-c36-once-t0.out 2>&1
  logline "demo-c36 typed Once T=0: $(grep -o '^ids [0-9]*/[0-9]*' $R/run-demo-c36.next/once-t0.summary.md | head -1); $(grep -o '^prefill epochs.*' $R/run-demo-c36.next/once-t0.summary.md); $(grep -o 'total .*' $R/run-demo-c36.next/once-t0.summary.md); $(grep -o 'RSS peak.*' $R/run-demo-c36.next/once-t0.summary.md)"
  touch $R/DONE-c36-once-t0
fi
if [[ ! -f $R/DONE-c36-once-s17 ]]; then
  B0_TYPED_PROMPT=$T B0_TYPED_IDS=$IDS B0_STOP_TOKEN=35 B0_SEED=17 B0_TEMP=1 REF_JSON=$R/reference_once-upon-a-time_s17_t1.0.json run c36-once-s17 2760 $R/c32_inner.sh demo-c36.next once-s17-t1 2500000 36 > $R/logs/chain3-c36-once-s17.out 2>&1
  logline "demo-c36 typed Once seed 17 T=1.0: $(grep -o '^ids [0-9]*/[0-9]*' $R/run-demo-c36.next/once-s17-t1.summary.md | head -1); $(grep -o 'total .*' $R/run-demo-c36.next/once-s17-t1.summary.md)"
  touch $R/DONE-c36-once-s17
fi
if [[ ! -f $R/DONE-c36-once-s42 ]]; then
  B0_TYPED_PROMPT=$T B0_TYPED_IDS=$IDS B0_STOP_TOKEN=35 B0_SEED=42 B0_TEMP=0.7 REF_JSON=$R/reference_once-upon-a-time_s42_t0.7.json run c36-once-s42 2760 $R/c32_inner.sh demo-c36.next once-s42-t0.7 2500000 36 > $R/logs/chain3-c36-once-s42.out 2>&1
  logline "demo-c36 typed Once seed 42 T=0.7: $(grep -o '^ids [0-9]*/[0-9]*' $R/run-demo-c36.next/once-s42-t0.7.summary.md | head -1); $(grep -o 'total .*' $R/run-demo-c36.next/once-s42-t0.7.summary.md)"
  touch $R/DONE-c36-once-s42
fi
touch $R/CHAIN-3-DONE; logline "chain 3 done"
