#!/bin/sh
# R2G runner v2: poll CHROME.lock (mkdir mutex) <= 60 s, touch it every 30 s while held, record load, release.
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
HERE=$ROOT/R2G/fixture
NODE=/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
FILTER=${1:-'pa-|svg-|rd-'}; OUT=${2:-results}; LOG=$ROOT/R2G.log.md
t0=$(date +%s)
while ! mkdir "$ROOT/CHROME.lock" 2>/dev/null; do
  sleep 5
  [ $(( $(date +%s) - t0 )) -gt 21600 ] && { echo "- $(date '+%F %T') R2G runner2 gave up on CHROME.lock after 6 h" >> "$LOG"; exit 1; }
done
echo "- $(date '+%F %T') R2G runner2 acquired CHROME.lock after $(( $(date +%s) - t0 )) s; filter=$FILTER out=$OUT; load=$(uptime | sed 's/.*load averages://')" >> "$LOG"
( while [ -d "$ROOT/CHROME.lock" ]; do touch "$ROOT/CHROME.lock"; sleep 30; done ) & TOUCHER=$!
( while [ -d "$ROOT/CHROME.lock" ]; do echo "$(date +%T) $(uptime | sed 's/.*load averages://')" >> "$HERE/$OUT.load.log"; sleep 30; done ) & LOADER=$!
for i in 1 2 3 4 5 6; do pgrep -f "Google Chrome --" >/dev/null || break; sleep 5; done
cd "$HERE"
if pmset -g batt | grep -qE 'AC Power|AC attached'; then
  caffeinate -dims "$NODE" run.mjs --trigger attr --trials 3 --warmup 1 --settle-ms 600 --filter "$FILTER" --out "$OUT" --traces traces > "$OUT.stdout.log" 2>&1; rc=$?
else
  echo "- $(date '+%F %T') R2G runner2: not on AC, not running" >> "$LOG"; rc=2
fi
kill $TOUCHER $LOADER 2>/dev/null
rmdir "$ROOT/CHROME.lock"
echo "- $(date '+%F %T') R2G runner2 done rc=$rc; lock released; load=$(uptime | sed 's/.*load averages://')" >> "$LOG"
