#!/bin/zsh
# R4W build chain: 2-layer smoke pair (on/off, capacity 8) then combined4-c32d (12 layers, capacity 32).
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
touch $W/CPU-BUSY-R4W
log() { echo "- $(date '+%F %T') [R4W build] $*" >> $W/R4W.log.md; }
log "build chain start: smoke-R4W-2L (R4W_V_PRECAT=1), smoke-R4W-2L-ref (=0), combined4-c32d"
R4W_V_PRECAT=1 $W/R4W/compile-r4w.sh smoke-R4W-2L 8 2 > $W/R4W/compile-smoke-R4W-2L.log 2>&1; log "smoke-R4W-2L rc=$?"
R4W_V_PRECAT=0 $W/R4W/compile-r4w.sh smoke-R4W-2L-ref 8 2 > $W/R4W/compile-smoke-R4W-2L-ref.log 2>&1; log "smoke-R4W-2L-ref rc=$?"
R4W_V_PRECAT=1 $W/R4W/compile-r4w.sh combined4-c32d 32 12 > $W/R4W/compile-c32d.log 2>&1; log "combined4-c32d rc=$?"
rm -f $W/CPU-BUSY-R4W
touch $W/R4W/BUILD-DONE
log "build chain done"
