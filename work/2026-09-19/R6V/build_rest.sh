#!/bin/zsh
# R6V: sequential builds (one at a time): cap-8 flag-off twin -> compare to combined8 -> delete; combined8-c32-ui; cap-32 flag-off twin -> compare to combined8-c32 -> delete.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; cd $W
log() { echo "- $(date '+%F %T') [R6V build] $*" >> $W/R6V.log.md; echo "$(date '+%T') $*"; }
mkdir -p R6V/scratch R6V/logs
log "twin p8-off: R6V_PROGRESS_UI=0 cap 8"
R6V_PROGRESS_UI=0 R6V/compile.sh $W/R6V/scratch/p8-off 8 12 > R6V/logs/compile-p8-off.log 2>&1 || log "BUILD FAIL p8-off"
python3 R5X/compare_bundles.py bundles/combined8 R6V/scratch/p8-off > R6V/logs/compare-p8-off-vs-combined8.log 2>&1; log "compare p8-off vs combined8: $(grep -E '^(index|runtime|manifest|font)' R6V/logs/compare-p8-off-vs-combined8.log | cut -c1-160 | tr '\n' ' | ')"
rm -rf R6V/scratch/p8-off; log "twin p8-off deleted"
log "combined8-c32-ui: VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 cap 32"
VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 R6V/compile.sh $W/bundles/combined8-c32-ui 32 12 > R6V/logs/compile-combined8-c32-ui.log 2>&1 || log "BUILD FAIL combined8-c32-ui"
log "combined8-c32-ui built: $(ls -la bundles/combined8-c32-ui | awk '{print $5, $NF}' | tr '\n' ' ')"
log "twin p32w-off: R6V_PROGRESS_UI=0 VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 cap 32"
R6V_PROGRESS_UI=0 VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 R6V/compile.sh $W/R6V/scratch/p32w-off 32 12 > R6V/logs/compile-p32w-off.log 2>&1 || log "BUILD FAIL p32w-off"
python3 R5X/compare_bundles.py bundles/combined8-c32 R6V/scratch/p32w-off > R6V/logs/compare-p32w-off-vs-combined8-c32.log 2>&1; log "compare p32w-off vs combined8-c32: $(grep -E '^(index|runtime|manifest|font)' R6V/logs/compare-p32w-off-vs-combined8-c32.log | cut -c1-160 | tr '\n' ' | ')"
rm -rf R6V/scratch/p32w-off; log "twin p32w-off deleted"
touch R6V/BUILDS-DONE
