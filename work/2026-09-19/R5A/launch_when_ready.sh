#!/bin/bash
# R5A: every 60 s check AC power + >=3 GB free; when both hold, run run_trace8.sh; if it refuses on a precondition (rc 8/9) keep polling; stop on any other exit.
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
n=0
while true; do
  b=$(pmset -g batt | head -1); avail_kb=$(df -k / | awk 'NR==2{print $4}'); swap_used_mb=$(sysctl -n vm.swapusage | sed 's/.*used = \([0-9.]*\)M.*/\1/' | cut -d. -f1)
  # coordinator gate (12:51): AC AND free disk >= 3.0 GB AND swap used < 3,000 MB; poll 60 s; no retry until all hold
  if echo "$b" | grep -q "AC Power" && [ "$avail_kb" -ge 3145728 ] && [ "${swap_used_mb:-9999}" -lt 3000 ]; then
    n=$((n+1)); echo "$(date '+%F %T') preconditions hold (avail_kb=$avail_kb) -> attempt $n" >> R5A/machine_poll.log
    zsh R5A/run_trace8.sh t$n > R5A/run_trace8-$n.out 2>&1; rc=$?
    echo "$(date '+%F %T') run_trace8.sh attempt $n exited rc=$rc" >> R5A/machine_poll.log
    if [ $rc -ne 8 ] && [ $rc -ne 9 ]; then touch R5A/RUNS-FINISHED; exit $rc; fi
  else
    echo "$(date '+%F %T') waiting power='$b' avail_kb=$avail_kb swap_used_mb=$swap_used_mb" >> R5A/machine_poll.log
  fi
  sleep 60
done
