#!/bin/zsh
# R6X v5e: same-harness smoke comparison (coordinator): ordering harness, 32 tokens 'Shubham was', old 2-layer twin (v3 wiring) vs fixed (v5) — diff the 32 ids. Was: 2x2 on a quiet machine (gate AND load1 < 6): (a) PASSIVE harness (bench_native: fill + keyboard Run, DOM.querySelector polling only) typed "Shubham was"
# on the live v5 demo-c32; (b) the ordering harness (keystrokes + mouse + per-capture getComputedStyle reads) on the kept v4 build bundles/demo-c32.prev.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R6X; cd $W
logline() { echo "- $(date '+%F %T') [R6X chain v5e] $*" >> $W/R6X.log.md; echo "$(date '+%T') $*"; }
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
logline "chain v5e armed ($(state)); waiting for CHAIN-V5D-DONE"
until [[ -f $R/CHAIN-V5D-DONE ]]; do sleep 30; done
for b in smoke-demo-2L smoke-demo-2L-v5; do
  [[ -f $R/DONE-v5e-$b ]] && continue
  R6X_TYPED="Shubham was" R6X_CAP_MS=900000 run smoke32-$b 1200 $R/ordering_inner.sh $b keys-mouse-32 0 32 > $R/logs/chain-v5e-$b.out 2>&1
  logline "smoke 32 tokens, ordering harness, $b: $(summ $R/runs/ordering-$b-keys-mouse-32/harness.log $R/reference_ids_shubham_was_2layers.json)"; touch $R/DONE-v5e-$b
done
python3 - <<'PY' >> $W/R6X.md
import json
W = "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19"
def ids(path):
    w = None
    for l in open(path):
        try: j = json.loads(l)
        except Exception: continue
        if j.get("event") == "winners": w = j
    return [int(float(x)) for x in w["feedback"] if x not in ("", None)] if w else []
a = ids(f"{W}/R6X/runs/ordering-smoke-demo-2L-keys-mouse-32/harness.log"); b = ids(f"{W}/R6X/runs/ordering-smoke-demo-2L-v5-keys-mouse-32/harness.log")
ref = json.load(open(f"{W}/R6X/reference_ids_shubham_was_2layers.json"))["freeRunningReference"]
print("\n### 10.S same-harness 2-layer smoke comparison, 32 tokens 'Shubham was' (ordering harness, keystrokes + mouse)\n")
print("```"); print("old (v3 wiring):", a); print("fixed (v5)     :", b); print("reference      :", ref)
print("old vs ref:", sum(x == y for x, y in zip(a, ref)), "/", len(a), "| fixed vs ref:", sum(x == y for x, y in zip(b, ref)), "/", len(b), "| old vs fixed identical:", a == b, "first diff:", next((i + 1 for i, (x, y) in enumerate(zip(a, b)) if x != y), None)); print("```")
PY
touch $R/CHAIN-V5E-DONE; logline "chain v5e done"
