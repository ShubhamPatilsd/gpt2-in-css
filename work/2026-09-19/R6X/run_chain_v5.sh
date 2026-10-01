#!/bin/zsh
# R6X v5 chain (user report #2, typed "Shubham was"): waits for CHAIN-V4-DONE (no concurrent R6X Chrome) and the NumPy references, then under the lock:
# (1) HEADED 2-layer smoke typed "Shubham was" vs reference_ids_shubham_was_2layers.json (≈3 min; shots ready/5/30/90 s/final + per-shot display dumps);
# (2) HEADED demo-c32 typed "Shubham was" vs reference_ids_shubham_was.json (same shots/dumps). Appends §9 to R6X.md.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R6X; cd $W
logline() { echo "- $(date '+%F %T') [R6X chain v5] $*" >> $W/R6X.log.md; echo "$(date '+%T') $*"; }
swap_used_mb() { sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1; }
free_gb() { df -g $W | tail -1 | awk '{print $4}'; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
gate_ok() { on_ac && { { (( $(free_gb) >= 4 )) && (( $(swap_used_mb) < 4000 )); } || { (( $(free_gb) >= 3 )) && (( $(swap_used_mb) < 3000 )); }; }; }
state() { echo "AC=$(on_ac && echo 1 || echo 0) disk=$(free_gb)GB swap_used=$(swap_used_mb)MB lock=$(cat $W/CHROME.lock/owner 2>/dev/null || echo free)"; }
wait_gate() { local n=0; while ! gate_ok; do (( n % 30 == 0 )) && logline "gate closed, waiting ($(state)); poll 60 s"; n=$((n+1)); sleep 60; done; logline "gate open ($(state))"; }
run() { local label=$1 cap=$2; shift 2; while true; do wait_gate; $R/with_lock.sh $label $cap "$@"; local rc=$?; (( rc == 8 || rc == 9 )) || return $rc; logline "$label refused (rc=$rc: gate/battery) — retrying in 60 s"; sleep 60; done; }
logline "chain v5 armed ($(state)); waiting for CHAIN-V4-DONE + DONE-numpy-shubham"
until [[ -f $R/CHAIN-V4-DONE && -f $R/DONE-numpy-shubham ]]; do sleep 20; done
IDS='[2484,549,2763,373]'
if [[ ! -f $R/DONE-v5-smoke ]]; then
  B0_HEADED=1 B0_VIEWPORT=1100x700 B0_READY_SHOT=1 B0_SHOTS=5,30,90 B0_SHOT_DUMP=1 B0_TYPED_PROMPT="Shubham was" B0_TYPED_IDS=$IDS REF_JSON=$R/reference_ids_shubham_was_2layers.json run headed-smoke-shubham 900 $R/c32_inner.sh smoke-demo-2L headed-shubham 600000 32 > $R/logs/chain-v5-smoke.out 2>&1
  logline "headed smoke 'Shubham was': $(grep -o '^ids [0-9]*/32' $R/run-smoke-demo-2L/headed-shubham.summary.md 2>/dev/null | head -1); typed: $(grep -h '"prompt-typed"' $R/run-smoke-demo-2L/headed-shubham.stdout.log | grep -o '"ids":\[[^]]*\]\|"promptCount":[0-9]*' | tr '\n' ' '); dumps: $(grep -h '"shot-dump"' $R/run-smoke-demo-2L/headed-shubham.stdout.log | grep -o '"s":[0-9]*\|"promptCount":"[^"]*"\|"promptTokenIds":\[[^]]*\]\|"displayTokens":\[[^]]*\]\|"innerText":"[^"]*"' | tr '\n' ' ' | cut -c1-600)"
  touch $R/DONE-v5-smoke
fi
if [[ ! -f $R/DONE-v5-c32 ]]; then
  B0_HEADED=1 B0_VIEWPORT=1100x700 B0_READY_SHOT=1 B0_SHOTS=5,30,90 B0_SHOT_DUMP=1 B0_TYPED_PROMPT="Shubham was" B0_TYPED_IDS=$IDS REF_JSON=$R/reference_ids_shubham_was.json run headed-c32-shubham 2760 $R/c32_inner.sh demo-c32 headed-shubham 2400000 32 > $R/logs/chain-v5-c32.out 2>&1
  logline "headed demo-c32 'Shubham was': $(grep -o '^ids [0-9]*/32' $R/run-demo-c32/headed-shubham.summary.md 2>/dev/null | head -1); dumps: $(grep -h '"shot-dump"' $R/run-demo-c32/headed-shubham.stdout.log | grep -o '"s":[0-9]*\|"promptCount":"[^"]*"\|"promptTokenIds":\[[^]]*\]\|"displayTokens":\[[^]]*\]' | tr '\n' ' ' | cut -c1-600)"
  touch $R/DONE-v5-c32
fi
{ echo; echo "## 9. User report #2 — typed \"Shubham was\" (auto-appended by R6X/run_chain_v5.sh $(date '+%F %T'))"; echo
  echo "Reference: R6X/reference_ids_shubham_was.json (R6P/reference_prompt.py on R6X/tools): $(python3 -c "import json;d=json.load(open('$R/reference_ids_shubham_was.json'));print(d['promptTokens'], d['winners'], repr(d['fullText']))" 2>/dev/null | cut -c1-600)"; echo
  for f in $R/run-smoke-demo-2L/headed-shubham $R/run-demo-c32/headed-shubham; do echo "### $f (screenshots *-ready.png, *-run-{5,30,90}s.png, *-final.png)"; echo '```'; grep -o '^ids [0-9]*/32.*' $f.summary.md 2>/dev/null | cut -c1-400; grep -h '"prompt-typed"' $f.stdout.log 2>/dev/null | cut -c1-900; grep -h '"shot-dump"' $f.stdout.log 2>/dev/null | cut -c1-1500; grep -h '"display-dump"' $f.stdout.log 2>/dev/null | cut -c1-2500; echo '```'; done; } >> $W/R6X.md
touch $R/CHAIN-V5-DONE; logline "chain v5 done"
