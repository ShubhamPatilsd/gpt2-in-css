#!/bin/zsh
# R4T finish chain after the --lp forwarding fix: (1) wait for the 2L offline check -> PASS; (2) smoke of the fixed smoke-R4T-2L only (ref run kept);
# (3) gate ids [11,3387] + log frame/ULT/Layout counts vs the ref run; (4) rebuild 12-layer bundles/R4T + offline check vs combined4 -> PASS;
# (5) ONE passive 8-token correctness run; READY only on 8/8 ids + verify rc 0. Output: R4T/finish_v2.out, lines in R4T.log.md.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
logline() { echo "- $(date '+%F %T') [R4T finish_v2] $*" >> $W/R4T.log.md; echo "$*"; }
counts() { python3 - "$1" <<'PY'
import sys, json, gzip
from collections import Counter
run = sys.argv[1]; tr = json.load(gzip.open(f"{run}/trace.json.gz", "rt"))["traceEvents"]
cnt = Counter((e.get("pid"), e.get("tid")) for e in tr if e.get("name") == "UpdateLayoutTree" and e.get("ph") == "X"); (PID, TID), _ = cnt.most_common(1)[0]
X = [e for e in tr if e.get("pid") == PID and e.get("tid") == TID and e.get("ph") == "X"]; n = Counter(e["name"] for e in X)
print(f"frames {n['WebFrameWidgetImpl::BeginMainFrame']} ULT {n['UpdateLayoutTree']} Layout {n['Layout']} ULT_ms {sum(e.get('dur',0) for e in X if e['name']=='UpdateLayoutTree')//1000} Layout_ms {sum(e.get('dur',0) for e in X if e['name']=='Layout')//1000} paintLC_ms {sum(e.get('dur',0) for e in X if e['name']=='LocalFrameView::RunPaintLifecyclePhase')//1000} animate_ms {sum(e.get('dur',0) for e in X if e['name']=='WebFrameWidgetImpl::BeginMainFrame')//1000}")
PY
}
until grep -q CHECK-EXIT $W/R4T/offline_check-smoke-2L.log 2>/dev/null; do sleep 10; done
grep -q "RESULT: PASS" $W/R4T/offline_check-smoke-2L.log || { logline "2L offline check FAILED — stop"; exit 2; }
logline "2L offline check PASS (fixed build) -> smoke of smoke-R4T-2L"
$W/R4T/run_smoke.sh smoke2Lb smoke-R4T-2L > $W/R4T/runs/smoke2Lb.wrapper.log 2>&1
f=$(grep '"final"' $W/R4T/runs/smoke-R4T-2L/harness.log | tail -1)
echo "$f" | tr -d ' ' | grep -q '"tokens":\[11,3387\]' || { logline "smoke ids STILL WRONG: $(echo "$f" | cut -c1-200) — stop"; exit 3; }
logline "smoke ids [11,3387] OK. counts R4T: $(counts $W/R4T/runs/smoke-R4T-2L) | ref: $(counts $W/R4T/runs/smoke-R4T-2L-ref)"
logline "rebuilding 12-layer bundles/R4T with the fix"
$W/R4T/compile-R4T.sh R4T 12 8 > $W/R4T/compile-R4T.log 2>&1 || { logline "12L build failed"; exit 4; }
python3 $W/R4T/offline_check_r4t.py $W/bundles/R4T $W/bundles/combined4 > $W/R4T/offline_check-R4T.log 2>&1
grep -q "RESULT: PASS" $W/R4T/offline_check-R4T.log || { logline "12L offline check FAILED — stop"; exit 5; }
logline "12L offline check PASS -> ONE passive 8-token correctness run"
$W/R4T/run_correctness.sh R4T > $W/R4T/run_correctness.out 2>&1; rc=$?
final=$(grep '"final"' $W/R4T/run-R4T/harness.log 2>/dev/null | tail -1)
vrc=$(grep -o 'verify rc=[0-9]*' $W/R4T.log.md | tail -1 | cut -d= -f2)
logline "correctness rc=$rc verify_rc=${vrc:-?} final=$(echo "$final" | cut -c1-300)"
if echo "$final" | tr -d ' ' | grep -q '"tokens":\[11,314,1101,7926,11,475,314,1101\]' && [[ ${vrc:-1} == 0 ]]; then
  echo "READY $(date '+%F %T') 8/8 ids [11,314,1101,7926,11,475,314,1101] verify rc 0 (R4T finish_v2.sh)" > $W/bundles/R4T/READY; logline "bundles/R4T/READY created"
else logline "NOT READY"; fi
