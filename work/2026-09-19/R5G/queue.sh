#!/bin/zsh
# R5G queue: runs the flag-set pairs sequentially (each pair = one lock hold). usage: queue.sh "<label>|<JS_FLAGS>|<EXTRA_ARGS>" ...
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; D=$W/R5G
log() { echo "- $(date '+%F %T') R5G queue: $*" >> $W/R5G.log.md; echo "$(date '+%T') $*"; }
log "started pid $$ with ${#@} flag sets: $*"
for spec in "$@"; do
  IFS='|' read -r label js extra <<< "$spec"
  [[ -f $D/STOP ]] && { log "STOP file present — exiting before $label"; break; }
  log "=== flag set '$label': JS_FLAGS='$js' EXTRA_ARGS='$extra'"
  CAND_JS_FLAGS="$js" CAND_EXTRA_ARGS="$extra" $D/pair.sh $label; rc=$?
  log "=== flag set '$label' finished rc=$rc"
  python3 $D/analyze_r5g.py $label >> $D/analysis-$label.md 2>&1 && log "analysis → R5G/analysis-$label.md: $(grep -m1 '^PAIR' $D/analysis-$label.md | cut -c1-300)"
done
log "queue done"; touch $D/QUEUE-DONE
