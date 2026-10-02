#!/bin/zsh
# R7X: run one compile.sh build while HOLDING CHROME.lock (no build while another agent's Chrome holds the lock; nobody's Chrome starts while we build).
# lock: mkdir CHROME.lock (poll 5 s), owner "R7X build <pid> <time>", touch -c every 30 s, rmdir only if the owner marker is mine.
# usage: build_lock.sh <log> <out> <cap> [blocks]   (flags + VALUE_LAYOUT/R4S_SMALL_HOPS via env)
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; log=$1; shift
CHROME='^/Applications/.*Google Chrome .*--headless'
OWNER="R7X build $$ $(date '+%F %T')"
mine() { [[ -d $W/CHROME.lock && -f $W/CHROME.lock/owner ]] && grep -q "^R7X build $$ " $W/CHROME.lock/owner; }
n=0
while true; do
  while ! mkdir $W/CHROME.lock 2>/dev/null; do (( n % 60 == 0 )) && echo "$(date '+%T') waiting for CHROME.lock ($(cat $W/CHROME.lock/owner 2>/dev/null || echo 'dir, no owner'))" >> $log; n=$((n+1)); sleep 5; done
  echo "$OWNER" > $W/CHROME.lock/owner
  pgrep -f "$CHROME" >/dev/null || break
  echo "$(date '+%T') lock acquired but a foreign headless Chrome runs — releasing" >> $log; rm -f $W/CHROME.lock/owner; rmdir $W/CHROME.lock; sleep 10
done
( while mine; do touch -c $W/CHROME.lock $W/CHROME.lock/owner 2>/dev/null; sleep 30; done ) & tpid=$!
echo "$(date '+%T') building $* (lock held by '$OWNER', load $(sysctl -n vm.loadavg), env $(env | grep -E '^(R7B|R7H|R6X)_' | sort | tr '\n' ' '))" >> $log
$W/R7X/compile.sh "$@" >> $log 2>&1; rc=$?
echo "$(date '+%T') build rc=$rc" >> $log
kill $tpid 2>/dev/null; wait $tpid 2>/dev/null
if mine; then rm -f $W/CHROME.lock/owner; rmdir $W/CHROME.lock; fi
exit $rc
