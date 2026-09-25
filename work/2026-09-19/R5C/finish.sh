#!/bin/zsh
# R5C unattended finish: wait for chrome_all.sh, then (a) append the smoke frame tables + correctness result to R5C.md,
# (b) create bundles/R5C/READY only on 8/8 ids + verify rc 0, (c) log. Safe to re-run.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; cd $W/R5C
logline() { echo "- $(date '+%F %T') [R5C finish] $*" >> $W/R5C.log.md; }
while [[ ! -f logs/CHROME_ALL_DONE ]]; do sleep 60; done
{
  echo; echo "## 5b. Smoke pair — harness results (appended unattended by R5C/finish.sh, $(date '+%F %T'))"; echo
  for r in smoke-R5C-2L smoke-R5C-2L-ref; do
    echo "### $r"; echo; echo '```'; grep -E '"event":"(loaded|pre-run-idle|final|token-captured|metrics|trace)"' runs/$r/harness.log 2>/dev/null | cut -c1-600; echo '```'
    [[ -f runs/$r/frames.md ]] && { echo; echo "Per-token frame summary (R5C/frames.py, full table in \`R5C/runs/$r/frames.md\`):"; echo; sed -n '/^| token/,/^$/p' runs/$r/frames.md; }
    echo
  done
  echo "## 6b. 12-layer correctness run — harness results (appended unattended)"; echo; echo '```'
  grep -E '"event":"(loaded|final|token-captured)"' run-R5C/harness.log 2>/dev/null | cut -c1-700; echo; tail -c 900 run-R5C/verify.log 2>/dev/null; echo '```'
} >> $W/R5C.md
ids=$(grep -o '"tokens":\[[^]]*\]' run-R5C/harness.log 2>/dev/null | tail -1)
vrc=$(grep -o 'verify rc=[0-9]*' logs/chrome-correctness-R5C.out 2>/dev/null | tail -1)
if [[ "$ids" == '"tokens":[11,314,1101,7926,11,475,314,1101]' && "$vrc" == "verify rc=0" ]]; then
  touch $W/bundles/R5C/READY; logline "READY created: ids 8/8, $vrc"
  echo "- READY created $(date '+%F %T') (8/8 ids, verify rc 0)." >> $W/bundles/R5C/BUILD.md
else
  logline "NOT READY: ids=$ids $vrc (see run-R5C/harness.log, verify.log)"
fi
touch logs/FINISH_DONE
