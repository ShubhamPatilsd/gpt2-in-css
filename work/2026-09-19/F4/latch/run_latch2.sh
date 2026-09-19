#!/bin/zsh
# F4 latch micro-test under the Chromium mutex (PLAN.md). F5's harness copy (latch/run.mjs), 3 trials, 1 warm-up (arms the transitions).
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
logline() { echo "- $(date '+%F %T') [latch] $*" >> $W/F4.log.md; echo "$*"; }
waited=0
while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held, polling every 15 s"; sleep 15; waited=$((waited+15)); done
trap 'rmdir $W/CHROME.lock 2>/dev/null' EXIT INT TERM
if pgrep -f "Google Chrome --" >/dev/null; then logline "another Chrome is running — abort"; exit 3; fi
logline "START latch micro-test 2 (bytes vs entries) (waited ${waited}s) batt='$(pmset -g batt | sed -n 2p | tr -s '\t' ' ')'"
cd $W/F4/latch
caffeinate -dims $NODE run.mjs --trials 3 --warmup 1 --settle-ms 500 --idle-ms 3000 --out results2 --traces traces2 > run.stdout.log 2>&1
rc=$?
pgrep -f "Google Chrome --" >/dev/null && { logline "Chrome still alive, killing"; pkill -f "Google Chrome --"; sleep 2; }
rmdir $W/CHROME.lock 2>/dev/null; trap - EXIT INT TERM
rm -f $W/F4/latch/pages/*.html
logline "END micro-test 2 rc=$rc (pages deleted)"
exit $rc
