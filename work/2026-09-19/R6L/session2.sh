#!/bin/zsh
# R6L session 2: the ONE prompt-40 32-token correctness run of combined8-c32-fast (ids must equal R4P/reference_ids_32_40.json).
set -u; W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
B0_PROMPT_TOKEN=40 $W/R6L/c32_inner.sh combined8-c32-fast c32-p40 2400000
rc=$?
if grep -q "32/32 tokens" $W/R6L/run-combined8-c32-fast/c32-p40.summary.md 2>/dev/null; then
  echo "READY $(date '+%F %T') R6L: prompt-40 32/32 (R6L/run-combined8-c32-fast/c32-p40.summary.md)" > $W/bundles/combined8-c32-fast/READY
  echo "- $(date '+%F %T') combined8-c32-fast c32-p40: 32/32 → READY created" >> $W/R6L.log.md
else
  echo "- $(date '+%F %T') combined8-c32-fast c32-p40: NOT 32/32 or run failed (rc=$rc) — see R6L/run-combined8-c32-fast/" >> $W/R6L.log.md
fi
touch $W/R6L/loads/SESSION2-DONE
