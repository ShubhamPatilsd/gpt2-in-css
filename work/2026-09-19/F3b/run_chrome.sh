#!/bin/zsh
# F3b Chrome session under the Chromium mutex (PLAN.md). usage: run_chrome.sh <label> <command...>
# Acquires work/2026-09-19/CHROME.lock (polls every 15 s), refuses if another Chrome runs, runs the command, releases.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
label=$1; shift
logline() { echo "- $(date '+%F %T') [chrome/$label] $*" >> $W/F3b.log.md; echo "$*"; }
waited=0
while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held, polling every 15 s"; sleep 15; waited=$((waited+15)); done
echo "F3b $(date -u +%FT%TZ) $label" > $W/CHROME.lock/owner
trap 'rm -rf $W/CHROME.lock' EXIT INT TERM
if pgrep -f "Google Chrome --" >/dev/null; then logline "another Chrome is running — abort"; exit 3; fi
logline "START (waited ${waited}s): $*"
"$@"
rc=$?
pgrep -f "Google Chrome --" >/dev/null && { logline "Chrome still alive, killing"; pkill -f "Google Chrome --"; sleep 2; }
logline "END rc=$rc"
exit $rc
