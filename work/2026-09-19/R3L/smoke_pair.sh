#!/bin/zsh
# R3L: both 2-layer smokes (font-mode bundle + flag-off ref) in ONE lock acquisition, then per-frame anatomy.
# usage: smoke_pair.sh   (writes R3L/runs/smoke-2L-font, R3L/runs/smoke-2L-ref, frames.md in each)
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
cd $W/R3L
./run_chrome.sh smoke-2L-pair 600 zsh -c "$W/R3L/smoke_inner.sh smoke-R3L-2L-font smoke-2L-font; $W/R3L/smoke_inner.sh smoke-R3L-2L-ref smoke-2L-ref"
rc=$?
for r in smoke-2L-font smoke-2L-ref; do
  [[ -f runs/$r/trace.json.gz ]] && python3 frames.py runs/$r runs/$r/frames.md > /dev/null 2>&1 && echo "frames.md written for $r"
  grep '"final"' runs/$r/harness.log | cut -c1-300
done
exit $rc
