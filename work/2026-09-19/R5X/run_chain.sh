#!/bin/zsh
# R5X Chrome chain: waits for the round-5 machine gate (AC AND ((disk >= 4 GB AND swap used < 4,000 MB) OR (disk >= 3 GB AND swap used < 3,000 MB)); poll 60 s),
# then under CHROME.lock (with_lock.sh: owner "R5X <label> <pid> <time>", touch -c 30 s, 5 s poll, rmdir only own):
# (1) ONE passive 8-token correctness run of bundles/combined8 (+ verify with the merged tools) -> bundles/combined8/READY only on 8/8 ids + verify rc 0;
# (2) ONE 32-token prompt-40 run of bundles/combined8-c32 (bench_native.mjs, keyboard trigger, heap=1, RSS/token, memstate before/after) -> summary + READY on 32/32.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; cd $W
logline() { echo "- $(date '+%F %T') [R5X chain] $*" >> $W/R5X.log.md; echo "$(date '+%T') $*"; }
swap_used_mb() { sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1; }
free_gb() { df -g $W | tail -1 | awk '{print $4}'; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
gate_ok() { on_ac && { { (( $(free_gb) >= 4 )) && (( $(swap_used_mb) < 4000 )); } || { (( $(free_gb) >= 3 )) && (( $(swap_used_mb) < 3000 )); }; }; }
state() { echo "AC=$(on_ac && echo 1 || echo 0) disk=$(free_gb)GB swap_used=$(swap_used_mb)MB lock=$(cat $W/CHROME.lock/owner 2>/dev/null || echo free)"; }
wait_gate() { local n=0; while ! gate_ok; do (( n % 10 == 0 )) && logline "gate closed, waiting ($(state)); poll 60 s"; n=$((n+1)); sleep 60; done; logline "gate open ($(state))"; }
run() { local label=$1 cap=$2; shift 2; while true; do wait_gate; $W/R5X/with_lock.sh $label $cap "$@"; local rc=$?; (( rc == 8 || rc == 9 )) || return $rc; logline "$label refused (rc=$rc: gate/battery) — retrying in 60 s"; sleep 60; done; }
logline "chain armed ($(state))"
run correctness-combined8 1500 $W/R5X/correctness_inner.sh combined8 > $W/R5X/logs/chain-correctness.out 2>&1
crc=$?; logline "correctness rc=$crc -> R5X/logs/chain-correctness.out"; touch $W/R5X/CORRECTNESS-DONE
ids=$(grep -o '"tokens":\[[^]]*\]' $W/R5X/run-combined8/harness.log | tail -1); vrc=$(grep -o 'verify rc=[0-9]*' $W/R5X/logs/chain-correctness.out | tail -1)
if [[ $ids == '"tokens":[11,314,1101,7926,11,475,314,1101]' && $vrc == "verify rc=0" ]]; then
  echo "combined8 READY $(date '+%F %T'): ids 8/8 [11,314,1101,7926,11,475,314,1101], $vrc, run R5X/run-combined8 (harness.log, verify.log); = combined7 + R5E (all flags on) + R5H (R5H_CH_SCORES on, R4S off)" > $W/bundles/combined8/READY; logline "bundles/combined8/READY created ($ids $vrc)"
else logline "NO READY for combined8: ids=$ids $vrc"; fi
B0_PROMPT_TOKEN=40 REF_JSON=$W/R4P/reference_ids_32_40.json run c32-combined8-c32 2760 $W/R5X/c32_inner.sh combined8-c32 c32-p40 2400000 > $W/R5X/logs/chain-c32.out 2>&1
c32rc=$?; logline "c32 rc=$c32rc -> R5X/logs/chain-c32.out"
sm=$W/R5X/run-combined8-c32/c32-p40.summary.md
if [[ -f $sm ]]; then
  ok=$(grep -o '^ids [0-9]*/32' $sm | head -1)
  logline "c32 summary: $ok; RecalcStyle/token: $(grep -E '^\| *[0-9]+ \|' $sm | awk -F'|' '{printf "%s ", $7}' | tr -s ' ' | cut -c1-120)"
  if [[ $ok == "ids 32/32" ]]; then echo "combined8-c32 READY $(date '+%F %T'): prompt 40 32/32 = R4P/reference_ids_32_40.json, run R5X/run-combined8-c32/c32-p40.{json,summary.md}" > $W/bundles/combined8-c32/READY; logline "bundles/combined8-c32/READY created"; else logline "NO READY for combined8-c32 ($ok)"; fi
else logline "c32: no summary produced"; fi
touch $W/R5X/CHAIN-DONE
