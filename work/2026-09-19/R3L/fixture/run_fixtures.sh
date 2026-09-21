#!/bin/zsh
# R3L fixture run under the Chromium mutex (PLAN.md + R2H/R3F refinements): mkdir lock (poll 15 s), refuse while a
# foreign headless Chrome runs, touch the lock every 30 s, release promptly. usage: run_fixtures.sh [filter] [out]
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
HERE=$W/R3L/fixture
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
FILTER=${1:-'lat-'}; OUT=${2:-results}
CHROME='^/Applications/Google Chrome.app/Contents/MacOS/Google Chrome .*--headless'
logline() { echo "- $(date '+%F %T') [R3L fixture/$OUT] $*" >> $W/R3L.log.md; echo "$(date '+%T') $*"; }
pmset -g batt | grep -qE 'AC Power|AC attached' || { logline "not on AC power; refusing"; exit 2; }
waited=0
while true; do
  while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held, polling every 3 s"; sleep 3; waited=$((waited+3)); done
  for _ in $(seq 1 30); do pgrep -f "$CHROME" >/dev/null || break; sleep 3; waited=$((waited+3)); done
  pgrep -f "$CHROME" >/dev/null || break
  logline "lock acquired but a foreign Chrome still runs after 90 s — releasing, back to polling"
  rmdir $W/CHROME.lock 2>/dev/null; sleep 15
done
echo "R3L $(date -u +%FT%TZ) fixture/$OUT" > $W/CHROME.lock/owner
( while [[ -d $W/CHROME.lock ]]; do touch $W/CHROME.lock; sleep 30; done ) & tpid=$!
trap 'kill $tpid 2>/dev/null; rm -rf $W/CHROME.lock' EXIT INT TERM
logline "START (waited ${waited}s) load=$(sysctl -n vm.loadavg) filter=$FILTER"
cd $HERE
extra=(); [[ -n ${EXTRA_ARGS:-} ]] && extra=(--extra-args "$EXTRA_ARGS")
caffeinate -dims $NODE run.mjs --trigger attr --trials 3 --warmup 1 --settle-ms 600 --filter "$FILTER" --out "$OUT" --traces traces-$OUT --save-all-traces "${extra[@]}" > $OUT.stdout.log 2>&1
rc=$?
pgrep -f "$CHROME" >/dev/null && { logline "Chrome still alive, killing"; pkill -f "$CHROME"; sleep 2; }
kill $tpid 2>/dev/null; rm -rf $W/CHROME.lock; trap - EXIT INT TERM
logline "END rc=$rc lock released"
exit $rc
