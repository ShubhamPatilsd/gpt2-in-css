#!/bin/zsh
# R4M c32 finisher: wait for run-combined6-c32/DONE, then create bundles/combined6-c32/READY ONLY if the summary says ids 32/32.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
out=$W/R4M/run-combined6-c32; B=$W/bundles/combined6-c32; label=${1:-c32-run1}
log() { echo "- $(date '+%F %T') [R4M c32 finisher] $*" >> $W/R4M.log.md; }
while [[ ! -f $out/DONE ]]; do sleep 30; done; sleep 2
s=$out/$label.summary.md
if grep -q '^ids 32/32 vs reference' $s 2>/dev/null; then
  echo "combined6-c32 READY $(date '+%F %T'): $(sed -n 3p $s | cut -c1-60); $(grep '^total' $s)" > $B/READY
  log "READY created: $(grep '^total' $s)"
else
  log "READY NOT created: $(sed -n 3p $s 2>/dev/null | cut -c1-200)"
fi
