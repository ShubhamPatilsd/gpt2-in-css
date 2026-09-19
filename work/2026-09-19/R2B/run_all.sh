#!/bin/zsh
# R2B driver: Chromium mutex + AC check + caffeinate, then MB6..MB9 in order (3 trials + 1 warm-up).
#   ./run_all.sh [extra run.mjs args]      e.g. ./run_all.sh --filter '^mb9-'
set -u
cd "$(dirname "$0")"
NODE=/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
LOCK=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/CHROME.lock
LOG=results/run_all.log
mkdir -p results
say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }

# AC power + mutex: acquire the lock, then re-check AC (the lock wait can outlast the power state); release and wait if on battery
while true; do
  until pmset -g batt | head -1 | grep -q "AC Power"; do say "on battery; waiting"; sleep 60; done
  until mkdir "$LOCK" 2>/dev/null; do say "CHROME.lock held by another agent; polling"; sleep 15; done
  if pmset -g batt | head -1 | grep -q "AC Power"; then break; fi
  rmdir "$LOCK"; say "lock taken but on battery; released, waiting for AC"
done
trap 'rmdir "$LOCK" 2>/dev/null; say "lock released"' EXIT INT TERM
# no other Chrome
n=$(pgrep -f "Google Chrome --" | wc -l | tr -d ' ')
if [ "$n" != "0" ]; then say "REFUSING: $n Google Chrome processes running"; exit 1; fi
say "START lock taken; AC=$(pmset -g batt | head -1); args: $*"
caffeinate -dims $NODE run.mjs --trials 3 --warmup 1 "$@" >> "$LOG" 2>&1
say "END rc=$?"
