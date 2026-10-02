#!/bin/zsh
# R7H builds (run under the lock so no other agent's Chrome runs during the builds): guard ON and OFF twins of the 2-layer smoke,
# demo-c32 and demo-8, each into R7H/twin-<name>-{on,off}; OFF must be identical to the shipped bundle (compare_rules), ON must differ
# only by the guard rules/elements; the ON builds are then moved to bundles/<b>.r7h (never written into a live bundle dir).
set -u; W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R7H; cd $W; mkdir -p $R/logs
build() { # name cap blocks flag extra...
  local name=$1 cap=$2 blocks=$3 flag=$4; shift 4
  echo "### $(date '+%T') build $name (R7H_ID_GUARD=$flag)"; rm -rf $R/twin-$name
  env "$@" R7H_ID_GUARD=$flag $R/compile.sh $R/twin-$name $cap $blocks > $R/logs/compile-$name.log 2>&1 || { echo "BUILD FAILED $name"; tail -3 $R/logs/compile-$name.log; exit 1; }
  du -sm $R/twin-$name | cut -f1 | tr '\n' ' '; echo "MB"
}
build smoke-2L-off 32 2 0 VALUE_LAYOUT=widths R4S_SMALL_HOPS=0
build smoke-2L-on  32 2 1 VALUE_LAYOUT=widths R4S_SMALL_HOPS=0
build demo-c32-off 32 12 0 VALUE_LAYOUT=widths R4S_SMALL_HOPS=0
build demo-c32-on  32 12 1 VALUE_LAYOUT=widths R4S_SMALL_HOPS=0
build demo-8-off 8 12 0
build demo-8-on  8 12 1
build smoke-2L-fault 32 2 1 VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 R6X_SCROLLBAR_FIX=0   # fault injection: guard on, v6 scrollbar fix OFF
echo "### $(date '+%T') builds done"
