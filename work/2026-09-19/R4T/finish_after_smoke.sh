#!/bin/zsh
# R4T: after the queued 2-layer smoke finishes, gate on ids [11, 3387] in BOTH bundles, then run ONE passive 8-token correctness run of bundles/R4T
# (R4T/run_correctness.sh, lock protocol inside) and create bundles/R4T/READY only on 8/8 ids + verify rc 0. Writes R4T/finish.out.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
logline() { echo "- $(date '+%F %T') [R4T finish] $*" >> $W/R4T.log.md; echo "$*"; }
while [[ ! -f $W/R4T/runs/smoke2L.DONE ]]; do sleep 20; done
ok=1
for b in smoke-R4T-2L smoke-R4T-2L-ref; do
  f=$(grep '"final"' $W/R4T/runs/$b/harness.log 2>/dev/null | tail -1)
  echo "$f" | grep -q '11, *3387\|11,3387\|\[11,3387\]\|"ids":\[11,3387\]' || { echo "$f" | tr -d ' ' | grep -q '11,3387' || ok=0; }
  logline "smoke $b: $(echo "$f" | cut -c1-260)"
  python3 $W/R4T/frames.py $W/R4T/runs/$b > /dev/null 2>&1 && logline "smoke $b frames: $(grep -c '^|' $W/R4T/runs/$b/frames.md) table rows -> $W/R4T/runs/$b/frames.md"
done
if (( ! ok )); then logline "smoke ids mismatch — NOT running the correctness run"; exit 3; fi
logline "smoke ids OK in both bundles -> ONE passive 8-token correctness run of bundles/R4T"
$W/R4T/run_correctness.sh R4T > $W/R4T/run_correctness.out 2>&1; rc=$?
final=$(grep '"final"' $W/R4T/run-R4T/harness.log 2>/dev/null | tail -1)
vrc=$(grep -o 'verify rc=[0-9]*' $W/R4T.log.md | tail -1 | cut -d= -f2)
logline "correctness rc=$rc verify_rc=${vrc:-?} final=$(echo "$final" | cut -c1-300)"
ids=$(echo "$final" | tr -d ' ' | grep -o '\[11,314,1101,7926,11,475,314,1101\]' | head -1)
if [[ -n $ids && ${vrc:-1} == 0 ]]; then echo "READY $(date '+%F %T') 8/8 ids $ids verify rc 0 (R4T finish_after_smoke.sh)" > $W/bundles/R4T/READY; logline "bundles/R4T/READY created"; else logline "NOT READY (ids='$ids' verify_rc=${vrc:-?})"; fi
