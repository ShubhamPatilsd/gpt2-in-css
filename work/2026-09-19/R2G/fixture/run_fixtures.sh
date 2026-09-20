#!/bin/sh
# R2G: acquire CHROME.lock (mkdir mutex, poll 15 s), run the fixture families, release.
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
HERE=$ROOT/R2G/fixture
NODE=/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
FILTER=${1:-'pa-|svg-|rd-'}
OUT=${2:-results}
LOG=$ROOT/R2G.log.md
t0=$(date +%s)
# wait for AC power first (PLAN: timing only on AC), poll 30 s, give up after 6 h
while ! pmset -g batt | grep -qE "AC Power|AC attached"; do
  sleep 30
  if [ $(( $(date +%s) - t0 )) -gt 21600 ]; then echo "- $(date +%H:%M:%S) R2G gave up waiting for AC power after 6 h" >> "$LOG"; exit 3; fi
done
echo "- $(date +%H:%M:%S) AC power detected after $(( $(date +%s) - t0 )) s; now polling CHROME.lock" >> "$LOG"
while ! mkdir "$ROOT/CHROME.lock" 2>/dev/null; do
  sleep 15
  if [ $(( $(date +%s) - t0 )) -gt 14400 ]; then echo "- $(date +%H:%M:%S) R2G gave up waiting for CHROME.lock after 4 h" >> "$LOG"; exit 1; fi
done
echo "R2G fixture run $(date +%H:%M:%S) filter=$FILTER" > "$HERE/lock-owner.txt"
echo "- $(date +%H:%M:%S) acquired CHROME.lock after $(( $(date +%s) - t0 )) s; running fixtures filter=$FILTER -> R2G/fixture/$OUT" >> "$LOG"
# wait for any stray Chrome from the previous holder to exit
for i in 1 2 3 4 5 6 7 8; do pgrep -f "Google Chrome --" >/dev/null || break; sleep 5; done
cd "$HERE"
pmset -g batt | grep -qE 'AC Power|AC attached' || { echo "- $(date +%H:%M:%S) NOT on AC power; aborting" >> "$LOG"; rm -f "$ROOT/CHROME.lock/owner"; rmdir "$ROOT/CHROME.lock"; exit 2; }
caffeinate -dims "$NODE" run.mjs --trigger attr --trials 3 --warmup 1 --settle-ms 600 --filter "$FILTER" --out "$OUT" --traces traces --save-all-traces > "$OUT.stdout.log" 2>&1
rc=$?
rm -f "$ROOT/CHROME.lock/owner"; rmdir "$ROOT/CHROME.lock"
echo "- $(date +%H:%M:%S) fixtures done rc=$rc; lock released" >> "$LOG"
