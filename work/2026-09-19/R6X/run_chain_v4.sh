#!/bin/zsh
# R6X v4 chain: build under the lock (R6X/build_v2.sh, identity check vs the shipped v3), typed "Once upon a time" load-paint probes at 900x300 and
# 1100x700 (screenshots at Complete, overlap geometry), demo-8 Hello guard → READY/BUILD.md appended, R6X.md §8 appended.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R6X; cd $W
logline() { echo "- $(date '+%F %T') [R6X chain v4] $*" >> $W/R6X.log.md; echo "$(date '+%T') $*"; }
swap_used_mb() { sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1; }
free_gb() { df -g $W | tail -1 | awk '{print $4}'; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
gate_ok() { on_ac && { { (( $(free_gb) >= 4 )) && (( $(swap_used_mb) < 4000 )); } || { (( $(free_gb) >= 3 )) && (( $(swap_used_mb) < 3000 )); }; }; }
state() { echo "AC=$(on_ac && echo 1 || echo 0) disk=$(free_gb)GB swap_used=$(swap_used_mb)MB lock=$(cat $W/CHROME.lock/owner 2>/dev/null || echo free)"; }
wait_gate() { local n=0; while ! gate_ok; do (( n % 30 == 0 )) && logline "gate closed, waiting ($(state)); poll 60 s"; n=$((n+1)); sleep 60; done; logline "gate open ($(state))"; }
run() { local label=$1 cap=$2; shift 2; while true; do wait_gate; $R/with_lock.sh $label $cap "$@"; local rc=$?; (( rc == 8 || rc == 9 )) || return $rc; logline "$label refused (rc=$rc: gate/battery) — retrying in 60 s"; sleep 60; done; }
logline "chain v4 armed ($(state))"
if [[ ! -f $R/BUILD-V2-DONE ]]; then
  run build-v4 900 $R/build_v2.sh > $R/logs/chain-v4-build.out 2>&1; brc=$?
  logline "build-v4 rc=$brc: $(grep -h 'only in\|RESULT\|swapped\|FAILED' $R/logs/chain-v4-build.out | cut -c1-140 | tr '\n' ' ')"
  [[ -f $R/BUILD-V2-DONE ]] || { logline "ABORT: v4 builds not swapped in"; exit 2; }
fi
for vp in 900x300 1100x700; do
  [[ -f $R/DONE-v4-probe-$vp ]] && continue
  R6X_TYPED="Once upon a time" R6X_VIEWPORT=$vp R6X_SHOTS=10 R6X_HEAD_SHOTS=0 R6X_WAIT_MS=1500000 R6X_CAPACITY=32 run probe-v4-$vp 1900 $R/loadpaint_inner.sh demo-c32 1 v4-$vp > $R/logs/chain-v4-probe-$vp.out 2>&1
  logline "probe v4 $vp rc=$? -> R6X/runs/loadpaint-demo-c32-v4-$vp/: $(grep -h '"fonts-loaded"\|"run-complete"' $R/runs/loadpaint-demo-c32-v4-$vp/harness.log | grep -o '"sinceNavMs":[0-9]*\|"doneWhy":"[a-z-]*"\|"sinceRunMs":[0-9]*' | tr '\n' ' '); geometry at complete: $(grep -h '"tag":"complete' $R/runs/loadpaint-demo-c32-v4-$vp/harness.log | grep -o '"geometry":{.*}' | cut -c1-260 | tr '\n' ' ')"
  touch $R/DONE-v4-probe-$vp
done
if [[ ! -f $R/DONE-v4-correctness ]]; then
  run correctness-demo-8-v4 1500 $R/correctness_inner.sh demo-8 > $R/logs/chain-v4-correctness.out 2>&1
  crc=$?; ids=$(grep -o '"tokens":\[[^]]*\]' $R/run-demo-8/harness.log | tail -1); vrc=$(grep -o 'verify rc=[0-9]*' $R/logs/chain-v4-correctness.out | tail -1)
  logline "demo-8 v4 correctness rc=$crc ids=$ids $vrc"
  if [[ $ids == '"tokens":[11,314,1101,7926,11,475,314,1101]' && $vrc == "verify rc=0" ]]; then
    echo "demo-8 v4 READY $(date '+%F %T'): display-only rebuild v4 (html .visible-output{max-height:calc(100vh - 280px);min-height:4lh;overflow:auto} + html .tk-aside{top:calc(192px + max(128px,100vh - 280px))!important;bottom:auto} replace v2's bottom:96px; rules otherwise identical to v3, R6X/logs/compare_rules-demo-8-v2.log); dropdown Hello ids 8/8 [11,314,1101,7926,11,475,314,1101], $vrc, run R6X/run-demo-8 (v3 run: run-demo-8-v3, v1: run-demo-8-v1)" >> $W/bundles/demo-8/READY; logline "bundles/demo-8/READY updated (v4)"
  else logline "demo-8 v4: ids/verify NOT ok — READY left at v3"; fi
  touch $R/DONE-v4-correctness
fi
g1=$(grep -h '"tag":"complete"' $R/runs/loadpaint-demo-c32-v4-900x300/harness.log | grep -o '"overlap":[a-z]*' | head -1); g2=$(grep -h '"tag":"complete"' $R/runs/loadpaint-demo-c32-v4-1100x700/harness.log | grep -o '"overlap":[a-z]*' | head -1)
echo "demo-c32 v4 $(date '+%F %T'): display-only rebuild v4 (output box max-height:calc(100vh - 280px)/min-height:4lh/overflow:auto, footer placed below the output's maximum extent; replaces v2's bottom:96px which clipped the box in short windows; index.html byte-identical and all other rules identical to v3 — R6X/logs/compare_rules-demo-c32-v2.log); probes R6X/runs/loadpaint-demo-c32-v4-{900x300,1100x700} typed 'Once upon a time' to Complete: 900x300 $g1, 1100x700 $g2; demo-8 v4 Hello 8/8 guard: see bundles/demo-8/READY" >> $W/bundles/demo-c32/READY
{ echo; echo "## 8. v4 robust output sizing — re-verification (auto-appended by R6X/run_chain_v4.sh $(date '+%F %T'))"; echo
  echo "### 8.1 builds under the lock (R6X/logs/compare_rules-*-v2.log = v4 vs shipped v3)"; echo '```'; grep -h 'index.html\|^rules\|only in\|order of\|RESULT\|swapped\|staticFiles\|runtimeJavaScript\|^total' $R/logs/chain-v4-build.out | cut -c1-300; echo '```'
  for vp in 900x300 1100x700; do echo "### 8.2 probe $vp (R6X/runs/loadpaint-demo-c32-v4-$vp/: shot-ready.png, shot-typed.png, shot-run-10s.png, shot-complete.png, shot-complete-900x300.png)"; echo '```'; grep -h '"load-event"\|"fonts-loaded"\|"run-complete"\|"tag":"run-10s"\|"tag":"complete' $R/runs/loadpaint-demo-c32-v4-$vp/harness.log | cut -c1-700; echo '```'; done
  echo "### 8.3 demo-8 Hello guard (R6X/run-demo-8/)"; echo '```'; grep -h '"final"' $R/run-demo-8/harness.log 2>/dev/null | cut -c1-300; grep -o 'verify rc=[0-9]*.*' $R/logs/chain-v4-correctness.out | tail -1 | cut -c1-300; echo "RSS renderer peak MB: $(awk '$2>m{m=$2} END{print m}' $R/run-demo-8/rss-renderer.log 2>/dev/null)"; echo '```'
  echo "READY demo-8: $(tail -1 $W/bundles/demo-8/READY)"; echo; echo "READY demo-c32: $(tail -1 $W/bundles/demo-c32/READY)"; } >> $W/R6X.md
touch $R/CHAIN-V4-DONE; logline "chain v4 done"
