#!/bin/zsh
# R6X v5c: after chain v5b finishes, wait until the 1-minute load average is < 6 (and the gate is open), then re-run the HEADED keystrokes+mouse
# "Shubham was" guard on the live demo-c32 with the full 32-token cap (R6X_CAP_MS=2400000); append the result to R6X.md §10 and the READY file.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R6X; cd $W
logline() { echo "- $(date '+%F %T') [R6X chain v5c] $*" >> $W/R6X.log.md; echo "$(date '+%T') $*"; }
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
logline "chain v5c armed ($(state)); waiting for CHAIN-V5B-DONE"
until [[ -f $R/CHAIN-V5B-DONE ]]; do sleep 30; done
[[ -d $R/runs/ordering-demo-c32-keys-mouse && ! -d $R/runs/ordering-demo-c32-keys-mouse-load30 ]] && mv $R/runs/ordering-demo-c32-keys-mouse $R/runs/ordering-demo-c32-keys-mouse-load30
R6X_TYPED="Shubham was" R6X_CAP_MS=2400000 run headed-shubham-v5-quiet 2760 $R/ordering_inner.sh demo-c32 keys-mouse 0 32 > $R/logs/chain-v5c-shubham.out 2>&1
res=$(summ $R/runs/ordering-demo-c32-keys-mouse/harness.log $R/reference_ids_shubham_was.json); logline "headed demo-c32 'Shubham was' keystrokes+mouse, quiet machine: $res; load at start/end: see with_lock START/END lines"
echo "demo-c32 v5 re-guard $(date '+%F %T') (quiet machine, load1 < 6, full cap): headed keystrokes+mouse 'Shubham was' $res (R6X/runs/ordering-demo-c32-keys-mouse; the 13/32 run under load 25–31 is kept in ordering-demo-c32-keys-mouse-load30)" >> $W/bundles/demo-c32/READY
{ echo; echo "### 10.R headed 'Shubham was' re-guard on a quiet machine (auto-appended by R6X/run_chain_v5c.sh $(date '+%F %T'))"; echo '```'; echo "$res"; grep -h 'START\|END' $W/R6X.log.md | grep 'headed-shubham-v5-quiet' | cut -c1-300; grep -h '"winners"' $R/runs/ordering-demo-c32-keys-mouse/harness.log | cut -c1-900; echo '```'; } >> $W/R6X.md
touch $R/CHAIN-V5C-DONE; logline "chain v5c done"
