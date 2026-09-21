#!/bin/zsh
# R3M: poll for bundles/R3F/READY and bundles/R3L/READY every 60 s (up to 4 h); log arrivals.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
t0=$(date +%s); f=0; l=0
while true; do
  [[ $f == 0 && -f $W/bundles/R3F/READY ]] && { f=1; echo "- $(date '+%F %T') [R3M wait] R3F READY appeared: $(cat $W/bundles/R3F/READY | head -1)" >> $W/R3M.log.md; }
  [[ $l == 0 && -f $W/bundles/R3L/READY ]] && { l=1; echo "- $(date '+%F %T') [R3M wait] R3L READY appeared: $(cat $W/bundles/R3L/READY | head -1)" >> $W/R3M.log.md; }
  (( f && l )) && { echo BOTH > $W/R3M/READY-STATE; exit 0; }
  now=$(date +%s)
  (( now - t0 >= 3*3600 )) && (( f || l )) && { echo "ONE:$([[ $f == 1 ]] && echo R3F || echo R3L)" > $W/R3M/READY-STATE; exit 0; }
  (( now - t0 >= 4*3600 )) && { echo NONE > $W/R3M/READY-STATE; exit 1; }
  echo "waiting f=$f l=$l $(date '+%T')" > $W/R3M/wait-status.txt
  sleep 60
done
