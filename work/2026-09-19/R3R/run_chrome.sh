#!/bin/zsh
# R3R Chrome session under the Chromium mutex (PLAN.md + R2H refinements): mkdir lock (poll 15 s), refuse while a
# foreign headless Chrome runs, touch the lock every 30 s, watchdog (wall cap + Chrome-exit), release promptly.
# usage: run_chrome.sh <label> <wall-cap-s> <command...>   (the command must write its own outputs)
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
label=$1; cap=$2; shift 2
CHROME='^/Applications/Google Chrome.app/Contents/MacOS/Google Chrome .*--headless'
logline() { echo "- $(date '+%F %T') [R3R chrome/$label] $*" >> $W/R3R.log.md; echo "$(date '+%T') $*"; }
waited=0
while true; do
  while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held, polling every 3 s"; sleep 3; waited=$((waited+3)); done
  for _ in $(seq 1 30); do pgrep -f "$CHROME" >/dev/null || break; sleep 3; waited=$((waited+3)); done
  pgrep -f "$CHROME" >/dev/null || break
  logline "lock acquired but a foreign Chrome still runs after 90 s — releasing, back to polling"
  rmdir $W/CHROME.lock 2>/dev/null; sleep 15
done
echo "R3R $(date -u +%FT%TZ) $label" > $W/CHROME.lock/owner
( while [[ -d $W/CHROME.lock ]]; do touch $W/CHROME.lock; sleep 30; done ) & tpid=$!
trap 'kill $tpid 2>/dev/null; rm -rf $W/CHROME.lock' EXIT INT TERM
logline "START (waited ${waited}s) power=$(pmset -g batt | sed -n 2p | tr -s "\t" " " | cut -c1-60) load=$(sysctl -n vm.loadavg): $*"
"$@" & npid=$!
t0=$(date +%s); seen=0; gone=0; why=""
while kill -0 $npid 2>/dev/null; do
  sleep 5; now=$(date +%s)
  if pgrep -f "$CHROME" >/dev/null; then seen=1; gone=0
  elif (( seen )); then (( gone == 0 )) && gone=$now; (( now - gone >= 60 )) && { why="Chrome gone 60 s, node alive (hung close)"; break; }
  fi
  (( now - t0 >= cap )) && { why="wall cap ${cap}s"; break; }
done
if [[ -n $why ]]; then logline "WATCHDOG: $why — killing $npid"; pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; sleep 2; kill -9 $npid 2>/dev/null; rc=124; else wait $npid; rc=$?; fi
pgrep -f "$CHROME" >/dev/null && { logline "Chrome still alive, killing"; pkill -f "$CHROME"; sleep 2; }
kill $tpid 2>/dev/null; rm -rf $W/CHROME.lock; trap - EXIT INT TERM
logline "END rc=$rc lock released"
exit $rc
