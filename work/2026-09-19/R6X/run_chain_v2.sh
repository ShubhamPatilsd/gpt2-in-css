#!/bin/zsh
# R6X v2 chain: (0) builds under the lock (R6X/build_v2.sh), (1) demo-c32 load-paint + typed "Once upon a time" + Run, screenshots at 10/70 s and at completion
# (900x600, then 900x300) — overlap check, (2) demo-8 Hello correctness 8/8 + verify → READY files updated, R6X.md §7 appended.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R6X; cd $W
logline() { echo "- $(date '+%F %T') [R6X chain v2] $*" >> $W/R6X.log.md; echo "$(date '+%T') $*"; }
swap_used_mb() { sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1; }
free_gb() { df -g $W | tail -1 | awk '{print $4}'; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
gate_ok() { on_ac && { { (( $(free_gb) >= 4 )) && (( $(swap_used_mb) < 4000 )); } || { (( $(free_gb) >= 3 )) && (( $(swap_used_mb) < 3000 )); }; }; }
state() { echo "AC=$(on_ac && echo 1 || echo 0) disk=$(free_gb)GB swap_used=$(swap_used_mb)MB lock=$(cat $W/CHROME.lock/owner 2>/dev/null || echo free)"; }
wait_gate() { local n=0; while ! gate_ok; do (( n % 30 == 0 )) && logline "gate closed, waiting ($(state)); poll 60 s"; n=$((n+1)); sleep 60; done; logline "gate open ($(state))"; }
run() { local label=$1 cap=$2; shift 2; while true; do wait_gate; $R/with_lock.sh $label $cap "$@"; local rc=$?; (( rc == 8 || rc == 9 )) || return $rc; logline "$label refused (rc=$rc: gate/battery) — retrying in 60 s"; sleep 60; done; }
logline "chain v2 armed ($(state))"
if [[ ! -f $R/BUILD-V2-DONE ]]; then
  run build-v2 900 $R/build_v2.sh > $R/logs/chain-v2-build.out 2>&1; brc=$?
  logline "build-v2 rc=$brc: $(grep -h 'only in NEW\|RESULT\|swapped\|FAILED' $R/logs/chain-v2-build.out | cut -c1-160 | tr '\n' ' ')"
  [[ -f $R/BUILD-V2-DONE ]] || { logline "ABORT: v2 builds not swapped in"; exit 2; }
fi
# (H) user report "Complete · 32 tokens but no text" (coordinator): HEADED runs (real window 1100x700, the user's launcher serving) with the
#     display dump at Complete. (H1-3) 2-layer smoke twin, typed "Once upon a time" / trailing space / newline (≈3 min each); (H4) demo-c32 full run.
REF2=$W/R6P/reference_ids_once_upon_a_time_2layers.json; ONCE='[7454,2402,257,640]'
if [[ ! -f $R/DONE-v3-headed-smoke ]]; then
  B0_HEADED=1 B0_VIEWPORT=1100x700 B0_READY_SHOT=1 B0_SHOTS=10 B0_TYPED_PROMPT="Once upon a time" B0_TYPED_IDS=$ONCE REF_JSON=$REF2 run headed-smoke-plain 900 $R/c32_inner.sh smoke-demo-2L headed-plain 600000 32 > $R/logs/chain-v3-headed-plain.out 2>&1
  logline "headed smoke plain: $(grep -o '^ids [0-9]*/32' $R/run-smoke-demo-2L/headed-plain.summary.md 2>/dev/null | head -1); dump: $(grep -h '"display-dump"' $R/run-smoke-demo-2L/headed-plain.stdout.log | grep -o '"before":"[^"]*"\|"status":"[^"]*"\|"promptCount":"[^"]*"' | tr '\n' ' ' | cut -c1-300)"
  B0_HEADED=1 B0_VIEWPORT=1100x700 B0_READY_SHOT=1 B0_SHOTS=10 B0_TYPED_PROMPT="Once upon a time " B0_TYPED_IDS=$ONCE REF_JSON=$REF2 run headed-smoke-space 900 $R/c32_inner.sh smoke-demo-2L headed-space 600000 32 > $R/logs/chain-v3-headed-space.out 2>&1
  logline "headed smoke trailing space: $(grep -o '^ids [0-9]*/32' $R/run-smoke-demo-2L/headed-space.summary.md 2>/dev/null | head -1); typed ids: $(grep -h '"prompt-typed"' $R/run-smoke-demo-2L/headed-space.stdout.log | grep -o '"ids":\[[^]]*\]\|"promptCount":[0-9]*' | tr '\n' ' ')"
  B0_HEADED=1 B0_VIEWPORT=1100x700 B0_READY_SHOT=1 B0_SHOTS=10 B0_TYPED_PROMPT=$'Once upon a time\n' REF_JSON=$REF2 run headed-smoke-newline 900 $R/c32_inner.sh smoke-demo-2L headed-newline 600000 32 > $R/logs/chain-v3-headed-newline.out 2>&1
  logline "headed smoke newline: $(grep -o '^ids [0-9]*/32' $R/run-smoke-demo-2L/headed-newline.summary.md 2>/dev/null | head -1) (expected: rule invalid -> dropdown fallback, ids != typed reference); typed state: $(grep -h '"prompt-typed"' $R/run-smoke-demo-2L/headed-newline.stdout.log | grep -o '"draftPrompt":"[^"]*"\|"ids":\[[^]]*\]\|"tokensReadout":"[^"]*"' | tr '\n' ' ' | cut -c1-300)"
  touch $R/DONE-v3-headed-smoke
fi
if [[ ! -f $R/DONE-v3-headed-c32 ]]; then
  B0_HEADED=1 B0_VIEWPORT=1100x700 B0_READY_SHOT=1 B0_SHOTS=10,60 B0_TYPED_PROMPT="Once upon a time" B0_TYPED_IDS=$ONCE REF_JSON=$W/R6P/reference_ids_once_upon_a_time.json run headed-c32-once 2760 $R/c32_inner.sh demo-c32 headed-once 2400000 32 > $R/logs/chain-v3-headed-c32.out 2>&1
  logline "headed demo-c32 typed Once upon a time: $(grep -o '^ids [0-9]*/32' $R/run-demo-c32/headed-once.summary.md 2>/dev/null | head -1); status/after at Complete: $(grep -h '"display-dump"' $R/run-demo-c32/headed-once.stdout.log | grep -o '"status":"[^"]*"\|"contentVisibility":"[^"]*"\|"display":"[^"]*"' | tr '\n' ' ' | cut -c1-300)"
  touch $R/DONE-v3-headed-c32
fi
if [[ ! -f $R/DONE-v2-loadpaint ]]; then
  [[ -d $R/runs/loadpaint-demo-c32 && ! -d $R/runs/loadpaint-demo-c32-v1 ]] && mv $R/runs/loadpaint-demo-c32 $R/runs/loadpaint-demo-c32-v1
  R6X_TYPED="Once upon a time" R6X_VIEWPORT=900x600 R6X_SHOTS=10,70 R6X_HEAD_SHOTS=3 R6X_WAIT_MS=1500000 R6X_CAPACITY=32 run loadpaint-v2 1900 $R/loadpaint_inner.sh demo-c32 1 > $R/logs/chain-v2-loadpaint.out 2>&1
  logline "loadpaint-v2 rc=$? -> R6X/runs/loadpaint-demo-c32/: $(grep -h '"load-event"\|"fonts-loaded"\|"run-complete"' $R/runs/loadpaint-demo-c32/harness.log | grep -o '"sinceNavMs":[0-9]*\|"doneWhy":"[a-z-]*"\|"sinceRunMs":[0-9]*' | tr '\n' ' '); overlap: $(grep -h '"tag":"complete' $R/runs/loadpaint-demo-c32/harness.log | grep -o '"overlap":[a-z]*' | tr '\n' ' ')"
  touch $R/DONE-v2-loadpaint
fi
if [[ ! -f $R/DONE-v2-correctness ]]; then
  [[ -d $R/run-demo-8 && ! -d $R/run-demo-8-v1 ]] && mv $R/run-demo-8 $R/run-demo-8-v1
  run correctness-demo-8-v2 1500 $R/correctness_inner.sh demo-8 > $R/logs/chain-v2-correctness.out 2>&1
  crc=$?; ids=$(grep -o '"tokens":\[[^]]*\]' $R/run-demo-8/harness.log | tail -1); vrc=$(grep -o 'verify rc=[0-9]*' $R/logs/chain-v2-correctness.out | tail -1)
  logline "demo-8 v2 correctness rc=$crc ids=$ids $vrc"
  if [[ $ids == '"tokens":[11,314,1101,7926,11,475,314,1101]' && $vrc == "verify rc=0" ]]; then
    echo "demo-8 v2 READY $(date '+%F %T'): display-only rebuild v3 (layout rule html .visible-output{bottom:96px;overflow:auto} + head-phase 13th segment .pg::before/::after; rules otherwise identical to v1, R6X/logs/compare_rules-demo-8-v2.log); dropdown Hello ids 8/8 [11,314,1101,7926,11,475,314,1101], $vrc, run R6X/run-demo-8 (v1 run: R6X/run-demo-8-v1)" >> $W/bundles/demo-8/READY; logline "bundles/demo-8/READY updated (v2)"
  else logline "demo-8 v2: ids/verify NOT ok — READY left at v1 (rebuild differs by one display rule only)"; fi
  touch $R/DONE-v2-correctness
fi
ov=$(grep -h '"tag":"complete"' $R/runs/loadpaint-demo-c32/harness.log | grep -o '"overlap":[a-z]*' | head -1)
echo "demo-c32 v2 $(date '+%F %T'): display-only rebuild v3 (layout rule html .visible-output{bottom:96px;overflow:auto} + head-phase 13th segment .pg::before/::after with estimated 2.8 s fill; index.html byte-identical and all other rules identical to the v1 build whose typed runs gave 32/32 + 32/32, R6X/logs/compare_rules-demo-c32-v2.log); v2 probe R6X/runs/loadpaint-demo-c32 (typed 'Once upon a time', shots run-10s / run-70s / head-1..3 (vocabulary-head phase) / complete / complete-900x300; geometry at completion: $ov); demo-8 v2 Hello 8/8 guard: see bundles/demo-8/READY" >> $W/bundles/demo-c32/READY
{ echo; echo "## 7. v3 display fixes (footer overlap + head-phase segment) — re-verification (auto-appended by R6X/run_chain_v2.sh $(date '+%F %T'))"; echo
  echo "### 7.1 builds under the lock (R6X/build_v2.sh; R6X/logs/compare_rules-*-v2.log)"; echo '```'; grep -h 'index.html\|^rules\|only in\|order of\|RESULT\|swapped\|staticFiles\|runtimeJavaScript\|^total' $R/logs/chain-v2-build.out | cut -c1-300; echo '```'
  echo "### 7.2 demo-c32 load-paint + typed 'Once upon a time' + Run (R6X/runs/loadpaint-demo-c32/: shot-load-*.png, shot-ready.png, shot-typed.png, shot-run-10s.png, shot-run-70s.png, shot-head-{1,1b,2,3}.png, shot-complete.png, shot-complete-900x300.png; v1 probe in loadpaint-demo-c32-v1/)"; echo '```'; grep -h '"state"\|"load-event"\|"fonts-loaded"\|"prompt-typed"\|"run-keyed"\|"run-complete"\|"screenshot"' $R/runs/loadpaint-demo-c32/harness.log | cut -c1-700; echo '```'
  echo "### 7.H headed runs (user report: Complete but no text) — R6X/run-smoke-demo-2L/headed-{plain,space,newline}.*, R6X/run-demo-c32/headed-once.* (screenshots *-ready.png, *-run-10s.png, *-run-60s.png, *-final.png)"; echo '```'
  for f in $R/run-smoke-demo-2L/headed-plain $R/run-smoke-demo-2L/headed-space $R/run-smoke-demo-2L/headed-newline $R/run-demo-c32/headed-once; do echo "== $f"; grep -o '^ids [0-9]*/32.*' $f.summary.md 2>/dev/null | cut -c1-200; grep -h '"prompt-typed"' $f.stdout.log 2>/dev/null | cut -c1-900; grep -h '"display-dump"' $f.stdout.log 2>/dev/null | cut -c1-2500; done; echo '```'
  echo "### 7.3 demo-8 Hello correctness guard (R6X/run-demo-8/; v1 run in run-demo-8-v1/)"; echo '```'; grep -h '"loaded"\|"token-captured"\|"final"' $R/run-demo-8/harness.log 2>/dev/null | cut -c1-500; grep -o 'verify rc=[0-9]*.*' $R/logs/chain-v2-correctness.out | tail -1 | cut -c1-400; echo "RSS renderer peak MB: $(awk '$2>m{m=$2} END{print m}' $R/run-demo-8/rss-renderer.log 2>/dev/null)"; echo '```'
  echo "READY demo-8: $(tail -1 $W/bundles/demo-8/READY)"; echo; echo "READY demo-c32: $(tail -1 $W/bundles/demo-c32/READY)"; } >> $W/R6X.md
touch $R/CHAIN-V2-DONE; logline "chain v2 done"
