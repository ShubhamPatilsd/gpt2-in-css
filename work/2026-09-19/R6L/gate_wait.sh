#!/bin/zsh
# R6L: wait (poll 60 s) until the Chrome gate is open, then run the command under R6L/with_lock.sh.
# usage: gate_wait.sh <max-wait-s> <label> <wall-cap-s> <command...>
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
maxwait=$1; label=$2; cap=$3; shift 3
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
free_gb() { df -g $W | tail -1 | awk '{print $4}'; }
swap_used_mb() { sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1; }
gate_ok() { on_ac && { { (( $(free_gb) >= 4 )) && (( $(swap_used_mb) < 4000 )); } || { (( $(free_gb) >= 3 )) && (( $(swap_used_mb) < 3000 )); }; }; }
t=0
while ! gate_ok; do (( t >= maxwait )) && { echo "- $(date '+%F %T') gate_wait/$label: gate still closed after ${t}s (AC=$(on_ac && echo 1 || echo 0) disk=$(free_gb)GB swap=$(swap_used_mb)MB) — giving up" >> $W/R6L.log.md; exit 8; }; sleep 60; t=$((t+60)); done
echo "- $(date '+%F %T') gate_wait/$label: gate OPEN after ${t}s (disk=$(free_gb)GB swap=$(swap_used_mb)MB) → with_lock" >> $W/R6L.log.md
exec $W/R6L/with_lock.sh $label $cap "$@"
