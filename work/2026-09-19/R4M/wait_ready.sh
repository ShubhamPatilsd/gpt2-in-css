#!/bin/zsh
# R4M: poll for bundles/R4T/READY and bundles/combined5/READY every 60 s (up to 5 h); log arrivals. (R4S is READY already.)
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
t0=$(date +%s); t=0; d=0
while true; do
  [[ $t == 0 && -f $W/bundles/R4T/READY ]] && { t=1; echo "- $(date '+%F %T') [R4M wait] R4T READY appeared: $(head -1 $W/bundles/R4T/READY)" >> $W/R4M.log.md; }
  [[ $d == 0 && -f $W/bundles/combined5/READY ]] && { d=1; echo "- $(date '+%F %T') [R4M wait] combined5 READY appeared: $(head -1 $W/bundles/combined5/READY)" >> $W/R4M.log.md; }
  (( t && d )) && { echo BOTH > $W/R4M/READY-STATE; exit 0; }
  now=$(date +%s)
  (( now - t0 >= 4*3600 )) && (( t || d )) && { echo "ONE:$([[ $t == 1 ]] && echo R4T || echo combined5)" > $W/R4M/READY-STATE; exit 0; }
  (( now - t0 >= 5*3600 )) && { echo NONE > $W/R4M/READY-STATE; exit 1; }
  echo "waiting R4T=$t combined5=$d $(date '+%T')" > $W/R4M/wait-status.txt
  sleep 60
done
