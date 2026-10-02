#!/bin/zsh
# R7X: ONE Chrome step (run from the harness, not detached): waits for R7B's armed sampled runs (R7B/CHAIN-3-DONE or run_chain3.sh gone), then
# R7X/with_lock.sh <label> <wall-cap> <command…> with a 60 s retry on rc 8 (gate) / 9 (power); DONE-<marker> on rc 0. Env for inner.sh is inherited.
# usage: step.sh <marker> <label> <wall-cap-s> <command…>
set -u; W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R7X
marker=$1; label=$2; cap=$3; shift 3
logline() { echo "- $(date '+%F %T') [R7X step/$label] $*" >> $W/R7X.log.md; echo "$(date '+%T') $*"; }
n=0; while [[ ! -f $W/R7B/CHAIN-3-DONE ]] && pgrep -f "R7B/run_chain3.sh" >/dev/null; do (( n % 15 == 0 )) && logline "waiting for R7B's chain (lock: $(cat $W/CHROME.lock/owner 2>/dev/null || echo free); charge $(pmset -g batt | sed -n 2p | grep -oE '[0-9]+%'))"; sleep 60; n=$((n+1)); done
n=0; while true; do $R/with_lock.sh $label $cap "$@"; rc=$?; (( rc == 8 || rc == 9 )) || break; (( n % 15 == 0 )) && logline "refused rc=$rc ($( (( rc == 9 )) && echo 'charge < 40 %' || echo gate)) — retrying every 60 s"; sleep 60; n=$((n+1)); done
(( rc == 0 )) && touch $R/DONE-$marker
logline "step finished rc=$rc (battery — timing not comparable)"; exit $rc
