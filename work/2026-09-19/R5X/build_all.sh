#!/bin/zsh
# R5X: the two deliverables + five flag twins, three builds at a time (nice 19). Logs in R5X/logs/compile-<name>.log; DONE-<name> markers.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; cd $W/R5X
OFF_E="R5E_LEAN_WALLS=0 R5E_LP_INHERIT=0 R5E_DROP_DEAD_LISTS=0 R5E_KEEP_DIAG=1"
b() { local name=$1 out=$2 cap=$3; shift 3; ( echo "$(date '+%T') start $name: $* cap=$cap"; env "$@" ./compile.sh $out $cap 12 > logs/compile-$name.log 2>&1; echo "$(date '+%T') end $name rc=$?"; touch DONE-$name ) }
echo "$(date '+%T') batch 1"
b combined8      $W/bundles/combined8      8  R5H_CH_SCORES=1 &
b combined8-c32  $W/bundles/combined8-c32  32 R5H_CH_SCORES=1 VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 &
b p8-alloff      $W/R5X/scratch/p8-alloff  8  ${=OFF_E} R5H_CH_SCORES=0 &
wait
echo "$(date '+%T') batch 2"
b p32w-alloff    $W/R5X/scratch/p32w-alloff 32 ${=OFF_E} R5H_CH_SCORES=0 VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 &
b p8-R5Eonly     $W/R5X/scratch/p8-R5Eonly  8  R5H_CH_SCORES=0 &
b p8-R5Honly     $W/R5X/scratch/p8-R5Honly  8  ${=OFF_E} R5H_CH_SCORES=1 &
wait
echo "$(date '+%T') batch 3"
b p32w-R5Honly   $W/R5X/scratch/p32w-R5Honly 32 ${=OFF_E} R5H_CH_SCORES=1 VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 &
wait
echo "$(date '+%T') all builds done"; touch DONE-ALL
