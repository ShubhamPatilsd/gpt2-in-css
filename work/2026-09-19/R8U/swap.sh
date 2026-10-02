#!/bin/zsh
# R8U atomic swap (run only after the coordinator/user approved the screenshots; not while any harness Chrome holds CHROME.lock):
#   bundles/demo-c32.next-v5 -> bundles/demo-c32   and   bundles/demo-8.next -> bundles/demo-8
#   current live -> <b>.prev, older .prev -> .prev2 (the old .prev2 is deleted, as in R7X/swap.sh). READY must exist in the source.
set -eu; W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; cd $W/bundles
[[ -e $W/CHROME.lock ]] && { echo "CHROME.lock held ($(cat $W/CHROME.lock/owner 2>/dev/null)) — not swapping"; exit 3; }
for pair in demo-c32:demo-c32.next-v5 demo-8:demo-8.next; do
  b=${pair%%:*}; src=${pair##*:}
  [[ -d $src && -f $src/READY ]] || { echo "$src missing or not READY"; exit 2; }
done
for pair in demo-c32:demo-c32.next-v5 demo-8:demo-8.next; do
  b=${pair%%:*}; src=${pair##*:}
  [[ -d $b.prev2 ]] && rm -rf $b.prev2
  [[ -d $b.prev ]] && mv $b.prev $b.prev2
  mv $b $b.prev && mv $src $b
  echo "$(date '+%F %T') swapped: $b (round 7 now $b.prev) <- $src; previous .prev kept as $b.prev2" | tee -a $W/R8U.log.md
done
