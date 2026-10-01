#!/bin/zsh
# R6P Chrome chain: waits for the machine gate (AC AND ((disk >= 4 GB AND swap used < 4,000 MB) OR (disk >= 3 GB AND swap used < 3,000 MB)); poll 60 s),
# then under CHROME.lock (with_lock.sh: owner "R6P <label> <pid> <time>", touch -c 30 s, 5 s poll, rmdir only own), ONE run each:
# (1) smoke: R6P/scratch/smoke2-on (2 layers, cap 32) typed "Once upon a time" -> 32 winners vs reference_ids_once_upon_a_time_2layers.json (mechanism check: typed ids, prefill, display)
# (2) bundles/combined8-prompt (cap 8, dropdown Hello, nothing typed) correctness 8/8 + verify rc 0 -> READY (the "ids unchanged" check for part A/B on cap 8)
# (3) bundles/combined8-c32-prompt typed "I" (ids [40]) -> 32/32 vs R4P/reference_ids_32_40.json (= the dropdown-40 reference)
# (4) bundles/combined8-c32-prompt typed "Once upon a time" (ids [7454,2402,257,640]) -> 32 winners vs R6P/reference_ids_once_upon_a_time.json -> READY on (3) and (4)
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R6P; cd $W
logline() { echo "- $(date '+%F %T') [R6P chain] $*" >> $W/R6P.log.md; echo "$(date '+%T') $*"; }
swap_used_mb() { sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1; }
free_gb() { df -g $W | tail -1 | awk '{print $4}'; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
gate_ok() { on_ac && { { (( $(free_gb) >= 4 )) && (( $(swap_used_mb) < 4000 )); } || { (( $(free_gb) >= 3 )) && (( $(swap_used_mb) < 3000 )); }; }; }
state() { echo "AC=$(on_ac && echo 1 || echo 0) disk=$(free_gb)GB swap_used=$(swap_used_mb)MB lock=$(cat $W/CHROME.lock/owner 2>/dev/null || echo free)"; }
wait_gate() { local n=0; while ! gate_ok; do (( n % 30 == 0 )) && logline "gate closed, waiting ($(state)); poll 60 s"; n=$((n+1)); sleep 60; done; logline "gate open ($(state))"; }
run() { local label=$1 cap=$2; shift 2; while true; do wait_gate; $R/with_lock.sh $label $cap "$@"; local rc=$?; (( rc == 8 || rc == 9 )) || return $rc; logline "$label refused (rc=$rc: gate/battery) — retrying in 60 s"; sleep 60; done; }
grep -q 'tk-root{display:contents;--prompt-armed:inherit}' $W/bundles/combined8-c32-prompt/runtime.css || { logline "ABORT: bundles/combined8-c32-prompt lacks the .tk-root hop fix"; exit 2; }
logline "chain armed ($(state))"
ONCE='[7454,2402,257,640]'
# (1) 2-layer smoke, typed "Once upon a time"
B0_TYPED_PROMPT="Once upon a time" B0_TYPED_IDS=$ONCE REF_JSON=$R/reference_ids_once_upon_a_time_2layers.json run smoke2-once 1200 $R/c32_inner.sh smoke2-on smoke2-once 900000 32 > $R/logs/chain-smoke2.out 2>&1
logline "smoke2 rc=$? -> $(grep -o '^ids [0-9]*/32' $R/run-smoke2-on/smoke2-once.summary.md 2>/dev/null | head -1) (R6P/run-smoke2-on/smoke2-once.summary.md)"
# (2) cap 8 correctness, dropdown Hello (nothing typed)
run correctness-combined8-prompt 1500 $R/correctness_inner.sh combined8-prompt > $R/logs/chain-correctness.out 2>&1
crc=$?; ids=$(grep -o '"tokens":\[[^]]*\]' $R/run-combined8-prompt/harness.log | tail -1); vrc=$(grep -o 'verify rc=[0-9]*' $R/logs/chain-correctness.out | tail -1)
logline "correctness rc=$crc ids=$ids $vrc"
if [[ $ids == '"tokens":[11,314,1101,7926,11,475,314,1101]' && $vrc == "verify rc=0" ]]; then
  echo "combined8-prompt READY $(date '+%F %T'): dropdown Hello ids 8/8 [11,314,1101,7926,11,475,314,1101], $vrc, run R6P/run-combined8-prompt (harness.log, verify.log); = combined8 + R6P echo fix + typed prompt (flags off = combined8 byte-identical)" > $W/bundles/combined8-prompt/READY; logline "bundles/combined8-prompt/READY created"
else logline "NO READY for combined8-prompt"; fi
# (3) c32 typed "I" == prompt-40 reference
B0_TYPED_PROMPT="I" B0_TYPED_IDS='[40]' REF_JSON=$W/R4P/reference_ids_32_40.json run c32-typed-I 2760 $R/c32_inner.sh combined8-c32-prompt typed-I 2400000 32 > $R/logs/chain-c32-I.out 2>&1
okI=$(grep -o '^ids [0-9]*/32' $R/run-combined8-c32-prompt/typed-I.summary.md 2>/dev/null | head -1); logline "c32 typed I: $okI"
# (4) c32 typed "Once upon a time"
B0_TYPED_PROMPT="Once upon a time" B0_TYPED_IDS=$ONCE REF_JSON=$R/reference_ids_once_upon_a_time.json run c32-typed-once 2760 $R/c32_inner.sh combined8-c32-prompt typed-once 2400000 32 > $R/logs/chain-c32-once.out 2>&1
okO=$(grep -o '^ids [0-9]*/32' $R/run-combined8-c32-prompt/typed-once.summary.md 2>/dev/null | head -1); logline "c32 typed Once upon a time: $okO"
if [[ $okI == "ids 32/32" && $okO == "ids 32/32" ]]; then
  echo "combined8-c32-prompt READY $(date '+%F %T'): typed 'I' 32/32 = R4P/reference_ids_32_40.json; typed 'Once upon a time' 32/32 = R6P/reference_ids_once_upon_a_time.json (4 prefilled + 29 generated); runs R6P/run-combined8-c32-prompt/typed-{I,once}.{json,summary.md}" > $W/bundles/combined8-c32-prompt/READY; logline "bundles/combined8-c32-prompt/READY created"
else logline "NO READY for combined8-c32-prompt (I: $okI, Once: $okO)"; fi
touch $R/CHAIN-DONE
