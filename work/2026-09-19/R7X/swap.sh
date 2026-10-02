#!/bin/zsh
# R7X atomic swap (run ONLY after the full guard set passed; not while any Chrome serves the live bundles): bundles/<b> -> <b>.prev (older .prev -> .prev2), <b>.next -> <b>.
set -eu; W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; cd $W/bundles
[[ -e $W/CHROME.lock ]] && { echo "CHROME.lock held ($(cat $W/CHROME.lock/owner 2>/dev/null)) — not swapping"; exit 3; }
for b in demo-c32 demo-8; do
  [[ -d $b.next && -f $b.next/READY ]] || { echo "$b.next missing or not READY"; exit 2; }
  [[ -d $b.prev2 ]] && rm -rf $b.prev2
  [[ -d $b.prev ]] && mv $b.prev $b.prev2
  mv $b $b.prev && mv $b.next $b
  echo "$(date '+%F %T') swapped: $b (was v6, now $b.prev) <- $b.next; previous .prev kept as $b.prev2"
done
