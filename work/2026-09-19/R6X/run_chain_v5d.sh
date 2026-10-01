#!/bin/zsh
# R6X v5d: 2x2 on a quiet machine (gate AND load1 < 6): (a) PASSIVE harness (bench_native: fill + keyboard Run, DOM.querySelector polling only) typed "Shubham was"
# on the live v5 demo-c32; (b) the ordering harness (keystrokes + mouse + per-capture getComputedStyle reads) on the kept v4 build bundles/demo-c32.prev.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R6X; cd $W
logline() { echo "- $(date '+%F %T') [R6X chain v5d] $*" >> $W/R6X.log.md; echo "$(date '+%T') $*"; }
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
logline "chain v5d armed ($(state))"
if [[ ! -f $R/DONE-v5d-passive ]]; then
  B0_TYPED_PROMPT="Shubham was" B0_TYPED_IDS='[2484,549,2763,373]' REF_JSON=$R/reference_ids_shubham_was.json run c32-shubham-passive-v5 2760 $R/c32_inner.sh demo-c32 shubham-passive-v5 2400000 32 > $R/logs/chain-v5d-passive.out 2>&1
  logline "(a) PASSIVE harness, v5 demo-c32, typed 'Shubham was': $(grep -o '^ids [0-9]*/32.*' $R/run-demo-c32/shubham-passive-v5.summary.md 2>/dev/null | cut -c1-200)"; touch $R/DONE-v5d-passive
fi
if [[ ! -f $R/DONE-v5d-ordering-v4 ]]; then
  R6X_TYPED="Shubham was" R6X_CAP_MS=2400000 run headed-shubham-v4-ordering 2760 $R/ordering_inner.sh demo-c32.prev keys-mouse 0 32 > $R/logs/chain-v5d-ordering-v4.out 2>&1
  logline "(b) ordering harness, v4 build (demo-c32.prev), keystrokes+mouse 'Shubham was': $(summ $R/runs/ordering-demo-c32.prev-keys-mouse/harness.log $R/reference_ids_shubham_was.json)"; touch $R/DONE-v5d-ordering-v4
fi
{ echo; echo "### 10.X 2×2 on a quiet machine (auto-appended by R6X/run_chain_v5d.sh $(date '+%F %T'))"; echo '```'
  echo "(a) passive harness on v5: $(grep -o '^ids [0-9]*/32.*' $R/run-demo-c32/shubham-passive-v5.summary.md 2>/dev/null | cut -c1-300)"; grep -h 'c32-shubham-passive-v5\] START\|c32-shubham-passive-v5\] END' $W/R6X.log.md | grep -o 'load={[^}]*}' | tr '\n' ' '; echo
  echo "(b) ordering harness on v4 (demo-c32.prev): $(summ $R/runs/ordering-demo-c32.prev-keys-mouse/harness.log $R/reference_ids_shubham_was.json)"; grep -h 'headed-shubham-v4-ordering\] START\|headed-shubham-v4-ordering\] END' $W/R6X.log.md | grep -o 'load={[^}]*}' | tr '\n' ' '; echo; echo '```'; } >> $W/R6X.md
touch $R/CHAIN-V5D-DONE; logline "chain v5d done"
