#!/bin/zsh
# R7B (cap-8 recipe = demo-8: default VALUE_LAYOUT=runs, no R4S override): run compile.sh once CHROME.lock is free (no build while another agent's Chrome holds the lock) and load1 < 8. usage: build_when_free.sh <log> <out> <cap> [blocks]  (flags via env)
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; log=$1; shift
n=0
while [[ -e $W/CHROME.lock ]] || (( $(sysctl -n vm.loadavg | awk '{print int($2)}') >= 8 )); do
  (( n % 60 == 0 )) && echo "$(date '+%T') waiting: lock=$(cat $W/CHROME.lock/owner 2>/dev/null || echo free) load=$(sysctl -n vm.loadavg)" >> $log
  n=$((n+1)); sleep 5
done
echo "$(date '+%T') building $* (lock free, load $(sysctl -n vm.loadavg))" >> $log
$W/R7B/compile.sh "$@" >> $log 2>&1; rc=$?
echo "$(date '+%T') build rc=$rc" >> $log; exit $rc
