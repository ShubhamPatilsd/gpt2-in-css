#!/bin/zsh
# R2E pause-and-hold fixture under the Chromium mutex (PLAN.md + coordinator 2026-09-20: touch the lock every 30 s while held; a lock
# not touched for >180 s is stale and taken over; the user's own Chrome may run — only another HEADLESS Chrome aborts). AC required.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
logline() { echo "- $(date '+%F %T') [hold-fixture] $*" >> $W/R2C.log.md; echo "$*"; }
waited=0
while ! mkdir $W/CHROME.lock 2>/dev/null; do
  age=$(( $(date +%s) - $(stat -f %m $W/CHROME.lock 2>/dev/null || date +%s) ))
  if (( age > 180 )); then logline "CHROME.lock stale (${age}s since last touch) — taking over"; rmdir $W/CHROME.lock 2>/dev/null; continue; fi
  (( waited == 0 )) && logline "CHROME.lock held (age ${age}s), polling every 15 s"; sleep 15; waited=$((waited+15))
done
( while true; do touch $W/CHROME.lock 2>/dev/null || exit; sleep 30; done ) & toucher=$!
trap 'kill $toucher 2>/dev/null; rmdir $W/CHROME.lock 2>/dev/null' EXIT INT TERM
if pgrep -f "Google Chrome.*--headless" >/dev/null; then logline "another HEADLESS Chrome is running — abort"; exit 3; fi
logline "START pause-and-hold fixture (waited ${waited}s) load='$(uptime | sed 's/.*load averages: //')' batt='$(pmset -g batt | sed -n 2p | tr -s '\t' ' ')' user-chrome-procs=$(pgrep -f 'Google Chrome' | wc -l | tr -d ' ')"
cd $W/R2C/hold
caffeinate -dims $NODE run_hold.mjs --pages 1024,0 --trials 2 --settle-ms 400 --idle-ms 2000 --out results > run_hold.stdout.log 2>&1
rc=$?
pgrep -f "Google Chrome.*--headless" >/dev/null && { logline "headless Chrome still alive, killing"; pkill -f "Google Chrome.*--headless"; sleep 2; }
kill $toucher 2>/dev/null; rmdir $W/CHROME.lock 2>/dev/null; trap - EXIT INT TERM
logline "END fixture rc=$rc load='$(uptime | sed 's/.*load averages: //')'"
touch $W/R2C/hold/DONE
exit $rc
