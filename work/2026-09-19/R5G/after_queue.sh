#!/bin/zsh
# R5G: 4th flag set, chained after queue.sh finishes — repeat of o4s on the footprint-enabled harness.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; D=$W/R5G
until [[ -f $D/QUEUE-DONE || -f $D/STOP ]]; do sleep 30; done
[[ -f $D/STOP ]] && exit 0
echo "- $(date '+%F %T') R5G queue: === flag set 'o4s-b' (repeat of o4s with footprint sampling): JS_FLAGS='--heap-growing-percent=10 --optimize-for-size'" >> $W/R5G.log.md
CAND_JS_FLAGS="--heap-growing-percent=10 --optimize-for-size" CAND_EXTRA_ARGS="" $D/pair.sh o4s-b; rc=$?
echo "- $(date '+%F %T') R5G queue: === flag set 'o4s-b' finished rc=$rc" >> $W/R5G.log.md
python3 $D/analyze_r5g.py o4s-b > $D/analysis-o4s-b.md 2>&1 && echo "- $(date '+%F %T') R5G queue: analysis → R5G/analysis-o4s-b.md: $(grep -m1 '^PAIR' $D/analysis-o4s-b.md | cut -c1-300)" >> $W/R5G.log.md
touch $D/QUEUE2-DONE
