#!/bin/zsh
# R5E chain: smoke pair (light trace, per-pass counts) -> if both smokes emit identical tokens -> 12-layer correctness run of bundles/R5E.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
logline() { echo "- $(date '+%F %T') [R5E chain] $*" >> $W/R5E.log.md; echo "$*"; }
while [[ ! -f $W/bundles/R5E/manifest.json ]]; do sleep 20; done   # 12-layer candidate build
logline "chain start"
$W/R5E/run_smoke.sh smoke2L smoke-R5E-2L-ref smoke-R5E-2L
ref=$(grep -o '"tokens":\[[^]]*\]' $W/R5E/runs/smoke-R5E-2L-ref/harness.log | tail -1)
cand=$(grep -o '"tokens":\[[^]]*\]' $W/R5E/runs/smoke-R5E-2L/harness.log | tail -1)
logline "smoke tokens ref=$ref cand=$cand"
if [[ -n $ref && $ref == $cand ]]; then
  logline "smoke PASS -> correctness run bundles/R5E"
  $W/R5E/run_correctness.sh R5E
else
  logline "smoke FAIL or missing tokens -> NOT running the 12-layer correctness run"
fi
$W/R5E/finish.sh
touch $W/R5E/CHAIN-DONE
