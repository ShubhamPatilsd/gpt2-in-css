#!/bin/zsh
# R6X v6 guards (quiet machine: gate AND load1 < 6; all typed runs HEADED 1100x700, SCROLLBARS SHOWN (B0_SHOW_SCROLLBARS=1 omits --hide-scrollbars), standard harness fill + keyboard Run): (0) positive control — the OLD build
# bundles/demo-c32.prev (v5, scrollbar bug) typed "I": R7H predicts a flip at position 15 (ref 16918); (1) v6 typed "I" 32/32; (2) v6 typed "Shubham was" 32/32; (3) demo-8 Hello 8/8.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R6X; cd $W
logline() { echo "- $(date '+%F %T') [R6X chain v6] $*" >> $W/R6X.log.md; echo "$(date '+%T') $*"; }
swap_used_mb() { sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1; }
free_gb() { df -g $W | tail -1 | awk '{print $4}'; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
load1() { sysctl -n vm.loadavg | awk '{print int($2)}'; }
gate_ok() { on_ac && { { (( $(free_gb) >= 4 )) && (( $(swap_used_mb) < 4000 )); } || { (( $(free_gb) >= 3 )) && (( $(swap_used_mb) < 3000 )); }; }; }
state() { echo "AC=$(on_ac && echo 1 || echo 0) disk=$(free_gb)GB swap_used=$(swap_used_mb)MB load1=$(load1) lock=$(cat $W/CHROME.lock/owner 2>/dev/null || echo free)"; }
wait_quiet() { local n=0; while ! gate_ok || (( $(load1) >= 6 )); do (( n % 15 == 0 )) && logline "waiting for gate open AND load1 < 6 ($(state)); poll 60 s"; n=$((n+1)); sleep 60; done; logline "quiet ($(state))"; }
run() { local label=$1 cap=$2; shift 2; while true; do wait_quiet; $R/with_lock.sh $label $cap "$@"; local rc=$?; (( rc == 8 || rc == 9 )) || return $rc; logline "$label refused (rc=$rc) — retrying in 60 s"; sleep 60; done; }
summ() { python3 - "$@" <<'PY'
import json, sys
log, ref = sys.argv[1], sys.argv[2]; want = json.load(open(ref))["freeRunningReference"]; w = None; caps = 0
for l in open(log):
    try: j = json.loads(l)
    except Exception: continue
    if j.get("event") == "winners": w = j
    if j.get("event") == "token-captured": caps = j["k"]; last = j["sinceRun"]
fb = [int(float(x)) for x in (w or {}).get("feedback", []) if x not in ("", None)]
ok = sum(1 for a, b in zip(fb, want) if a == b); mm = next((i+1 for i,(a,b) in enumerate(zip(fb,want)) if a!=b), None)
print(f"ids {ok}/{len(fb)} (captured {caps} in {round(last/1000) if caps else 0} s) vs {ref.split('/')[-1]}; first mismatch {mm}")
PY
}
logline "chain v6 armed ($(state)); waiting for BUILD-V2-DONE (v6 swap)"
until [[ -f $R/BUILD-V2-DONE ]]; do sleep 20; done
if [[ ! -f $R/DONE-v6-control ]]; then
  B0_HEADED=1 B0_SHOW_SCROLLBARS=1 B0_VIEWPORT=1100x700 B0_READY_SHOT=1 B0_TYPED_PROMPT="I" B0_TYPED_IDS='[40]' REF_JSON=$W/R4P/reference_ids_32_40.json run control-prev-headed-I 2760 $R/c32_inner.sh demo-c32.prev headed-I-prev 2400000 32 > $R/logs/chain-v6-control.out 2>&1
  logline "(0) positive control, OLD build (demo-c32.prev) HEADED typed I: $(grep -o '^ids [0-9]*/32.*first\|^ids [0-9]*/32' $R/run-demo-c32.prev/headed-I-prev.summary.md 2>/dev/null | head -1 | cut -c1-120); $(grep -o '^first mismatching position: [0-9None]*' $R/run-demo-c32.prev/headed-I-prev.summary.md 2>/dev/null)"; touch $R/DONE-v6-control
fi
if [[ ! -f $R/DONE-v6-I ]]; then
  B0_HEADED=1 B0_SHOW_SCROLLBARS=1 B0_VIEWPORT=1100x700 B0_READY_SHOT=1 B0_TYPED_PROMPT="I" B0_TYPED_IDS='[40]' REF_JSON=$W/R4P/reference_ids_32_40.json run v6-headed-I 2760 $R/c32_inner.sh demo-c32 headed-I-v6 2400000 32 > $R/logs/chain-v6-I.out 2>&1
  logline "(1) v6 HEADED typed I: $(grep -o '^ids [0-9]*/32' $R/run-demo-c32/headed-I-v6.summary.md 2>/dev/null | head -1); $(grep -o '^first mismatching position: [0-9None]*' $R/run-demo-c32/headed-I-v6.summary.md 2>/dev/null)"; touch $R/DONE-v6-I
fi
if [[ ! -f $R/DONE-v6-shubham ]]; then
  B0_HEADED=1 B0_SHOW_SCROLLBARS=1 B0_VIEWPORT=1100x700 B0_READY_SHOT=1 B0_TYPED_PROMPT="Shubham was" B0_TYPED_IDS='[2484,549,2763,373]' REF_JSON=$R/reference_ids_shubham_was.json run v6-headed-shubham 2760 $R/c32_inner.sh demo-c32 headed-shubham-v6 2400000 32 > $R/logs/chain-v6-shubham.out 2>&1
  logline "(2) v6 HEADED typed Shubham was: $(grep -o '^ids [0-9]*/32' $R/run-demo-c32/headed-shubham-v6.summary.md 2>/dev/null | head -1); $(grep -o '^first mismatching position: [0-9None]*' $R/run-demo-c32/headed-shubham-v6.summary.md 2>/dev/null)"; touch $R/DONE-v6-shubham
fi
if [[ ! -f $R/DONE-v6-8 ]]; then
  [[ -d $R/run-demo-8 && ! -d $R/run-demo-8-v5 ]] && mv $R/run-demo-8 $R/run-demo-8-v5
  run correctness-demo-8-v6 1500 $R/correctness_inner.sh demo-8 > $R/logs/chain-v6-correctness.out 2>&1
  crc=$?; ids=$(grep -o '"tokens":\[[^]]*\]' $R/run-demo-8/harness.log | tail -1); vrc=$(grep -o 'verify rc=[0-9]*' $R/logs/chain-v6-correctness.out | tail -1)
  logline "(3) demo-8 v6 Hello rc=$crc ids=$ids $vrc"
  [[ $ids == '"tokens":[11,314,1101,7926,11,475,314,1101]' && $vrc == "verify rc=0" ]] && { echo "demo-8 v6 READY $(date '+%F %T'): + .feedback-scroller{scrollbar-width:none} (R7H's headed-Chrome id-readback fix, R6X.md §11); dropdown Hello ids 8/8, $vrc, run R6X/run-demo-8" >> $W/bundles/demo-8/READY; logline "demo-8 READY v6"; }
  touch $R/DONE-v6-8
fi
c=$(grep -o '^ids [0-9]*/32' $R/run-demo-c32.prev/headed-I-prev.summary.md 2>/dev/null | head -1); i6=$(grep -o '^ids [0-9]*/32' $R/run-demo-c32/headed-I-v6.summary.md 2>/dev/null | head -1); s6=$(grep -o '^ids [0-9]*/32' $R/run-demo-c32/headed-shubham-v6.summary.md 2>/dev/null | head -1)
echo "demo-c32 v6 $(date '+%F %T'): + .feedback-scroller{scrollbar-width:none} (R7H: headed Chrome's classic scrollbar biased read-back ids >= 9283 by +1; R6X.md §11); HEADED scrollbars-shown guards: typed 'I' $i6, typed 'Shubham was' $s6 (positive control on the old build headed typed 'I': $c); demo-8 Hello: see bundles/demo-8/READY" >> $W/bundles/demo-c32/READY
{ echo; echo "### 11.G guards (auto-appended by R6X/run_chain_v6.sh $(date '+%F %T'); all typed runs HEADED 1100x700, scrollbars shown, standard harness)"; echo '```'
  for f in run-demo-c32.prev/headed-I-prev run-demo-c32/headed-I-v6 run-demo-c32/headed-shubham-v6; do echo "== $f"; grep -h '^# \|^ids \|^first mismatching' $R/$f.summary.md 2>/dev/null | cut -c1-400; done
  echo "== demo-8 v6: $(tail -1 $W/bundles/demo-8/READY | cut -c1-200)"; echo '```'; echo; echo "READY demo-c32: $(tail -1 $W/bundles/demo-c32/READY)"; } >> $W/R6X.md
touch $R/CHAIN-V6-DONE; logline "chain v6 done"
