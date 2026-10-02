#!/bin/zsh
# R7B: run compile.sh once CHROME.lock is free (no build while another agent's Chrome holds the lock) and load1 < 8. usage: build_when_free.sh <log> <out> <cap> [blocks]  (flags via env)
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; log=$1; shift
n=0
while [[ -e $W/CHROME.lock ]] || (( $(sysctl -n vm.loadavg | awk '{print int($2)}') >= 8 )); do
  (( n % 60 == 0 )) && echo "$(date '+%T') waiting: lock=$(cat $W/CHROME.lock/owner 2>/dev/null || echo free) load=$(sysctl -n vm.loadavg)" >> $log
  n=$((n+1)); sleep 5
done
echo "$(date '+%T') building $* (lock free, load $(sysctl -n vm.loadavg))" >> $log
VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 $W/R7B/compile.sh "$@" >> $log 2>&1; rc=$?
echo "$(date '+%T') build rc=$rc" >> $log; exit $rc
