#!/bin/zsh
# R6X Chrome chain (= R6P/run_chain.sh protocol): waits for the machine gate (AC AND ((disk >= 4 GB AND swap used < 4,000 MB) OR (disk >= 3 GB AND swap used < 3,000 MB)); poll 60 s),
# then under CHROME.lock (R6X/with_lock.sh: owner "R6X <label> <pid> <time>", touch -c 30 s, 5 s poll, rmdir only own), ONE run each:
# (1) bundles/demo-8 (cap 8) dropdown Hello, nothing typed: correctness 8/8 + verify rc 0 -> READY
# (2) bundles/demo-c32 load-paint probe (R6V's loadpaint.mjs: screenshots 0.5/1/2/4/8… s, load event, Ready) -> R6X/runs/loadpaint-demo-c32/
# (3) bundles/demo-c32 typed "I" -> 32/32 vs R4P/reference_ids_32_40.json (+ screenshots at 8/30/60 s after Run)
# (4) bundles/demo-c32 typed "Once upon a time" -> 32/32 vs R6P/reference_ids_once_upon_a_time.json (+ screenshots 10/40/70 s) -> READY on (3) and (4)
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R6X; cd $W
logline() { echo "- $(date '+%F %T') [R6X chain] $*" >> $W/R6X.log.md; echo "$(date '+%T') $*"; }
swap_used_mb() { sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1; }
free_gb() { df -g $W | tail -1 | awk '{print $4}'; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
gate_ok() { on_ac && { { (( $(free_gb) >= 4 )) && (( $(swap_used_mb) < 4000 )); } || { (( $(free_gb) >= 3 )) && (( $(swap_used_mb) < 3000 )); }; }; }
state() { echo "AC=$(on_ac && echo 1 || echo 0) disk=$(free_gb)GB swap_used=$(swap_used_mb)MB lock=$(cat $W/CHROME.lock/owner 2>/dev/null || echo free)"; }
wait_gate() { local n=0; while ! gate_ok; do (( n % 30 == 0 )) && logline "gate closed, waiting ($(state)); poll 60 s"; n=$((n+1)); sleep 60; done; logline "gate open ($(state))"; }
run() { local label=$1 cap=$2; shift 2; while true; do wait_gate; $R/with_lock.sh $label $cap "$@"; local rc=$?; (( rc == 8 || rc == 9 )) || return $rc; logline "$label refused (rc=$rc: gate/battery) — retrying in 60 s"; sleep 60; done; }
mkdir -p $R/logs $R/runs
logline "chain armed ($(state))"
# (1) demo-8 correctness (dropdown Hello, nothing typed)
if [[ ! -f $R/DONE-correctness ]]; then
  run correctness-demo-8 1500 $R/correctness_inner.sh demo-8 > $R/logs/chain-correctness.out 2>&1
  crc=$?; ids=$(grep -o '"tokens":\[[^]]*\]' $R/run-demo-8/harness.log | tail -1); vrc=$(grep -o 'verify rc=[0-9]*' $R/logs/chain-correctness.out | tail -1)
  logline "demo-8 correctness rc=$crc ids=$ids $vrc RSS peak MB $(awk '$2>m{m=$2} END{print m}' $R/run-demo-8/rss-renderer.log 2>/dev/null)"
  if [[ $ids == '"tokens":[11,314,1101,7926,11,475,314,1101]' && $vrc == "verify rc=0" ]]; then
    echo "demo-8 READY $(date '+%F %T'): dropdown Hello ids 8/8 [11,314,1101,7926,11,475,314,1101], $vrc, run R6X/run-demo-8 (harness.log, verify.log); = combined8 + R6P echo fix + typed prompt + R6V progress UI/early paint (all-new-flags-off twin byte-identical to combined8)" > $W/bundles/demo-8/READY; logline "bundles/demo-8/READY created"
  else logline "NO READY for demo-8"; fi
  touch $R/DONE-correctness
fi
# (2) demo-c32 load-paint probe (load only; the typed runs below take the mid-token screenshots)
if [[ ! -f $R/DONE-loadpaint ]]; then
  run loadpaint-demo-c32 900 $R/loadpaint_inner.sh demo-c32 0 > $R/logs/chain-loadpaint.out 2>&1
  logline "loadpaint rc=$? -> R6X/runs/loadpaint-demo-c32/: $(grep -h '"load-event"\|"fonts-loaded"' $R/runs/loadpaint-demo-c32/harness.log | grep -o '"sinceNavMs":[0-9]*' | tr '\n' ' ')"
  touch $R/DONE-loadpaint
fi
# (3) demo-c32 typed "I" == prompt-40 reference
if [[ ! -f $R/DONE-typed-I ]]; then
  B0_TYPED_PROMPT="I" B0_TYPED_IDS='[40]' B0_SHOTS="8,30,60" REF_JSON=$W/R4P/reference_ids_32_40.json run c32-typed-I 2760 $R/c32_inner.sh demo-c32 typed-I 2400000 32 > $R/logs/chain-c32-I.out 2>&1
  logline "demo-c32 typed I: $(grep -o '^ids [0-9]*/32' $R/run-demo-c32/typed-I.summary.md 2>/dev/null | head -1) (R6X/run-demo-c32/typed-I.summary.md)"; touch $R/DONE-typed-I
fi
# (4) demo-c32 typed "Once upon a time"
if [[ ! -f $R/DONE-typed-once ]]; then
  B0_TYPED_PROMPT="Once upon a time" B0_TYPED_IDS='[7454,2402,257,640]' B0_SHOTS="10,40,70" REF_JSON=$W/R6P/reference_ids_once_upon_a_time.json run c32-typed-once 2760 $R/c32_inner.sh demo-c32 typed-once 2400000 32 > $R/logs/chain-c32-once.out 2>&1
  logline "demo-c32 typed Once upon a time: $(grep -o '^ids [0-9]*/32' $R/run-demo-c32/typed-once.summary.md 2>/dev/null | head -1)"; touch $R/DONE-typed-once
fi
okI=$(grep -o '^ids [0-9]*/32' $R/run-demo-c32/typed-I.summary.md 2>/dev/null | head -1); okO=$(grep -o '^ids [0-9]*/32' $R/run-demo-c32/typed-once.summary.md 2>/dev/null | head -1)
if [[ $okI == "ids 32/32" && $okO == "ids 32/32" ]]; then
  echo "demo-c32 READY $(date '+%F %T'): typed 'I' 32/32 = R4P/reference_ids_32_40.json; typed 'Once upon a time' 32/32 = R6P/reference_ids_once_upon_a_time.json (4 prefilled + 29 generated); runs R6X/run-demo-c32/typed-{I,once}.{json,summary.md}; load-paint R6X/runs/loadpaint-demo-c32/" > $W/bundles/demo-c32/READY; logline "bundles/demo-c32/READY created"
else logline "NO READY for demo-c32 (I: $okI, Once: $okO)"; fi
# auto-append the Chrome results to R6X.md
{ echo; echo "## 6. Chrome results (auto-appended by R6X/run_chain.sh $(date '+%F %T'))"; echo
  echo "### 6.1 demo-8 correctness (R6X/run-demo-8/)"; echo '```'; grep -h '"loaded"\|"token-captured"\|"final"' $R/run-demo-8/harness.log 2>/dev/null | cut -c1-500; grep -o 'verify rc=[0-9]*.*' $R/logs/chain-correctness.out | tail -1 | cut -c1-500; echo "RSS renderer peak MB: $(awk '$2>m{m=$2} END{print m}' $R/run-demo-8/rss-renderer.log 2>/dev/null)"; echo "READY: $(cat $W/bundles/demo-8/READY 2>/dev/null || echo none)"; echo '```'
  echo "### 6.2 demo-c32 load-paint probe (R6X/runs/loadpaint-demo-c32/shot-*.png)"; echo '```'; grep -h '"state"\|"load-event"\|"fonts-loaded"\|"screenshot"' $R/runs/loadpaint-demo-c32/harness.log 2>/dev/null | cut -c1-600; echo '```'
  for l in typed-I typed-once; do echo "### 6.3 demo-c32 $l (R6X/run-demo-c32/$l.summary.md; screenshots $l-run-*s.png, $l-final.png)"; echo; cat $R/run-demo-c32/$l.summary.md 2>/dev/null; echo; grep -h '"prompt-typed"\|"screenshot"' $R/run-demo-c32/$l.stdout.log 2>/dev/null | cut -c1-700 | sed 's/^/    /'; echo; done
  echo "READY demo-c32: $(cat $W/bundles/demo-c32/READY 2>/dev/null || echo none)"; } >> $W/R6X.md
touch $R/CHAIN-DONE; logline "chain done"
