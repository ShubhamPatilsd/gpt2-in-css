#!/bin/zsh
# R6X v5 chain: gate → (O) ordering probes HEADED 1100x700, keystrokes + MOUSE click, browser zoom 150 % (3 × Meta+=): old smoke (v3 wiring) and fixed
# smoke (v5), 5 tokens each → (B) build+swap demo-c32/demo-8 (v5, .next/.prev, check_v5_identity) → (G) guards: demo-8 Hello 8/8; HEADED demo-c32
# "Shubham was" typed by keystrokes + mouse click, 32 tokens vs reference (ordering.mjs); "Once upon a time" 32/32 (standard harness) → READY/§10.
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
summ() { python3 - "$@" <<'PY'
import json, sys
log, ref = sys.argv[1], sys.argv[2]; d = json.load(open(ref)); want = d["freeRunningReference"]
w = None
for l in open(log):
    try: j = json.loads(l)
    except Exception: continue
    if j.get("event") == "winners": w = j
fb = [int(float(x)) if x not in ("", None) else None for x in (w or {}).get("feedback", [])]
ok = sum(1 for a, b in zip(fb, want) if a == b); print(f"ids {ok}/{len(fb)} vs {ref.split('/')[-1]}; first mismatch {next((i+1 for i,(a,b) in enumerate(zip(fb,want)) if a!=b), None)}; model count {(w or {}).get('select',{}).get('--prompt-count')} armed {(w or {}).get('armedRoot')}")
PY
}
logline "chain v5 armed ($(state))"
if [[ ! -f $R/DONE-v5-ordering ]]; then
  for b in smoke-demo-2L smoke-demo-2L-v5; do
    R6X_TYPED="Shubham was" run ordering-$b 900 $R/ordering_inner.sh $b zoom150 3 5 > $R/logs/chain-v5-ordering-$b.out 2>&1
    logline "ordering $b (zoom 150 %, keystrokes, mouse): $(summ $R/runs/ordering-$b-zoom150/harness.log $R/reference_ids_shubham_was_2layers.json); frames with armed=1: $(grep -c '"armed":"1"' $R/runs/ordering-$b-zoom150/harness.log) / latched: $(grep -c '"latched":true' $R/runs/ordering-$b-zoom150/harness.log); first frame armed: $(grep -h '"frame"' $R/runs/ordering-$b-zoom150/harness.log | grep '"armed":"1"' | head -1 | cut -c1-300); first frame latched: $(grep -h '"frame"' $R/runs/ordering-$b-zoom150/harness.log | grep '"latched":true' | head -1 | cut -c1-300)"
  done
  touch $R/DONE-v5-ordering
fi
if [[ ! -f $R/BUILD-V2-DONE ]]; then
  run build-v5 900 $R/build_v2.sh > $R/logs/chain-v5-build.out 2>&1; brc=$?
  logline "build-v5 rc=$brc: $(grep -h 'RESULT\|swapped\|FAILED\|model core' $R/logs/chain-v5-build.out | cut -c1-160 | tr '\n' ' ')"
  [[ -f $R/BUILD-V2-DONE ]] || { logline "ABORT: v5 builds not swapped in"; exit 2; }
fi
if [[ ! -f $R/DONE-v5-guard-8 ]]; then
  [[ -d $R/run-demo-8 && ! -d $R/run-demo-8-v4 ]] && mv $R/run-demo-8 $R/run-demo-8-v4
  run correctness-demo-8-v5 1500 $R/correctness_inner.sh demo-8 > $R/logs/chain-v5-correctness.out 2>&1
  crc=$?; ids=$(grep -o '"tokens":\[[^]]*\]' $R/run-demo-8/harness.log | tail -1); vrc=$(grep -o 'verify rc=[0-9]*' $R/logs/chain-v5-correctness.out | tail -1)
  logline "demo-8 v5 correctness rc=$crc ids=$ids $vrc"
  if [[ $ids == '"tokens":[11,314,1101,7926,11,475,314,1101]' && $vrc == "verify rc=0" ]]; then echo "demo-8 v5 READY $(date '+%F %T'): typed-prompt arming fix (token-fresh embedding receipt, sticky arming, no latch, editor locked from the click, Run after Ready, echo from model-facing values; model core rules identical — R6X/logs/identity-demo-8-v5.log); dropdown Hello ids 8/8, $vrc, run R6X/run-demo-8" >> $W/bundles/demo-8/READY; logline "demo-8 READY v5"; else logline "demo-8 v5 NOT ok"; fi
  touch $R/DONE-v5-guard-8
fi
if [[ ! -f $R/DONE-v5-guard-shubham ]]; then
  R6X_TYPED="Shubham was" run headed-shubham-v5 2760 $R/ordering_inner.sh demo-c32 keys-mouse 0 32 > $R/logs/chain-v5-shubham.out 2>&1
  logline "headed demo-c32 'Shubham was' keystrokes+mouse: $(summ $R/runs/ordering-demo-c32-keys-mouse/harness.log $R/reference_ids_shubham_was.json)"
  touch $R/DONE-v5-guard-shubham
fi
if [[ ! -f $R/DONE-v5-guard-once ]]; then
  B0_TYPED_PROMPT="Once upon a time" B0_TYPED_IDS='[7454,2402,257,640]' REF_JSON=$W/R6P/reference_ids_once_upon_a_time.json run c32-typed-once-v5 2760 $R/c32_inner.sh demo-c32 typed-once-v5 2400000 32 > $R/logs/chain-v5-once.out 2>&1
  logline "demo-c32 typed Once upon a time (v5): $(grep -o '^ids [0-9]*/32' $R/run-demo-c32/typed-once-v5.summary.md 2>/dev/null | head -1)"
  touch $R/DONE-v5-guard-once
fi
sh=$(summ $R/runs/ordering-demo-c32-keys-mouse/harness.log $R/reference_ids_shubham_was.json | cut -d';' -f1); on=$(grep -o '^ids [0-9]*/32' $R/run-demo-c32/typed-once-v5.summary.md 2>/dev/null | head -1)
echo "demo-c32 v5 $(date '+%F %T'): typed-prompt arming fix (R6X.md §10; model core rules identical, R6X/logs/identity-demo-c32-v5.log); guards: headed keystrokes+mouse 'Shubham was' $sh (R6X/runs/ordering-demo-c32-keys-mouse), typed 'Once upon a time' $on (R6X/run-demo-c32/typed-once-v5.summary.md), demo-8 Hello: see bundles/demo-8/READY" >> $W/bundles/demo-c32/READY
{ echo; echo "## 10. v5 — typed prompt shown but dropdown prompt run (user reports #2/#3): ordering probe, fix, guards (auto-appended by R6X/run_chain_v5b.sh $(date '+%F %T'))"; echo
  for b in smoke-demo-2L smoke-demo-2L-v5; do echo "### 10.O ordering probe $b (R6X/runs/ordering-$b-zoom150/: frames.json, shot-*.png)"; echo '```'; grep -h '"typed"\|"run-clicked"\|"after-click"\|"token-captured"\|"winners"' $R/runs/ordering-$b-zoom150/harness.log | cut -c1-900; echo "-- frames (f, ms, armed, live, count, id0, latched, ready, stamp, token, epoch)"; grep -h '"frame"' $R/runs/ordering-$b-zoom150/harness.log | head -45 | cut -c1-260; echo '```'; done
  echo "### 10.B builds (R6X/logs/identity-*-v5.log)"; echo '```'; grep -h 'index.html\|^rules\|only in\|order\|model core\|RESULT\|swapped' $R/logs/chain-v5-build.out | cut -c1-300; echo '```'
  echo "### 10.G guards"; echo '```'; echo "demo-8: $(tail -1 $W/bundles/demo-8/READY)"; echo "headed Shubham was: $(summ $R/runs/ordering-demo-c32-keys-mouse/harness.log $R/reference_ids_shubham_was.json)"; grep -h '"winners"' $R/runs/ordering-demo-c32-keys-mouse/harness.log | cut -c1-1200; echo "Once upon a time: $on"; echo '```'; } >> $W/R6X.md
touch $R/CHAIN-V5B-DONE; logline "chain v5 done"
