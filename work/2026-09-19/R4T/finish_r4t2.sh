#!/bin/zsh
# R4T2 chain: wait for the mech fixture (results/mech.DONE) and both offline checks (PASS) -> 2-layer smoke of smoke-R4T2-2L (ref kept) -> gate ids
# [11,3387] + counts -> ONE passive 8-token correctness run of bundles/R4T2 -> READY only on 8/8 + verify rc 0. Output R4T/finish_r4t2.out.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
logline() { echo "- $(date '+%F %T') [R4T2 finish] $*" >> $W/R4T.log.md; echo "$*"; }
counts() { python3 - "$1" <<'PY'
import sys, json, gzip
from collections import Counter
run = sys.argv[1]; tr = json.load(gzip.open(f"{run}/trace.json.gz", "rt"))["traceEvents"]
cnt = Counter((e.get("pid"), e.get("tid")) for e in tr if e.get("name") == "UpdateLayoutTree" and e.get("ph") == "X"); (PID, TID), _ = cnt.most_common(1)[0]
X = [e for e in tr if e.get("pid") == PID and e.get("tid") == TID and e.get("ph") == "X"]; n = Counter(e["name"] for e in X)
print(f"frames {n['WebFrameWidgetImpl::BeginMainFrame']} ULT {n['UpdateLayoutTree']} Layout {n['Layout']} ULT_ms {sum(e.get('dur',0) for e in X if e['name']=='UpdateLayoutTree')//1000} Layout_ms {sum(e.get('dur',0) for e in X if e['name']=='Layout')//1000} paintLC_ms {sum(e.get('dur',0) for e in X if e['name']=='LocalFrameView::RunPaintLifecyclePhase')//1000} animate_ms {sum(e.get('dur',0) for e in X if e['name']=='WebFrameWidgetImpl::BeginMainFrame')//1000}")
PY
}
until [[ -f $W/R4T/fixture/results/mech.DONE ]] && grep -q CHECK-EXIT $W/R4T/offline_check-R4T2.log 2>/dev/null && grep -q CHECK-EXIT $W/R4T/offline_check-smoke-R4T2-2L.log 2>/dev/null; do sleep 15; done
rm -f $W/R4T/fixture/pages/*.html && logline "fixture pages deleted after the mech run (generators + variants.json kept; regenerate with gen_r4t.py / gen_mech.py)"
grep -q "RESULT: PASS" $W/R4T/offline_check-smoke-R4T2-2L.log && grep -q "RESULT: PASS" $W/R4T/offline_check-R4T2.log || { logline "R4T2 offline checks not PASS — stop"; exit 2; }
logline "R4T2 offline checks PASS -> smoke of smoke-R4T2-2L"
$W/R4T/run_smoke.sh smoke2L-r4t2 smoke-R4T2-2L > $W/R4T/runs/smoke2L-r4t2.wrapper.log 2>&1
f=$(grep '"final"' $W/R4T/runs/smoke-R4T2-2L/harness.log | tail -1)
echo "$f" | tr -d ' ' | grep -q '"tokens":\[11,3387\]' || { logline "R4T2 smoke ids WRONG: $(echo "$f" | cut -c1-200) — stop"; exit 3; }
logline "R4T2 smoke ids [11,3387] OK. counts R4T2: $(counts $W/R4T/runs/smoke-R4T2-2L) | R4T: $(counts $W/R4T/runs/smoke-R4T-2L) | ref: $(counts $W/R4T/runs/smoke-R4T-2L-ref)"
$W/R4T/run_correctness.sh R4T2 > $W/R4T/run_correctness_r4t2.out 2>&1; rc=$?
final=$(grep '"final"' $W/R4T/run-R4T2/harness.log 2>/dev/null | tail -1)
vrc=$(grep -o 'verify rc=[0-9]*' $W/R4T.log.md | tail -1 | cut -d= -f2)
logline "R4T2 correctness rc=$rc verify_rc=${vrc:-?} final=$(echo "$final" | cut -c1-300)"
if echo "$final" | tr -d ' ' | grep -q '"tokens":\[11,314,1101,7926,11,475,314,1101\]' && [[ ${vrc:-1} == 0 ]]; then
  echo "READY $(date '+%F %T') 8/8 ids verify rc 0 (R4T finish_r4t2.sh)" > $W/bundles/R4T2/READY; logline "bundles/R4T2/READY created"
else logline "R4T2 NOT READY"; fi
