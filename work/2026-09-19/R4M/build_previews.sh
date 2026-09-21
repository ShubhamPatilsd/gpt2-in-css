#!/bin/zsh
# R4M preview builds (R4S+R4D merged tools, before R4T lands): all-on / all-off / one-off at capacity 8 and 32 -> R4M/scratch/<name>
R=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4M
T=${TOOLS:-$R/tools}; P=${PREFIX:-p}
b() { local name=$1 cap=$2; shift 2; echo "== $(date '+%T') $name cap=$cap $*"; env "$@" $R/compile.sh $T $R/scratch/$name $cap > $R/scratch/$name.log 2>&1 && echo "   rc=0 $(tail -1 $R/scratch/$name.log | cut -c1-200)" || echo "   FAILED rc=$? $(tail -3 $R/scratch/$name.log | cut -c1-400)"; }
b ${P}8        8
b ${P}8-alloff 8  R4S_SMALL_HOPS=0 R4D_EMPTY_UNFILLED=0 R4D_LEAN_LATCH=0 R4D_UNPACK_V=0 R4D_HIDE_UNFILLED=0 R4T_CONSUMER_CHUNK=${R4T_OFF:-}
b ${P}8-noR4S  8  R4S_SMALL_HOPS=0
b ${P}8-noR4D  8  R4D_EMPTY_UNFILLED=0 R4D_LEAN_LATCH=0 R4D_UNPACK_V=0 R4D_HIDE_UNFILLED=0
b ${P}32        32
b ${P}32-alloff 32 R4S_SMALL_HOPS=0 R4D_EMPTY_UNFILLED=0 R4D_LEAN_LATCH=0 R4D_UNPACK_V=0 R4D_HIDE_UNFILLED=0 R4T_CONSUMER_CHUNK=${R4T_OFF:-}
b ${P}32-noR4D 32 R4D_EMPTY_UNFILLED=0 R4D_LEAN_LATCH=0 R4D_UNPACK_V=0 R4D_HIDE_UNFILLED=0
b ${P}32-noR4S 32 R4S_SMALL_HOPS=0
echo "== $(date '+%T') ALL DONE"
