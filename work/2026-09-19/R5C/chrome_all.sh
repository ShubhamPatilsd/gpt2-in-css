#!/bin/zsh
# R5C Chrome plan: session 1 = 2-layer smoke pair (on, then off) under ONE lock hold with a light trace; if both give [11, 3387],
# session 2 = ONE passive 8-token correctness run of bundles/R5C. Each session goes through run_chrome.sh (machine gate + lock).
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; cd $W/R5C
logline() { echo "- $(date '+%F %T') [R5C chrome_all] $*" >> $W/R5C.log.md; echo "$(date '+%T') $*"; }
./run_chrome.sh smoke-pair 1200 zsh -c './smoke_inner.sh smoke-R5C-2L smoke-R5C-2L; ./smoke_inner.sh smoke-R5C-2L-ref smoke-R5C-2L-ref' > logs/chrome-smoke-pair.out 2>&1
rc=$?
ids_on=$(grep -o '"tokens":\[[^]]*\]' runs/smoke-R5C-2L/harness.log | tail -1); ids_off=$(grep -o '"tokens":\[[^]]*\]' runs/smoke-R5C-2L-ref/harness.log | tail -1)
logline "smoke pair rc=$rc on=$ids_on off=$ids_off"
for r in smoke-R5C-2L smoke-R5C-2L-ref; do [[ -f runs/$r/trace.json.gz ]] && python3 frames.py runs/$r > logs/frames-$r.json 2>&1; done
if [[ "$ids_on" == '"tokens":[11,3387]' && "$ids_off" == '"tokens":[11,3387]' ]]; then
  ./run_chrome.sh correctness-R5C 1500 ./correctness_inner.sh R5C > logs/chrome-correctness-R5C.out 2>&1
  logline "correctness rc=$? $(grep '"final"' run-R5C/harness.log | cut -c1-300)"
else
  logline "smoke ids not both [11,3387] — NOT starting the 12-layer correctness run"
fi
touch logs/CHROME_ALL_DONE
