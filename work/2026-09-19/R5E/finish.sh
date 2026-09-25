#!/bin/zsh
# R5E finish: after run_chain.sh — smoke-pair analyses, correctness evaluation, R5E.md §4, READY on 8/8 + verify rc 0.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R5E
logline() { echo "- $(date '+%F %T') [R5E finish] $*" >> $W/R5E.log.md; echo "$*"; }
{
echo; echo "## 4. Chrome (filled by R5E/finish.sh at $(date '+%F %T'))"; echo
if [[ -f $R/runs/smoke-R5E-2L-ref/frames.md && -f $R/runs/smoke-R5E-2L/frames.md ]]; then
  echo "### 4.1 2-layer smoke pair (cap 8, light trace + invalidation tracking; \`R5E/runs/smoke-R5E-2L{-ref,}\`)"; echo
  for b in smoke-R5E-2L-ref smoke-R5E-2L; do echo "- $b: $(grep -o '"tokens":\[[^]]*\]' $R/runs/$b/harness.log | tail -1); $(grep -o '"metrics-after"[^}]*}' $R/runs/$b/harness.log | cut -c1-200)"; done
  echo; echo '```'; python3 $R/compare_frames.py $R/runs/smoke-R5E-2L-ref $R/runs/smoke-R5E-2L 2>&1 | tee $R/runs/compare_frames.txt; echo '```'
  for b in smoke-R5E-2L-ref smoke-R5E-2L; do python3 $R/pass_census.py $R/runs/$b > /dev/null 2> $R/runs/$b/pass_census.err && echo "- per-pass element census (which classes each pass restyles): \`R5E/runs/$b/pass_census.md\`"; done
else
  echo "smoke pair did not produce frames (see R5E.log.md)"
fi
out=$R/run-R5E
if [[ -f $out/harness.log ]]; then
  echo; echo "### 4.2 ONE 8-token correctness run of \`bundles/R5E\` (\`R5E/run_correctness.sh R5E\`, R4M harness, keyboard-free click, heap flag on; NOT a timing run)"; echo
  ids=$(grep -o '"tokens":\[[^]]*\]' $out/harness.log | tail -1); vrc=$(grep -o 'verify rc=[0-9]*' $W/R5E.log.md | tail -1)
  echo "- ids: $ids (required [11,314,1101,7926,11,475,314,1101]); $vrc; $(grep -o "'finalResidualError': {[^}]*}" $out/verify.log | head -1)"
  echo "- capture times: $(grep -o '"token-captured"[^}]*}' $out/harness.log | grep -o '"sinceRunMs":[0-9]*' | cut -d: -f2 | tr '\n' ' ') ms; $(grep -o '"metrics-after"[^}]*}' $out/harness.log | cut -c1-260)"
  [[ -f $out/rss.log ]] && python3 - "$out" <<'PY'
import sys,re
out=sys.argv[1]; rows=[l.split() for l in open(f"{out}/rss.log") if len(l.split())==3]
peak=max((int(r[2]) for r in rows), default=0); peaksum=max((int(r[1]) for r in rows), default=0)
caps=[int(x) for x in re.findall(r'"sinceRunMs":(\d+)', open(f"{out}/harness.log").read())]
t0=None
for l in open(f"{out}/harness.log"):
    if '"run-clicked"' in l: t0=int(re.search(r'"t":(\d+)',l).group(1))
per=[]
if t0 is not None and rows:
    # rss.log seconds are since sampler start (~ harness start); align by harness t of run-clicked
    for k,c in enumerate(caps,1):
        sec=(t0+c)//1000; cand=[int(r[2]) for r in rows if int(r[0])<=sec]; per.append(cand[-1] if cand else 0)
print(f"- RSS (1 Hz `ps`, largest headless-Chrome process = renderer): peak {peak} MB (all Chrome processes {peaksum} MB); at each token capture: {per} MB (combined7 R5A run: peak 4,277; B5 runs 5.6–5.95 GB at token 8)")
PY
  if [[ $ids == '"tokens":[11,314,1101,7926,11,475,314,1101]' && $vrc == 'verify rc=0' ]]; then
    echo "- **READY** created ($(date '+%F %T'))."; echo "R5E $(date '+%F %T') 8/8 ids, verify rc 0 (R5E/run-R5E)" > $W/bundles/R5E/READY; logline "READY written"
  else
    echo "- **NOT READY**: ids or verify failed — see R5E/run-R5E/{harness.log,verify.log}"; logline "NOT READY (ids=$ids $vrc)"
  fi
else
  echo "correctness run did not start (smoke failed or gate never opened) — see R5E.log.md"
fi
} >> $W/R5E.md
touch $R/FINISH-DONE; logline "finish done"
